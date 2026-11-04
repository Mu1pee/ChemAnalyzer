# AI Research Lab — руководство

Агент выключен по умолчанию. Обычные функции ChemAnalyzer работают без него.
В backend-окружение или пользовательский .env добавьте
`CHEMANALYZER_RESEARCH_ENABLED=1`, затем перезапустите приложение.
Для разработки установите `backend/requirements.txt` в существующее окружение.

1. Откройте AI Research Lab и «Создать исследовательскую задачу».
   Готовая конфигурация FreeSolv предназначена для первой демонстрации.
2. Выберите задачу, посмотрите источники, нажмите «Импорт FreeSolv».
   Требуется интернет. Источник и LICENSE загружаются по фиксированной Git-версии.
3. «Подготовить данные» сохраняет все исключения и преобразования.
4. «Обучить и оценить» запускает отдельный процесс. История показывает реальные
   стадии; кнопка отмены останавливает процесс. Процент выполнения не выдумывается.
5. Откройте «Результаты и ошибки»: там источники, ошибки строк, кандидаты,
   train/validation/test indices, test и baseline. Подробные файлы остаются локально.
6. «Исследовательский прогноз» показывает status и область применимости.
   Сходство не является вероятностью активности; прогноз не является экспериментом.
7. Рецензию сохраняют только после независимой проверки. Для утверждения
   требуется отдельно отметить подтверждение и нажать кнопку выбранной модели.
   Это меняет исследовательский реестр и не заменяет существующую COX-2 модель.

## Локальный CSV

Выберите CSV с `smiles,value` и отдельный provenance JSON. Один файл должен
содержать один endpoint, единицы и сопоставимый экспериментальный контекст.
Операции преобразования единиц не выполняются автоматически. Поля:

```json
{
  "source_url": "https://publisher.example/data.csv",
  "doi": "10.1234/example",
  "license": "CC-BY-4.0",
  "license_url": "https://publisher.example/license",
  "source_version": "v1",
  "retrieved_at": "2026-11-04T12:00:00Z",
  "endpoint": "your_endpoint",
  "units": "your_units",
  "context": "Exact assay, organism, dose, time, controls and protocol",
  "experimental": true,
  "curator": "Your name"
}
```

Пример — контракт метаданных, не реальный источник. Лицензия и происхождение
проверяются куратором. Поддержаны CC-BY-4.0, CC0-1.0, CC-BY-SA-4.0, PDDL-1.0;
другие лицензии требуют отдельной реализации проверки.
Соли/смеси отклоняются для ручной обработки; стереохимия сохраняется. Одинаковые
структуры с разными метками исключаются целиком, а не усредняются молча.

## CLI (из backend)

```powershell
.\.venv\Scripts\python.exe -X utf8 -m app.ai_research_agent.cli demo
.\.venv\Scripts\python.exe -X utf8 -m app.ai_research_agent.cli list
.\.venv\Scripts\python.exe -X utf8 -m app.ai_research_agent.cli create --config task.json
.\.venv\Scripts\python.exe -X utf8 -m app.ai_research_agent.cli import TASK_ID --csv data.csv --provenance provenance.json
.\.venv\Scripts\python.exe -X utf8 -m app.ai_research_agent.cli prepare TASK_ID
.\.venv\Scripts\python.exe -X utf8 -m app.ai_research_agent.cli run TASK_ID
.\.venv\Scripts\python.exe -X utf8 -m app.ai_research_agent.cli predict MODEL_ID --smiles CCO
```

Ctrl+C отменяет CLI-задачу. `--root` задаёт отдельное исследовательское хранилище.
После сбоя создайте новый запуск той же задачи; исходные данные сохраняются.
Без интернета можно использовать уже импортированный CSV.

## Расписание

Локальный API `POST /api/research/schedules` принимает `task_id`, `enabled`,
`interval_seconds` (минимум 3600), `check_freesolv` и необязательный
`approved_dataset_sha256`. Передайте SHA256 только после утверждения конкретных
данных для обучения. `GET /api/research/schedules` показывает результаты проверок.
Планировщик работает только пока включён backend; это не служба Windows.
Новый файл требует нового явного разрешения. Расписание не активирует модели.

Результаты и ограничения первого эксперимента — MODEL_VALIDATION_REPORT.md;
архитектура и список следующего этапа — AI_AGENT_ARCHITECTURE.md.
