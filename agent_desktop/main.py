"""ChemAnalyzer Agent Desk: native Windows GUI, no scientific imports here."""
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from core import ChemistryAgent, ollama_models, chat


class AgentDesk(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Agent Desk · ChemAnalyzer и другие задачи")
        self.geometry("880x700")
        self.minsize(720, 560)
        self.agent = ChemistryAgent()
        self.events = queue.Queue()
        self.tasks = {}
        self.models = {}
        self.history = []
        self.busy = False
        self.chem_busy = False
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", padding=(12, 7))
        style.configure("TLabel", padding=3)
        ttk.Label(self, text="Agent Desk", font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=20, pady=(14, 0))
        ttk.Label(self, text="Научные модели и помощник для повседневных задач").pack(anchor="w", padx=20)
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=18, pady=10)
        chemistry, assistant = ttk.Frame(tabs, padding=12), ttk.Frame(tabs, padding=12)
        tabs.add(chemistry, text="ChemAnalyzer")
        tabs.add(assistant, text="ИИ-помощник")
        self.build_chemistry(chemistry)
        self.build_assistant(assistant)
        self.status = tk.StringVar(value="Готово. Выберите режим работы.")
        ttk.Label(self, textvariable=self.status, wraplength=820).pack(fill="x", padx=18, pady=(0, 10))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.pump)

    def work(self, function, callback=None, chemistry=False):
        if (self.chem_busy if chemistry else self.busy):
            return
        if chemistry:
            self.chem_busy = True
        else:
            self.busy = True
        def worker():
            try:
                self.events.put((callback, function(), chemistry, None))
            except Exception as exc:
                self.events.put((None, None, chemistry, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def pump(self):
        try:
            while True:
                callback, result, chemistry, error = self.events.get_nowait()
                if chemistry:
                    self.chem_busy = False
                elif chemistry is False:
                    self.busy = False
                if error:
                    self.status.set("Ошибка: " + error)
                    messagebox.showerror("Agent Desk", error)
                elif callback:
                    callback(result)
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def show(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, indent=2))
        self.output.configure(state="disabled")

    def build_chemistry(self, frame):
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Button(row, text="Запустить движок", command=self.start_chemistry).pack(side="left")
        ttk.Button(row, text="Обновить список", command=self.refresh).pack(side="left", padx=6)
        self.task = tk.StringVar()
        ttk.Label(frame, text="Исследовательская задача").pack(anchor="w", pady=(10, 0))
        self.task_box = ttk.Combobox(frame, textvariable=self.task, state="readonly")
        self.task_box.pack(fill="x")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=8)
        ttk.Button(row, text="Демонстрация FreeSolv", command=self.demo).pack(side="left")
        ttk.Button(row, text="Импорт задачи / CSV", command=self.import_task).pack(side="left", padx=5)
        ttk.Button(row, text="Обучить", command=self.train).pack(side="left")
        ttk.Button(row, text="Отменить", command=self.cancel).pack(side="left", padx=5)
        self.model = tk.StringVar()
        ttk.Label(frame, text="Модель для исследовательского прогноза").pack(anchor="w")
        self.model_box = ttk.Combobox(frame, textvariable=self.model, state="readonly")
        self.model_box.pack(fill="x")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=8)
        self.smiles = tk.StringVar(value="CCO")
        ttk.Entry(row, textvariable=self.smiles).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Проверить прогноз", command=self.predict).pack(side="left", padx=5)
        self.output = tk.Text(frame, wrap="word", font=("Consolas", 10), state="disabled")
        self.output.pack(fill="both", expand=True)
        ttk.Label(frame, text="Модели остаются experimental. Прогноз требует экспериментальной проверки.", wraplength=780).pack(anchor="w")

    def start_chemistry(self):
        if self.agent.process:
            self.refresh()
            return
        self.status.set("Запуск научного движка…")
        self.work(self.agent.start, lambda _: (self.status.set("ChemAnalyzer готов"), self.refresh()), chemistry=True)

    def refresh(self):
        def load():
            return self.agent.api("/api/research/tasks"), self.agent.api("/api/research/models")
        def display(data):
            tasks, models = data
            self.tasks = {f"{t['name']} · {t['id'][:8]}": t["id"] for t in tasks}
            self.models = {f"{m['task']['name']} · {m['status']} · {m['id'][:8]}": m["id"] for m in models if m["status"] != "archived"}
            self.task_box["values"] = list(self.tasks)
            self.model_box["values"] = list(self.models)
            if self.task.get() not in self.tasks:
                self.task.set(next(iter(self.tasks), ""))
            if self.model.get() not in self.models:
                self.model.set(next(reversed(self.models), ""))
        self.work(load, display, chemistry=True)

    def demo(self):
        self.status.set("Загрузка экспериментальных данных FreeSolv…")
        def run():
            task = self.agent.api("/api/research/status")["default_task"]
            identifier = self.agent.api("/api/research/tasks", task)["id"]
            return self.agent.api(f"/api/research/tasks/{identifier}/freesolv", {}, timeout=120)
        self.work(run, lambda data: (self.show(data), self.status.set("FreeSolv импортирован. Выберите задачу и нажмите «Обучить»."), self.refresh()), chemistry=True)

    def import_task(self):
        if self.chem_busy:
            return
        config = filedialog.askopenfilename(title="Конфигурация задачи JSON", filetypes=[("JSON", "*.json")])
        if not config:
            return
        csv = filedialog.askopenfilename(title="Экспериментальный CSV", filetypes=[("CSV", "*.csv")])
        if not csv:
            return
        provenance = filedialog.askopenfilename(title="Provenance JSON", filetypes=[("JSON", "*.json")])
        if not provenance:
            return
        def run():
            if Path(csv).stat().st_size > 8_000_000 or max(Path(config).stat().st_size, Path(provenance).stat().st_size) > 16000:
                raise ValueError("Слишком большой файл: CSV ≤8 MB, JSON ≤16 KB")
            task = self.agent.api("/api/research/tasks", json.loads(Path(config).read_text(encoding="utf-8-sig")))
            return self.agent.api(f"/api/research/tasks/{task['id']}/import", dict(csv_text=Path(csv).read_text(encoding="utf-8-sig"), provenance=json.loads(Path(provenance).read_text(encoding="utf-8-sig"))))
        self.work(run, lambda data: (self.show(data), self.refresh()), chemistry=True)

    def train(self):
        identifier = self.tasks.get(self.task.get())
        if not identifier:
            messagebox.showinfo("Задача", "Сначала запустите движок и выберите задачу")
            return
        self.status.set("Запуск обучения…")
        def run():
            state = self.agent.api(f"/api/research/tasks/{identifier}/train", {})
            self.agent.run_id = state["id"]
            while state["status"] in ("queued", "running"):
                time.sleep(1)
                state = self.agent.api(f"/api/research/runs/{self.agent.run_id}")
                self.events.put((lambda stage: self.status.set("Обучение: " + stage), state["stage"], None, None))
            self.agent.run_id = None
            return state
        self.work(run, lambda state: (self.show(state.get("result", state)), self.status.set("Обучение: " + state["status"]), self.refresh()), chemistry=True)

    def cancel(self):
        identifier = self.agent.run_id
        if identifier:
            self.work(lambda: self.agent.api(f"/api/research/runs/{identifier}/cancel", {}), lambda _: self.status.set("Задача отменена"))

    def predict(self):
        identifier, smiles = self.models.get(self.model.get()), self.smiles.get()
        if identifier:
            self.work(lambda: self.agent.api(f"/api/research/models/{identifier}/predict", dict(smiles=smiles)), self.show, chemistry=True)

    def build_assistant(self, frame):
        ttk.Label(frame, text="Локальный ИИ через Ollama · текст, объяснения и планы", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Нужен запущенный Ollama с установленной моделью. Сообщения отправляются на localhost:11434.", wraplength=780).pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=8)
        self.profile = ttk.Combobox(row, state="readonly", values=["Универсальный помощник", "Работа с текстом", "Планировщик задач"])
        self.profile.current(0)
        self.profile.pack(side="left")
        self.llm = ttk.Combobox(row)
        self.llm.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row, text="Найти модели", command=lambda: self.work(ollama_models, self.set_models)).pack(side="left")
        self.conversation = tk.Text(frame, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.conversation.pack(fill="both", expand=True)
        self.prompt = tk.Text(frame, height=5, wrap="word", font=("Segoe UI", 10))
        self.prompt.pack(fill="x", pady=8)
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Button(row, text="Отправить", command=self.send).pack(side="left")
        ttk.Button(row, text="Загрузить текст", command=self.load_text).pack(side="left", padx=6)
        ttk.Button(row, text="Новый диалог", command=self.clear_chat).pack(side="left")

    def set_models(self, models):
        self.llm["values"] = models
        if models:
            self.llm.set(models[0])
        self.status.set(f"Найдено моделей Ollama: {len(models)}")

    def clear_chat(self):
        if not self.busy:
            self.history = []
            self.conversation.configure(state="normal")
            self.conversation.delete("1.0", "end")
            self.conversation.configure(state="disabled")

    def load_text(self):
        path = filedialog.askopenfilename(filetypes=[("Текст", "*.txt *.md *.csv *.json")])
        if path:
            try:
                if Path(path).stat().st_size > 100000:
                    raise ValueError("Лимит текстового файла — 100 KB")
                self.prompt.insert("end", Path(path).read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                messagebox.showerror("Файл", str(exc))

    def send(self):
        if self.busy:
            return
        text, model, profile = self.prompt.get("1.0", "end").strip(), self.llm.get(), self.profile.get()
        if not text:
            return
        if len(text) > 100000:
            messagebox.showerror("Сообщение", "Лимит сообщения — 100 000 символов")
            return
        messages = self.history[-10:] + [dict(role="user", content=text)]
        self.status.set("Локальная модель готовит ответ…")
        def display(answer):
            self.history = messages + [dict(role="assistant", content=answer)]
            self.conversation.configure(state="normal")
            self.conversation.insert("end", f"Вы: {text}\n\nПомощник: {answer}\n\n")
            self.conversation.see("end")
            self.conversation.configure(state="disabled")
            self.prompt.delete("1.0", "end")
            self.status.set("Ответ получен")
        self.work(lambda: chat(model, messages, profile), display)

    def close(self):
        if self.chem_busy and not messagebox.askyesno("Выход", "Остановить научный движок и закрыть приложение?"):
            return
        # All backend calls are bounded; closing also cancels the current research run.
        self.withdraw()
        def cleanup():
            self.agent.stop()
            self.events.put((lambda _: self.destroy(), None, False, None))
        threading.Thread(target=cleanup, daemon=True).start()


if __name__ == "__main__":
    AgentDesk().mainloop()
