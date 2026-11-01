# Обучение QSAR-моделей на данных ChEMBL (запускать из папки backend).
# Нужен интернет (загрузка) и несколько десятков минут.
$ErrorActionPreference = "Stop"

if (!(Test-Path ".\venv\Scripts\python.exe")) {
    try { py -3.12 -m venv venv } catch { }
    if (!(Test-Path ".\venv\Scripts\python.exe")) { python -m venv venv }
}

.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m training.fetch_data
.\venv\Scripts\python.exe -m training.train

Write-Host ""
Write-Host "Готово. Перезапустите backend, чтобы он подхватил модели."
