# ChemAnalyzer AI Research Agent: аудит 2026-11-04

Исходная ветка: `feature/windows-desktop-stabilization`; рабочее дерево чистое.
Работа агента ведётся в `feature/ai-research-agent`. Пользовательские данные и
локальные веса не включаются в Git. Существующие функции сохраняются.

## Карта проекта

- `backend/app/main.py`: FastAPI, localhost/TrustedHost в desktop; роутеры
  molecules, structure, assistant. `config.py` выбирает пользовательскую папку.
- `backend/app/chemistry`: RDKit-дескрипторы, стандартизация, fingerprints,
  QSAR, ADME, similarity-профиль и специализированные активности.
- `backend/training/{fetch_data,train,train_specialized}.py`: ChEMBL и локальные
  CSV, scaffold CV, Y-randomization, quality gates. В общем QSAR конфигурация
  объединяет IC50/Ki/Kd/EC50; эти endpoint нельзя автоматически переносить в
  новые задачи как взаимозаменяемые экспериментальные измерения.
- `frontend/src`: React 19 / TypeScript / Vite; вкладки в ResultsPanel.tsx.
- `electron`: main, backend supervisor, preload, security, store; есть Node tests.
- `backend/chemanalyzer_server.py`: localhost uvicorn, freeze_support.
- `backend/chemanalyzer-backend.spec`, `scripts/build-*.ps1`, package.json,
  `.github/workflows/build-windows.yml`: PyInstaller onedir + Electron NSIS/portable.
- `backend/tests`: API, химия, ADME, PubChem, безопасность и обучение.
- `backend/training/specialized_data`: шаблоны/профили, не обучающий датасет.

## Что действительно существует

Локально обнаружены `backend/models/CHEMBL230.joblib`, manifest и training_report.
Манифест описывает COX-2: 1989 молекул, scaffold CV ROC-AUC 0.7739,
PR-AUC 0.8242, MCC 0.3969, Y-randomization AUC 0.5017. Это сведения локального
артефакта, не независимая повторная валидация. Веса исключены из Git.
Других локальных весов при аудите не обнаружено.

`activity.py`: сходство Morgan/Tanimoto с reference_drugs, эвристический перенос
активностей, не обученная экспериментальная модель. `qsar.py` загружает реальные
joblib при наличии manifest, иначе явно сообщает not_trained.
`specialized_activity.py` сохраняет существующий «Антидот-Прогноз», поддерживает
контекстные bundles; локальных весов для него нет. Исследовательские профили
Arabidopsis и APAP имеют status not_trained; ранее найденные публикации не
являются автоматически пригодными обучающими данными.

`adme.py/adme_calc.py`: RDKit, Crippen, ESOL и опубликованные расчётные правила;
это вычисления/эмпирические оценки, не новые обученные ADMET-модели. P-gp/CYP
явно не рассчитываются. services_placeholder.txt — placeholder, не ML-сервис.
LLM assistant — объяснения, не источник экспериментальных меток.

## Решение для первого цикла

Отдельный opt-in пакет `app/ai_research_agent`, отдельное хранилище, отдельные
API/CLI/UI. FreeSolv experimental hydration free energy (kcal/mol), без
использования GAFF-расчётов как меток. Версия Git источника, LICENSE, исходные
байты и SHA256 сохраняются. Новые модели experimental; старые manifests не
изменяются. Внутренние holdout/CV не означают научной валидации.

Полный autonomous literature mining, произвольные ADMET endpoints и допуск
антидотного обучения требуют следующих проверенных этапов. Их наличие не
должно имитироваться пустыми прогнозами или фиктивным прогрессом.
