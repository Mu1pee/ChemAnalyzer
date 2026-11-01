# ChemAnalyzer 3.2.0 — проверка текущего исходного проекта

Дата упаковки: 25 октября 2026.

## Исправления в этой сборке

- Добавлен автоматический копировщик ресурсов Ketcher из `node_modules/ketcher-react/dist` в `frontend/public/ketcher-assets`; он вызывается перед `npm run dev` и `npm run build`.
- В Ketcher задан отдельный путь `/ketcher-assets`.
- Раздел идентификации явно различает точное совпадение и совпадение по связности; последнее показывается как кандидат.
- Контекст Claude и CSV экспорт не представляют запись по связности как подтверждённое название/CID/InChIKey; кандидатские данные вынесены в отдельные поля.
- Добавлен `electron-builder` как сборочная зависимость, требования Node.js выровнены на 24.20.0+.
- Добавлен `scripts/build-windows.ps1` и workflow GitHub Actions для сборки Windows.

## Проверки, выполненные при создании архива

- Backend `pytest`: **102 passed**.
- Electron tests: **17 passed**.
- `backend/scripts/selftest.py`: **ALL CHECKS PASSED**.
- Smoke-test скрипта копирования ресурсов Ketcher: пройден на временной фикстуре.
- Синтаксис и JSON-конфигурации проверены.

## Что не подтверждено

- `npm install` и TypeScript/Vite production build не выполнялись: здесь доступен Node.js 22.16.0, а проект требует Node.js 24.20.0+; пакеты Ketcher отсутствуют в этой среде.
- Windows PyInstaller build и Electron installer не запускались в этой среде.
- Поэтому этот архив содержит исправленный **исходный проект**, а не готовый/подтверждённый `ChemAnalyzer.exe`.

## Сборка Windows

Из распакованной папки проекта, где лежит корневой `package.json`, в PowerShell:

```powershell
.\scripts\build-windows.ps1
```

Скрипт проверит версии Node/Python, установит зависимости и запустит полный pipeline. Ожидаемые артефакты в `dist/`:

- `ChemAnalyzer-Setup-3.2.0.exe`
- `ChemAnalyzer-Portable-3.2.0.exe`

Перед распространением приложение следует проверить на Windows-компьютере без отдельно установленного Python и Node.js.


## Дополнение 3.2.0 — ПК «Антидот-Прогноз»

Добавлена вкладка `Антидот-Прогноз`, API `POST /api/molecules/specialized-activity`, отдельный загрузчик endpoint-моделей, проверка применимости по сходству Tanimoto и скрипт обучения на пользовательских экспериментальных CSV. Поставляемые CSV — пустые шаблоны; предварительно обученных антидотных или рострегулирующих моделей в архиве нет. Поэтому прогноз появляется только после подготовки данных, обучения и прохождения quality gates.


## v3.2.0 — проверка модуля «Антидот-Прогноз» (2026-10-29)

Проверено в доступной среде:
- `python -m compileall -q backend/app backend/training backend/tests` — успешно.
- `pytest tests/test_specialized_activity.py tests/test_contract.py tests/test_security.py tests/test_pubchem.py` — 74 passed.
- Electron tests (`node --test electron/tests/backend.test.js electron/tests/security.test.js electron/tests/store.test.js`) — 17 passed.
- `backend/scripts/selftest.py` — все встроенные проверки прошли.
- TypeScript/TSX parser — 37 файлов, 0 синтаксических ошибок.
- Endpoint `/api/molecules/specialized-activity`: этанол возвращает два статуса `not_trained`, invalid SMILES — HTTP 400.
- Обучение на пустых CSV-шаблонах корректно отклоняется и не создаёт модели.

Не подтверждено:
- полный `pytest` набор в этой среде превысил timeout на длительных QSAR-тестах; целевые тесты выше выполнены;
- TypeScript/Vite production build не выполнен, потому что зависимости Frontend не установлены, а текущий Node.js 22.16 ниже требования проекта 24.20+;
- Windows PyInstaller/Electron installer и запуск на чистой Windows не выполнялись.
- В поставке нет обученных моделей Антидот-Прогноз; для настоящих оценок нужны экспериментальные, endpoint-specific и прослеживаемые данные.
