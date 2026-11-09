import json
from pathlib import Path
import sys
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from core import ChemistryAgent, json_request, chat


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
