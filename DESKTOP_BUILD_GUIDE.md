# Сборка ChemAnalyzer.exe для Windows

Результат: установщик `dist\ChemAnalyzer-Setup-<версия>.exe` (NSIS, ярлыки на
рабочем столе и в меню «Пуск») и `dist\ChemAnalyzer-Portable-<версия>.exe`.

> **Статус проверки.** Код сборки подготовлен, но **полная сборка и запуск
> `.exe` на Windows автором не выполнялись** (окружение разработки без
> Windows, npm и интернета). Проверены: логика запуска/остановки backend и
> безопасность (`npm run test:electron`), Python-логика и тесты, типы
> TypeScript. Шаги ниже и раздел «Проверка» нужно пройти у вас; найденные
> ошибки — в раздел «Если что-то не работает».

## 1. Что понадобится (на машине сборки)

| Инструмент | Версия | Зачем |
|---|---|---|
| Windows 10/11 x64 | — | `.exe` собирается под Windows |
| Node.js | ≥ 24.20.0 | Ketcher требует Node 24.20+; Electron, electron-builder |
| Python | **3.12 x64** | RDKit/scikit-learn публикуют колёса не для всех версий |
| Интернет | — | пакеты npm и pip (один раз) |
| Свободное место | ~5 ГБ | node_modules, venv, PyInstaller, установщик |

Проверка: `node --version` (не ниже v24.20.0), `py -3.12 --version`.

## 2. Сборка по шагам

Рекомендуемый запуск одной командой: ` .\scripts\build-windows.ps1 ` из корня проекта. Скрипт проверяет версии Node/Python, устанавливает корневые зависимости и вызывает полный pipeline.

Перед `dev` и `build` frontend автоматически копирует содержимое `frontend\node_modules\ketcher-react\dist` в `frontend\public\ketcher-assets` через `frontend\scripts\copy-ketcher-assets.mjs`. Если ресурсы пакета не найдены, скрипт останавливается с пояснением.

Выполняйте из корня проекта (там, где лежит `package.json`).

```powershell
# 0) Установка зависимостей Electron
npm install

# 1) Frontend -> frontend\dist
npm run build

# 2) Backend (Python + RDKit) -> build\backend\chemanalyzer-backend\
npm run build:backend

# 3) Установщик -> dist\
npx electron-builder --win --x64
```

Одной командой: `npm run dist:win` (шаги 1–3).

Что делает `npm run build:backend` (`scripts\build-backend.ps1`):
1. создаёт `backend\.venv-build` и ставит `requirements-build.txt`;
2. запускает PyInstaller по `chemanalyzer-backend.spec` (режим onedir);
3. **проверяет результат**: запускает собранный `chemanalyzer-backend.exe` на
   случайном порту, ждёт `/health` и анализирует аспирин (ожидает `C9H8O4`).
   Если проверка не прошла, скрипт завершится с ошибкой — установщик не
   собирайте.

## 3. Иконка

Иконка нарисована скриптом и лежит в `assets\icon.ico` / `icon.png`. Чтобы
изменить дизайн: правьте `scripts\make_icon.py` и запустите `npm run icon`
(нужен `pip install pillow`).

## 4. Проверка перед выдачей

**Обязательно на «чистой» Windows** (виртуальная машина или другой компьютер,
где нет Python, Node.js и каталога проекта) — на вашей рабочей машине всё
может запускаться из-за установленных инструментов.

1. Установите `ChemAnalyzer-Setup-*.exe`, запустите с рабочего стола.
   Появляется окно-заставка, затем главное окно (первый запуск может занять до
   минуты: загрузка RDKit/scikit-learn).
2. В Диспетчере задач виден `ChemAnalyzer.exe` и `chemanalyzer-backend.exe`.
3. **Редактор.** Нарисуйте кольцо, добавьте атом, двойную связь; проверьте
   Undo/Redo (Ctrl+Z / Ctrl+Y), очистку, импорт SMILES (`CCO`), примеры.
4. **ADME**: введите `C1CCCCCC1` (циклогептан), откройте вкладку «ADME».
   Ожидается (как на сайте SwissADME): жёлток содержит точку, ЖКТ — «низкое», ГЭБ — «да»,
   Ghose — 2 нарушения (MW<160, MR<40), Muegge — 2 нарушения (MW<200, гетероатомов<2).
   ESOL и Log Kp у вас будут другими, чем на сайте (там XLOGP3) — это нормально.
5. **Анализ трёх молекул** (кнопка «Анализировать» или Ctrl+Enter):

   | Молекула | SMILES | Ожидается |
   |---|---|---|
   | Этанол | `CCO` | C2H6O, MW ≈ 46.07, TPSA ≈ 20.23, HBD 1 |
   | Бензол | `c1ccccc1` | C6H6, MW ≈ 78.11, TPSA 0, HBD 0, HBA 0 |
   | Аспирин | `CC(=O)Oc1ccccc1C(=O)O` | C9H8O4, MW ≈ 180.16, TPSA ≈ 63.6, HBD 1 |

6. **Без интернета** (отключите сеть): анализ работает, на вкладке
   «Идентификация» — «PubChem недоступен — локальный анализ выполнен», на
   «ChEMBL» — сообщение о недоступности.
7. **QSAR**: на вкладке «Активность» — «QSAR-модель не обучена».
8. **3D**: «Построить 3D», вращение, масштаб, «Перестроить 3D».
9. **Экспорт**: SMILES, JSON, CSV, SVG, PNG, PDF (открыть PDF: кириллица,
   структура, таблицы на месте).
10. Закройте окно: в Диспетчере задач **не должно остаться**
   `chemanalyzer-backend.exe`.
11. Запустите второй экземпляр — должно сфокусироваться уже открытое окно.

Автоматическая часть (на машине сборки):

```powershell
npm run test:electron
cd backend ; .\.venv\Scripts\python scripts\selftest.py
```

## 5. Папка данных пользователя

`%APPDATA%\ChemAnalyzer\` (меню Settings → «Открыть папку данных»):

| Путь | Назначение |
|---|---|
| `.env` | `ANTHROPIC_API_KEY=...` для ассистента (создаётся пустым при первом запуске) |
| `models\` | обученные QSAR-модели (`manifest.json`, `*.joblib`) |
| `state\history.json`, `state\theme.json` | история анализов и выбранная тема (хранятся в файлах, а не в localStorage: порт backend при каждом запуске случайный, а значит и origin новый) |
| `logs\backend.log` | журнал backend (ключи в него не пишутся) |

При удалении программы эта папка не стирается (`deleteAppDataOnUninstall: false`).
Каталог установки (`resources\`) пользователю недоступен для записи — поэтому
модели и ключ хранятся отдельно.

## 6. Если что-то не работает

**Окно «ChemAnalyzer не запустился».** Откройте `%APPDATA%\ChemAnalyzer\logs\backend.log`.
Частые причины: антивирус заблокировал `chemanalyzer-backend.exe`; не
хватает файлов PyInstaller (см. ниже).

**`ModuleNotFoundError` в логе backend.** Добавьте модуль в `hiddenimports` в
`backend\chemanalyzer-backend.spec` и пересоберите backend.

**Ключевой риск: Ketcher не отображается (пустая область) в собранном
приложении.** Ketcher использует WASM-движок Indigo; Content-Security-Policy
разрешает `'wasm-unsafe-eval'`, но не `'unsafe-eval'`. Если редактор пуст:
1. запустите приложение с переменной окружения `CHEMANALYZER_RELAXED_CSP=1`
   (добавляет `'unsafe-eval'` в CSP);
2. включите DevTools: `CHEMANALYZER_DEVTOOLS=1` и посмотрите ошибки в консоли;
3. если помогло — это нужно закрепить, добавив `'unsafe-eval'` в
   `electron\security.js` (`buildCsp`), осознанно приняв ослабление защиты.
Этот сценарий в упакованном виде **не проверялся**.

**Ketcher не находит статические ресурсы.** Интерфейс раздаёт backend по
`http://127.0.0.1:<порт>/`, `staticResourcesUrl` равен `/`. Не открывайте
собранный `index.html` через `file://`. Если вы ранее правили загрузку
ресурсов Ketcher иначе, сверьте `frontend\src\components\KetcherEditor.tsx`.

**`npm install` падает на electron / electron-builder.** Проверьте доступ к
GitHub (Electron скачивает бинарник) и версию Node (≥ 24). Версии в
`package.json` (`electron ^42`, `electron-builder ^26.8`) подбирались по
документации; при несовместимости поставьте актуальную поддерживаемую.

**PyInstaller: RDKit/scikit-learn не находятся.** Используйте именно Python
3.12 x64 в `backend\.venv-build`; удалите папку и повторите `build:backend`.

**Windows SmartScreen / антивирус.** Неподписанный `.exe` вызывает
предупреждение («Неизвестный издатель»). Для распространения подпишите
установщик сертификатом подписи кода (электронная подпись в
electron-builder: переменные `CSC_LINK`, `CSC_KEY_PASSWORD`). Режим onedir и
отключённый UPX уже снижают число ложных срабатываний.

**Большой размер.** Установщик получается порядка сотен МБ (RDKit, scikit-learn,
scipy, Electron). Это ожидаемо.

**Движок остановился во время работы.** Автоматического перезапуска нет: статус внизу станет «нет связи», а в сообщениях об ошибках будет подсказка открыть `logs\backend.log`. Закройте и снова откройте приложение.

**Порт.** Порт выбирается автоматически; при ошибке запуска (порт успели
занять) делается до трёх попыток с новым портом.

**Режим разработки не запускается.** Задайте `CHEMANALYZER_PYTHON` на python
из `backend\.venv`, убедитесь, что порт 5173 свободен (`strictPort`).

## 7. Обновление версии

Меняйте версию в `package.json` (корень), `frontend\package.json` и
`backend\app\__init__.py`; затем `npm run dist:win`.


## ПК «Антидот-Прогноз»

Для локальных специализированных моделей см. `backend/training/specialized_data/README.md`. Модели размещаются в `%APPDATA%\ChemAnalyzer\models\specialized_activity`. Не копируйте модели без соответствующего `manifest.json`. Если обучающие данные не загружены или качество модели не прошло критерии, вкладка покажет статус, а не выдуманный прогноз.
