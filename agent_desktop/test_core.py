import json
from pathlib import Path
import sys
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from core import ChemistryAgent, json_request, chat
from core import find_running_backends


def test_http_error_has_user_message():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"detail":"Dataset checksum mismatch"}')
        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(RuntimeError, match="checksum mismatch"):
            json_request(f"http://127.0.0.1:{server.server_port}", "/")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_chat_uses_local_model_and_profile():
    with patch("core.json_request", return_value={"message": {"content": "Technical fixture"}}) as call:
        assert chat("test-model", [{"role": "user", "content": "Test"}], "Работа с текстом") == "Technical fixture"
        base, path, body = call.call_args.args
        assert base == "http://127.0.0.1:11434" and path == "/api/chat"
        assert body["stream"] is False
        assert body["messages"][0]["role"] == "system"


def test_missing_model_and_empty_response_are_errors():
    with pytest.raises(ValueError):
        chat("", [], "Универсальный помощник")
    with patch("core.json_request", return_value={"message": {"content": ""}}):
        with pytest.raises(RuntimeError):
            chat("test", [], "Универсальный помощник")


def test_backend_required_before_request():
    with pytest.raises(RuntimeError, match="Сначала"):
        ChemistryAgent().api("/health")


def test_local_request_does_not_initialize_https():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"healthy"}')
        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch("ssl.create_default_context", side_effect=FileNotFoundError("frozen SSL failure")):
            assert json_request(f"http://127.0.0.1:{server.server_port}", "/health")["status"] == "healthy"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("base", ["https://127.0.0.1", "http://remote.example", "http://user:secret@localhost"])
def test_local_client_rejects_external_addresses(base):
    with pytest.raises(ValueError):
        json_request(base, "/health")


def test_discovery_checks_identity_and_research_capability():
    def response(base, path, timeout):
        if base.endswith(":1234"):
            return {"application": "Unrelated service"}
        if path == "/health":
            return {"application": "ChemAnalyzer", "version": "3.2.0"}
        if base.endswith(":5678"):
            raise RuntimeError("HTTP 404")
        return {"enabled": True}
    with patch("core.running_backend_ports", return_value=[1234, 5678, 9012]), patch("core.json_request", side_effect=response):
        found = find_running_backends()
    assert [entry["base"] for entry in found] == ["http://127.0.0.1:5678", "http://127.0.0.1:9012"]
    assert [entry["research_enabled"] for entry in found] == [False, True]


def test_attaching_does_not_spawn_or_stop_running_application():
    agent = ChemistryAgent()
    existing = dict(base="http://127.0.0.1:5001", version="3.2.0", research_enabled=True)
    with patch("core.find_running_backends", return_value=[existing]), patch("core.json_request", return_value={"enabled": True}), patch("core.subprocess.Popen") as spawn:
        assert agent.start()["enabled"]
        assert agent.base == existing["base"]
        assert agent.process is None
        agent.stop()
        spawn.assert_not_called()
    assert agent.base is None


def test_failed_process_launch_releases_log(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    exe = tmp_path / "build/research-backend/chemanalyzer-backend/chemanalyzer-backend.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    agent = ChemistryAgent()
    with patch("core.project_root", return_value=tmp_path), patch("core.find_running_backends", return_value=[]), patch("core.subprocess.Popen", side_effect=FileNotFoundError("launch failed")):
        with pytest.raises(FileNotFoundError):
            agent.start()
    assert agent.log is None and agent.process is None and agent.base is None


def test_repeated_start_reuses_healthy_connection():
    agent = ChemistryAgent()
    agent.base = "http://127.0.0.1:5001"
    def response(base, path, body=None, timeout=30):
        return {"application": "ChemAnalyzer"} if path == "/health" else {"enabled": True}
    with patch("core.json_request", side_effect=response), patch("core.find_running_backends") as discover:
        assert agent.start()["enabled"]
        discover.assert_not_called()
