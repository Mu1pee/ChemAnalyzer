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
        self.geometry("1180x760")
        self.minsize(1060, 700)
        self.configure(bg="#111419")
        self.agent = ChemistryAgent()
        self.events = queue.Queue()
        self.tasks = {}
        self.models = {}
        self.history = []
        self.busy = False
        self.chem_busy = False
        self.setup_theme()
        sidebar = tk.Frame(self, bg="#181c23", width=216)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="◈  AGENT DESK", bg="#181c23", fg="#eff4fa", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=20, pady=(28, 4))
        tk.Label(sidebar, text="YOUR AI WORKSPACE", bg="#181c23", fg="#727d8e", font=("Segoe UI", 9)).pack(anchor="w", padx=22)
        tk.Label(sidebar, text="РАБОЧЕЕ ПРОСТРАНСТВО", bg="#181c23", fg="#727d8e", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=22, pady=(44, 12))
        self.navigation = []
        for index, label in enumerate(("⌬   ChemAnalyzer", "✦   ИИ-помощник")):
            button = tk.Button(sidebar, text=label, font=("Segoe UI", 11), anchor="w", padx=16, pady=13,
                               relief="flat", bd=0, cursor="hand2", activebackground="#26353a", activeforeground="#6ee7d5",
                               command=lambda i=index: self.navigate(i))
            button.pack(fill="x", padx=12, pady=3)
            self.navigation.append(button)
        bottom = tk.Frame(sidebar, bg="#181c23")
        bottom.pack(side="bottom", fill="x", padx=20, pady=24)
        tk.Label(bottom, text="●  Локальное пространство", bg="#181c23", fg="#6ee7d5", font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(bottom, text="Модели · Исследования · Текст", bg="#181c23", fg="#727d8e", font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))
        workspace = ttk.Frame(self, padding=(28, 24, 28, 16))
        workspace.pack(side="left", fill="both", expand=True)
        header = ttk.Frame(workspace)
        header.pack(fill="x", pady=(0, 20))
        titles = ttk.Frame(header)
        titles.pack(side="left")
        self.page_title = tk.StringVar()
        self.page_subtitle = tk.StringVar()
        ttk.Label(titles, textvariable=self.page_title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, textvariable=self.page_subtitle, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(header, text="  DESKTOP / RESEARCH  ", style="Badge.TLabel").pack(side="right", anchor="n", pady=8)
        self.tabs = ttk.Notebook(workspace, style="Workspace.TNotebook")
        self.tabs.pack(fill="both", expand=True)
        chemistry, assistant = ttk.Frame(self.tabs), ttk.Frame(self.tabs)
        self.tabs.add(chemistry, text="ChemAnalyzer")
        self.tabs.add(assistant, text="ИИ-помощник")
        self.build_chemistry(chemistry)
        self.build_assistant(assistant)
        self.status = tk.StringVar(value="Готово. Выберите режим работы.")
        ttk.Separator(workspace).pack(fill="x", pady=(12, 8))
        ttk.Label(workspace, textvariable=self.status, style="Muted.TLabel", wraplength=780).pack(fill="x")
        self.navigate(0)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.pump)

    def setup_theme(self):
        self.option_add("*Text.background", "#181e26")
        self.option_add("*Text.foreground", "#dbe4ee")
        self.option_add("*Text.insertBackground", "#6ee7d5")
        self.option_add("*Text.selectBackground", "#245950")
        self.option_add("*Text.relief", "flat")
        self.option_add("*Text.borderWidth", 0)
        self.option_add("*Text.padX", 18)
        self.option_add("*Text.padY", 16)
        self.option_add("*TCombobox*Listbox.background", "#232b36")
        self.option_add("*TCombobox*Listbox.foreground", "#edf3fa")
        self.option_add("*TCombobox*Listbox.selectBackground", "#315b59")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#111419", foreground="#dbe4ee", bordercolor="#303844", lightcolor="#303844", darkcolor="#303844", font=("Segoe UI", 10))
        style.configure("TFrame", background="#111419")
        style.configure("TLabel", background="#111419", foreground="#dbe4ee", padding=0)
        style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"), foreground="#f2f6fc")
        style.configure("Muted.TLabel", foreground="#8e9bad", font=("Segoe UI", 9))
        style.configure("Badge.TLabel", foreground="#6ee7d5", background="#203330", padding=(10, 7), font=("Segoe UI", 8, "bold"))
        style.configure("TButton", background="#252d38", foreground="#dbe4ee", padding=(13, 10), borderwidth=0, focusthickness=0)
        style.map("TButton", background=[("active", "#354253"), ("disabled", "#1c222b")], foreground=[("disabled", "#687383")])
        style.configure("Accent.TButton", background="#64dfc7", foreground="#0c2521", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#8cebd9")], foreground=[("active", "#0c2521")])
        for widget in ("TEntry", "TCombobox"):
            style.configure(widget, fieldbackground="#202732", foreground="#e8eef7", padding=9, borderwidth=1, arrowcolor="#8e9bad", insertcolor="#6ee7d5")
            style.map(widget, fieldbackground=[("readonly", "#202732")], foreground=[("readonly", "#e8eef7")], selectbackground=[("!disabled", "#315b59")])
        style.configure("TSeparator", background="#29313d")
        style.configure("Vertical.TScrollbar", background="#354252", troughcolor="#181e26", arrowcolor="#8e9bad", bordercolor="#181e26", lightcolor="#354252", darkcolor="#354252", width=12)
        style.configure("Workspace.TNotebook", background="#111419", borderwidth=0, tabmargins=0)
        style.layout("Workspace.TNotebook.Tab", [])

    def navigate(self, index):
        self.tabs.select(index)
        self.page_title.set(("Лаборатория моделей", "Ваш ИИ-помощник")[index])
        self.page_subtitle.set(("От экспериментальных данных — к проверяемому прогнозу", "Обсуждайте идеи, работайте с текстом и планируйте задачи")[index])
        for i, button in enumerate(self.navigation):
            button.configure(bg="#233b3a" if i == index else "#181c23", fg="#79e6d2" if i == index else "#919eaf")

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
        ttk.Button(row, text="▶  Запустить движок", style="Accent.TButton", command=self.start_chemistry).pack(side="left")
        ttk.Button(row, text="Обновить список", command=self.refresh).pack(side="left", padx=6)
        self.task = tk.StringVar()
        ttk.Label(frame, text="01  /  ДАННЫЕ И ОБУЧЕНИЕ", style="Muted.TLabel").pack(anchor="w", pady=(22, 10))
        ttk.Label(frame, text="Исследовательская задача").pack(anchor="w", pady=(0, 6))
        self.task_box = ttk.Combobox(frame, textvariable=self.task, state="readonly")
        self.task_box.pack(fill="x")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=8)
        ttk.Button(row, text="Демонстрация FreeSolv", command=self.demo).pack(side="left")
        ttk.Button(row, text="Импорт задачи / CSV", command=self.import_task).pack(side="left", padx=5)
        ttk.Button(row, text="Обучить", style="Accent.TButton", command=self.train).pack(side="left")
        ttk.Button(row, text="Отменить", command=self.cancel).pack(side="left", padx=5)
        self.model = tk.StringVar()
        ttk.Label(frame, text="02  /  ПРОГНОЗ", style="Muted.TLabel").pack(anchor="w", pady=(14, 8))
        ttk.Label(frame, text="Модель для исследовательского прогноза").pack(anchor="w", pady=(0, 6))
        self.model_box = ttk.Combobox(frame, textvariable=self.model, state="readonly")
        self.model_box.pack(fill="x")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=8)
        self.smiles = tk.StringVar(value="CCO")
        ttk.Entry(row, textvariable=self.smiles).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Проверить прогноз", command=self.predict).pack(side="left", padx=5)
        ttk.Label(frame, text="РЕЗУЛЬТАТЫ И ЖУРНАЛ", style="Muted.TLabel").pack(anchor="w", pady=(14, 8))
        self.output = self.text_panel(frame, font=("Consolas", 10))
        self.output.insert("end", "⌬  Здесь начинается исследование\n\nЗапустите движок и выберите экспериментальный датасет.\nРезультаты обучения, метрики и прогноз появятся в этой панели.")
        self.output.configure(state="disabled")
        ttk.Label(frame, text="Исследовательский режим · Прогнозы требуют экспериментальной проверки", style="Muted.TLabel", wraplength=780).pack(anchor="w", pady=(10, 0))

    def text_panel(self, parent, **options):
        options.setdefault("height", 8)
        panel = tk.Frame(parent, bg="#181e26", highlightbackground="#2a3441", highlightthickness=1)
        panel.pack(fill="both", expand=True)
        text = tk.Text(panel, wrap="word", **options)
        scroll = ttk.Scrollbar(panel, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        return text

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
        ttk.Label(frame, text="ПОДКЛЮЧЕНИЕ К МОДЕЛИ", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(frame, text="Ollama · локальный помощник", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Запустите Ollama и выберите установленную модель. Подключение: localhost:11434.", style="Muted.TLabel", wraplength=780).pack(anchor="w", pady=(5, 4))
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=8)
        self.profile = ttk.Combobox(row, state="readonly", values=["Универсальный помощник", "Работа с текстом", "Планировщик задач"])
        self.profile.current(0)
        self.profile.pack(side="left")
        self.llm = ttk.Combobox(row)
        self.llm.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row, text="Найти модели", command=lambda: self.work(ollama_models, self.set_models)).pack(side="left")
        self.conversation = self.text_panel(frame, font=("Segoe UI", 11))
        self.conversation.insert("end", "✦  Чем займёмся сегодня?\n\nВыберите профиль: универсальная помощь, работа с текстом\nили планирование задач. Затем подключите локальную модель.")
        self.conversation.configure(state="disabled")
        self.prompt = tk.Text(frame, height=5, wrap="word", font=("Segoe UI", 10))
        self.prompt.pack(fill="x", pady=8)
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Button(row, text="Отправить  ↗", style="Accent.TButton", command=self.send).pack(side="left")
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
