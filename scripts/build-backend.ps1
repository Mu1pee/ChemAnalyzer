# Сборка Python-backend (FastAPI + RDKit) в ЕДИНЫЙ каталог без установленного Python.
#   npm run build:backend
# Результат: build\backend\chemanalyzer-backend\chemanalyzer-backend.exe
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$venv = Join-Path $backend ".venv-build"
$py = Join-Path $venv "Scripts\python.exe"
$out = Join-Path $root "build\backend"

Write-Host "==> Виртуальное окружение сборки" -ForegroundColor Cyan
if (!(Test-Path $py)) {
    # RDKit/scikit-learn публикуют колёса не для всех версий Python.
    # Рекомендуется 3.12; запасной вариант — python из PATH.
    # Лаунчера py может не быть: при $ErrorActionPreference = "Stop" это исключение,
    # поэтому оборачиваем в try и переходим на python из PATH.
    try { py -3.12 -m venv $venv 2>$null } catch { }
    if (!(Test-Path $py)) { python -m venv $venv }
    if (!(Test-Path $py)) { throw "Не удалось создать виртуальное окружение. Установите Python 3.12 x64." }
}
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $backend "requirements-build.txt")

Write-Host "==> PyInstaller" -ForegroundColor Cyan
Push-Location $backend
try {
    & $py -m PyInstaller --noconfirm --clean `
        --distpath $out `
        --workpath (Join-Path $root "build\pyinstaller") `
        chemanalyzer-backend.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller завершился с ошибкой" }
} finally { Pop-Location }

$exe = Join-Path $out "chemanalyzer-backend\chemanalyzer-backend.exe"
if (!(Test-Path $exe)) { throw "Не найден $exe" }

Write-Host "==> Проверка: запуск собранного backend и /health" -ForegroundColor Cyan
$port = Get-Random -Minimum 20000 -Maximum 40000
$proc = Start-Process -FilePath $exe -ArgumentList "--port", $port -PassThru -WindowStyle Hidden
try {
    $ok = $false
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 1
        if ($proc.HasExited) { throw "Backend завершился при запуске (код $($proc.ExitCode))" }
        try {
            $r = Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 2
            if ($r.application -eq "ChemAnalyzer") { $ok = $true; break }
        } catch { }
    }
    if (!$ok) { throw "Backend не ответил на /health за 90 с" }

    $body = @{ smiles = "CC(=O)Oc1ccccc1C(=O)O" } | ConvertTo-Json
    $res = Invoke-RestMethod "http://127.0.0.1:$port/api/molecules/analyze" `
        -Method Post -ContentType "application/json" -Body $body
    if ($res.formula -ne "C9H8O4") { throw "Неверная формула аспирина: $($res.formula)" }
    Write-Host "OK: backend запускается, RDKit работает (аспирин: $($res.formula))" -ForegroundColor Green
} finally {
    if (!$proc.HasExited) { taskkill /pid $proc.Id /T /F | Out-Null }
}
