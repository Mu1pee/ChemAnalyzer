# ChemAnalyzer 3.2.1

Исследовательская поставка 3.2.1 включает QSAR-модель человеческого COX-2 по IC50 из ChEMBL 37: 2776 уникальных соединений, scaffold CV ROC-AUC 0.7867, MCC 0.4160. Это исследовательская оценка без внешней валидации. Модель поставляется отдельно от пользовательских файлов и загружается автоматически из ресурсов приложения. Подробности и ограничения: [QSAR_VALIDATION_3.2.1.md](docs/QSAR_VALIDATION_3.2.1.md).

**ChemAnalyzer** — настольное приложение для рисования и анализа химических структур. В проект входят Ketcher, React/TypeScript, Electron, FastAPI и RDKit.

## Возможности

- каталог биоактивности: фармакология, ADMET, научный анализ и базы данных; поиск и статусы каждого направления;
- переходы из каталога к расчётам и отдельным задачам AI Research Lab; экспорт реестра в JSON;

- 2D-рисование химических структур через Ketcher;
- расчёт молекулярной формулы, массы, LogP, TPSA, HBD/HBA, колец, связей и других дескрипторов с RDKit;
- идентификация через PubChem с разделением точного совпадения, совпадения по связности и похожих соединений;
- Drug-likeness и ADME-эвристики, BOILED-Egg, ChEMBL, локальные fingerprints/similarity и 3D-конформер;
- история, темы и экспорт SMILES/JSON/CSV/SVG/PNG/PDF;
- Electron desktop-оболочка и сборка Windows installer/portable.

## Быстрый запуск разработки (Windows)

### AI Research Lab

Опциональный исследовательский агент выполняет импорт экспериментального CSV,
RDKit-подготовку, обучение, scaffold-оценку и сохранение моделей в отдельный реестр.
Первый проверенный цикл — FreeSolv (642 молекулы); модели остаются experimental.
Включение: `CHEMANALYZER_RESEARCH_ENABLED=1` в окружении backend с перезапуском.
Обычные функции работают при выключенном агенте.
См. [руководство](AI_AGENT_USER_GUIDE.md), [архитектуру и ограничения](AI_AGENT_ARCHITECTURE.md),
[аудит](AI_AGENT_AUDIT.md), [данные](DATA_SOURCES.md) и [проверки](AI_AGENT_TEST_REPORT.md).

### Окружение приложения

Требования: Windows 10/11 x64, Node.js 24.20+, Python 3.12 x64 и интернет для установки зависимостей.

1. В корне проекта:

```powershell
npm install
```

2. В первом PowerShell настройте backend для разработки:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..
```

3. Задайте путь к Python из backend окружения и запустите dev desktop:

```powershell
$env:CHEMANALYZER_PYTHON = (Resolve-Path ".\backend\.venv\Scripts\python.exe").Path
npm run dev
```

Скрипт сам запускает Vite и Electron. Перед dev/build Ketcher-ресурсы копируются автоматически.

## Сборка Windows

Из корня проекта запустите:

```powershell
.\scripts\build-windows.ps1
```

Или выполните вручную:

```powershell
npm install
npm run dist:win
```

Результаты будут в `dist/`:

- `ChemAnalyzer-Setup-3.2.0.exe` — установщик NSIS;
- `ChemAnalyzer-Portable-3.2.0.exe` — portable-сборка.

**Важно:** ZIP содержит исходный проект и скрипты сборки, а не уже собранный Windows EXE. После сборки обязательно запустите тесты и проверьте Ketcher на чистой Windows без Python/Node.js.

## Проверки

```powershell
npm run test:electron
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\selftest.py
```

Frontend production build выполняется через `npm run build` из корня; внутренний `prebuild` копирует ресурсы Ketcher и затем запускает TypeScript/Vite build.

## Ограничения

- Основные дескрипторы RDKit рассчитываются локально. PubChem и ChEMBL требуют интернета.
- QSAR показывается только при наличии обученных моделей; similarity не является доказательством активности.
- 3D-конформер — вычисленная геометрия, а не экспериментально установленная структура.
- Drug-likeness / ADME — модели и эвристики, не медицинское заключение.
- Не все варианты сборки/внешние сервисы подтверждены в каждой среде; перед распространением нужен тест Windows installer.

## Документация

- `docs/BIOACTIVITY_WORKSPACE.md` — новый каталог, проверенные функции и результаты обучения агента.

- `DESKTOP_BUILD_GUIDE.md` — полная инструкция сборки и приёмки.
- `CHANGES.md` — журнал версий.
- `LICENSE_NOTICES.md` — уведомления о лицензиях и источниках.


## ПК «Антидот-Прогноз» (3.2.0)

Добавлен отдельный модуль для разработки endpoint-specific систем прогнозирования:
- антидотная активность;
- рострегулирующая активность химических соединений.

Это **каркас научного модуля, а не готовая универсальная модель**. В поставке нет обученных моделей и экспериментального набора данных, поэтому по умолчанию приложение корректно показывает «Модель не обучена». Оно не выдаёт синтетические прогнозы.

Шаблоны CSV и правила подготовки данных находятся в `backend/training/specialized_data/README.md`. После добавления прослеживаемых экспериментальных результатов обучить модели можно из папки `backend`:

```powershell
Push-Location backend
$modelsDir = Join-Path $env:APPDATA "ChemAnalyzer\models\specialized_activity"
python -m training.train_specialized --models-dir $modelsDir
Pop-Location
```

Для обучения обеих областей используйте `--domain all` (по умолчанию). В данных требуется строго определить endpoint и контекст опыта; недостающие измерения нельзя размечать как неактивные. Модель публикуется только после проверки объёма выборки и scaffold-based cross-validation. Эти результаты не являются медицинской, токсикологической или агрономической рекомендацией.
