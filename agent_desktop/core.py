"""Small stdlib-only clients. Scientific dependencies stay in ChemAnalyzer."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib import request, error


def json_request(base, path, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read(16_000_000).decode("utf-8"))
    except error.HTTPError as exc:
        try:
            detail = json.loads(exc.read(16000).decode()).get("detail", "Ошибка сервиса")
        except (ValueError, UnicodeError):
            detail = "Ошибка сервиса"
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from None
    except error.URLError:
        raise RuntimeError("Нет связи с сервисом. Проверьте, запущен ли он.") from None


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

    def start(self):
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
                   CHEMANALYZER_DATA_DIR=str(storage), CHEMANALYZER_FRONTEND_DIST="")
        self.log = (storage / "backend.log").open("a", encoding="utf-8")
        self.process = subprocess.Popen([str(exe), "--port", str(port)], cwd=exe.parent, env=env,
                                       stdout=self.log, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.base = f"http://127.0.0.1:{port}"
        try:
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
        if self.process and self.process.poll() is None:
            if self.run_id:
                try:
                    self.api(f"/api/research/runs/{self.run_id}/cancel", {})
                except Exception:
                    pass
            self.process.terminate()
            try:
                self.process.wait(8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.log:
            self.log.close()
        self.process = self.base = self.log = None


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
