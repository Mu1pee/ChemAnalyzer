"""Small stdlib-only clients. Scientific dependencies stay in ChemAnalyzer."""
import json
import http.client
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit


def json_request(base, path, body=None, timeout=30):
    address = urlsplit(base)
    if address.scheme != "http" or address.hostname not in ("127.0.0.1", "localhost", "::1") or address.username or address.password:
        raise ValueError("Подключение поддерживается только к локальному HTTP-сервису")
    data = None if body is None else json.dumps(body).encode("utf-8")
    connection = http.client.HTTPConnection(address.hostname, address.port, timeout=timeout)
    try:
        connection.request("GET" if body is None else "POST", path, body=data,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        payload = response.read(16_000_001)
        if len(payload) > 16_000_000:
            raise RuntimeError("Ответ сервиса превышает 16 MB")
        try:
            result = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise RuntimeError(f"Сервис вернул некорректный ответ (HTTP {response.status})") from None
        if response.status >= 400:
            detail = result.get("detail", "Ошибка сервиса") if isinstance(result, dict) else "Ошибка сервиса"
            raise RuntimeError(f"HTTP {response.status}: {detail}")
        return result
    except (OSError, http.client.HTTPException):
        raise RuntimeError("Нет связи с сервисом. Проверьте, запущен ли он.") from None
    finally:
        connection.close()


def running_backend_ports():
    """Read candidate ports from actual ChemAnalyzer processes, never scan the network."""
    ports = {8000}
    if os.name != "nt":
        return sorted(ports)
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    command = """
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$processes = Get-CimInstance Win32_Process -Filter "Name = 'chemanalyzer-backend.exe' OR Name = 'python.exe' OR Name = 'pythonw.exe'"
$chemProcesses = $processes | Where-Object { $_.Name -eq 'chemanalyzer-backend.exe' -or $_.CommandLine -match 'chemanalyzer_server\\.py' }
$portNumbers = foreach ($item in $chemProcesses) {
    if ($item.CommandLine -match '--port[ =]+(\\d+)') { [int]$Matches[1] }
}
ConvertTo-Json -InputObject @($portNumbers) -Compress
"""
    try:
        result = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", command],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                encoding="utf-8-sig", timeout=12, check=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        ports.update(port for port in json.loads(result.stdout) if isinstance(port, int) and 1024 <= port <= 65535)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return sorted(ports)


def find_running_backends():
    found = []
    for port in running_backend_ports():
        base = f"http://127.0.0.1:{port}"
        try:
            health = json_request(base, "/health", timeout=1)
            if not isinstance(health, dict) or health.get("application") != "ChemAnalyzer":
                continue
        except RuntimeError:
            continue
        try:
            research = json_request(base, "/api/research/status", timeout=2)
        except RuntimeError:
            research = {}
        enabled = isinstance(research, dict) and research.get("enabled") is True
        found.append(dict(base=base, version=health.get("version", "?"), research_enabled=enabled))
    return found


def project_root():
    start = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    for path in (start, *start.parents):
        if (path / "backend" / "app").is_dir():
            return path
    raise RuntimeError("Не найдена папка ChemAnalyzer. Разместите приложение внутри папки проекта.")


class ChemistryAgent:
    def __init__(self):
        self.process = None
        self.base = None
        self.run_id = None
        self.log = None
        self.connections = []

    def discover(self):
        self.connections = find_running_backends()
        return self.connections

    def start(self):
        if self.base:
            try:
                health = self.api("/health", timeout=2)
                status = self.api("/api/research/status", timeout=2)
                if health.get("application") == "ChemAnalyzer" and status.get("enabled") is True:
                    return status
            except RuntimeError:
                pass
            self.stop()
        connections = self.discover()
        for connection in connections:
            if connection["research_enabled"]:
                self.base = connection["base"]
                return self.api("/api/research/status")
        root = project_root()
        exe = root / "build/research-backend/chemanalyzer-backend/chemanalyzer-backend.exe"
        if not exe.exists():
            raise RuntimeError("Не найден собранный ChemAnalyzer backend в build/research-backend.")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        storage = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ChemAnalyzerAgent"
        storage.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, CHEMANALYZER_RESEARCH_ENABLED="1", CHEMANALYZER_DESKTOP="1",
                   CHEMANALYZER_DATA_DIR=str(storage), CHEMANALYZER_FRONTEND_DIST="",
                   PYINSTALLER_RESET_ENVIRONMENT="1")
        try:
            self.log = (storage / "backend.log").open("a", encoding="utf-8")
            self.process = subprocess.Popen([str(exe), "--port", str(port)], cwd=exe.parent, env=env,
                                           stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.base = f"http://127.0.0.1:{port}"
            for _ in range(120):
                if self.process.poll() is not None:
                    raise RuntimeError(f"Движок завершился. Журнал: {storage / 'backend.log'}")
                try:
                    if self.api("/health", timeout=1).get("application") == "ChemAnalyzer":
                        return self.api("/api/research/status")
                except RuntimeError:
                    pass
                time.sleep(.5)
            raise RuntimeError("Движок не запустился за 60 секунд")
        except Exception:
            self.stop()
            raise

    def api(self, path, body=None, timeout=30):
        if not self.base:
            raise RuntimeError("Сначала запустите ChemAnalyzer")
        return json_request(self.base, path, body, timeout)

    def stop(self):
        if self.run_id and self.base:
            try:
                self.api(f"/api/research/runs/{self.run_id}/cancel", {}, timeout=5)
            except Exception:
                pass
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.log:
            self.log.close()
        self.process = self.base = self.log = None
        self.run_id = None


def ollama_models():
    return [entry["name"] for entry in json_request("http://127.0.0.1:11434", "/api/tags")["models"]]


def chat(model, messages, profile):
    if not model.strip():
        raise ValueError("Выберите установленную модель Ollama")
    system = {
        "Универсальный помощник": "Помогай решать задачи пользователя. Не утверждай, что выполнил действия, если у тебя нет инструментов. Отвечай по-русски.",
        "Работа с текстом": "Редактируй и анализируй предоставленный текст. Отделяй факты от предположений. Отвечай по-русски.",
        "Планировщик задач": "Составляй конкретные пошаговые планы с проверяемыми результатами. Не утверждай, что выполнил план. Отвечай по-русски.",
    }[profile]
    result = json_request("http://127.0.0.1:11434", "/api/chat", dict(
        model=model, messages=[dict(role="system", content=system)] + messages,
        stream=False, options={"num_predict": 2048}), timeout=180)
    answer = result.get("message", {}).get("content")
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Модель не вернула текстовый ответ")
    return answer
