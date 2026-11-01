$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "==> Проверка окружения ChemAnalyzer" -ForegroundColor Cyan
$nodeVersion = (& node --version).Trim()
if ($LASTEXITCODE -ne 0) { throw "Node.js не найден. Установите Node.js 24.20.0 или новее." }
if ($nodeVersion -notmatch '^v(\d+)\.(\d+)\.(\d+)') {
    throw "Не удалось разобрать версию Node.js: $nodeVersion"
}
$major = [int]$Matches[1]; $minor = [int]$Matches[2]
if (($major -lt 24) -or ($major -eq 24 -and $minor -lt 20)) {
    throw "Требуется Node.js 24.20.0 или новее; найден $nodeVersion"
}

$pythonVersion = (& py -3.12 --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -notmatch 'Python 3\.12\.') {
    throw "Требуется Python 3.12 x64. Текущий результат: $pythonVersion"
}

Write-Host "Node.js: $nodeVersion" -ForegroundColor Green
Write-Host "Python:  $pythonVersion" -ForegroundColor Green
Write-Host "==> Установка root-зависимостей" -ForegroundColor Cyan
npm install
if ($LASTEXITCODE -ne 0) { throw "npm install завершился с ошибкой" }

Write-Host "==> Сборка frontend, Python/RDKit backend и Windows-дистрибутивов" -ForegroundColor Cyan
npm run dist:win
if ($LASTEXITCODE -ne 0) { throw "Сборка ChemAnalyzer не завершилась успешно. Смотрите вывод выше." }

Write-Host "==> Готовые файлы" -ForegroundColor Green
Get-ChildItem (Join-Path (Get-Location) "dist") -Filter "*.exe" | Select-Object FullName, Length
