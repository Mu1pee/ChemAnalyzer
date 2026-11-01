"""Настройки обучения QSAR-моделей на данных ChEMBL."""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "training" / "data"
MODELS_DIR = BACKEND_DIR / "models"

# Соединение считается активным при pChEMBL >= порога (6.0 = IC50/Ki <= 1 мкМ).
ACTIVE_PCHEMBL = 6.0

# Тип измерений, из которых берётся pChEMBL.
ACTIVITY_TYPES = "IC50,Ki,Kd,EC50"

# Максимум записей активности на одну мишень (защита от гигантских выгрузок).
MAX_RECORDS_PER_TARGET = 30000

# (ChEMBL ID, короткое название, фрагмент ожидаемого названия в ChEMBL).
# Фрагмент нужен для защиты от опечатки в ID: перед загрузкой скрипт
# сверяет реальное название мишени в ChEMBL и пропускает несовпадения.
TARGETS: list[tuple[str, str, str]] = [
    ("CHEMBL230", "COX-2", "cyclooxygenase-2"),
    ("CHEMBL221", "COX-1", "cyclooxygenase-1"),
    ("CHEMBL240", "hERG (кардиотоксичность)", "herg"),
    ("CHEMBL203", "EGFR", "epidermal growth factor"),
    ("CHEMBL1824", "HER2", "erbb-2"),
    ("CHEMBL279", "VEGFR2", "vascular endothelial growth factor receptor 2"),
    ("CHEMBL1862", "ABL1", "abl"),
    ("CHEMBL5145", "BRAF", "b-raf"),
    ("CHEMBL2971", "JAK2", "jak2"),
    ("CHEMBL4005", "PI3Kα", "p110-alpha"),
    ("CHEMBL204", "Тромбин", "thrombin"),
    ("CHEMBL244", "Фактор Xa", "factor x"),
    ("CHEMBL205", "Карбоангидраза II", "carbonic anhydrase ii"),
    ("CHEMBL220", "Ацетилхолинэстераза", "acetylcholinesterase"),
    ("CHEMBL4822", "BACE1", "beta-secretase"),
    ("CHEMBL1827", "ФДЭ-5", "phosphodiesterase 5a"),
    ("CHEMBL217", "Дофамин D2", "dopamine d2"),
    ("CHEMBL234", "Дофамин D3", "dopamine d3"),
    ("CHEMBL214", "Серотонин 5-HT1A", "5-ht1a"),
    ("CHEMBL224", "Серотонин 5-HT2A", "5-ht2a"),
    ("CHEMBL228", "SERT (транспортёр серотонина)", "serotonin transporter"),
    ("CHEMBL222", "NET (транспортёр норадреналина)", "norepinephrine transporter"),
    ("CHEMBL251", "Аденозин A2A", "adenosine a2a"),
    ("CHEMBL233", "μ-опиоидный рецептор", "mu opioid"),
    ("CHEMBL210", "β2-адренорецептор", "beta-2 adrenergic"),
    ("CHEMBL216", "Мускариновый M1", "muscarinic acetylcholine receptor m1"),
    ("CHEMBL231", "Гистамин H1", "histamine h1"),
    ("CHEMBL2039", "МАО-B", "monoamine oxidase b"),
    ("CHEMBL1951", "МАО-A", "monoamine oxidase a"),
]

# Критерии приёмки модели (см. qsar_core.quality_gate).
MIN_AUC = 0.75
MIN_MCC = 0.25
MIN_PER_CLASS = 30
