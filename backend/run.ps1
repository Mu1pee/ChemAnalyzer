$ErrorActionPreference = "Stop"

if (!(Test-Path ".\venv\Scripts\python.exe")) {
    py -3.12 -m venv venv
}

.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
