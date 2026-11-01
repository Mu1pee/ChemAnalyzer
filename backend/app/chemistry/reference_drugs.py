"""Справочная библиотека известных препаратов с фармакологическими классами.

Используется для прогноза спектра активности по структурному сходству
(метод ближайших соседей). Это НЕ PASS и не обученная QSAR-модель:
библиотека небольшая и расширяется простым добавлением строк в список.

Формат записи: (название, SMILES, [активности]).
Невалидные SMILES при загрузке пропускаются; проверить библиотеку
можно скриптом scripts/validate_reference.py.
"""

# Единые названия активностей (чтобы агрегация по классам работала).
NSAID = "НПВС (противовоспалительное)"
COX = "Ингибитор циклооксигеназы (ЦОГ)"
ANALGESIC = "Анальгетик"
ANTIPYRETIC = "Жаропонижающее"
ANTIPLATELET = "Антиагрегант"
OPIOID = "Агонист опиоидных рецепторов"
CNS_STIM = "Стимулятор ЦНС"
ADENOSINE = "Антагонист аденозиновых рецепторов"
PDE = "Ингибитор фосфодиэстеразы"
ANXIOLYTIC = "Анксиолитик / седативное"
GABA = "Модулятор ГАМК-А рецептора"
ANTICONV = "Противосудорожное"
NA_CHANNEL = "Блокатор натриевых каналов"
ANTIDEP = "Антидепрессант"
SERT = "Ингибитор обратного захвата серотонина"
ANTIPSY = "Антипсихотик"
D2 = "Антагонист дофаминовых рецепторов"
BETA_BLOCK = "Бета-адреноблокатор"
ANTIHYP = "Антигипертензивное"
ANTIARR = "Антиаритмическое"
BETA2 = "Агонист бета-2-адренорецепторов"
BRONCHO = "Бронходилататор"
ACE = "Ингибитор АПФ"
CA_BLOCK = "Блокатор кальциевых каналов"
ARB = "Антагонист рецепторов ангиотензина II"
DIURETIC = "Диуретик"
STATIN = "Ингибитор ГМГ-КоА-редуктазы (статин)"
LIPID = "Гиполипидемическое"
ANTIDIAB = "Антидиабетическое"
ANTICOAG = "Антикоагулянт"
P2Y12 = "Антагонист рецептора P2Y12"
PPI = "Ингибитор протонной помпы"
ULCER = "Противоязвенное"
H2 = "Антагонист H2-гистаминовых рецепторов"
H1 = "Антагонист H1-гистаминовых рецепторов"
ANTIHIST = "Антигистаминное"
PDE5 = "Ингибитор ФДЭ-5"
VASODIL = "Вазодилататор"
GLUCOCORT = "Глюкокортикоид"
ANTIINFL = "Противовоспалительное (стероидное)"
ANTIESTR = "Антиэстроген"
ANTITUMOR = "Противоопухолевое"
ANTIMETAB = "Антиметаболит"
DHFR = "Ингибитор дигидрофолатредуктазы"
KINASE = "Ингибитор протеинкиназ"
ANTIBACT = "Антибактериальное"
FQ = "Ингибитор ДНК-гиразы (фторхинолон)"
BETALACTAM = "β-лактамный антибиотик"
SULFA = "Сульфаниламид"
ANTIPROTOZOAL = "Антипротозойное"
ANTIFUNGAL = "Противогрибковое"
CYP51 = "Ингибитор CYP51 (синтез эргостерола)"
ANTIVIRAL = "Противовирусное"
VIRAL_POL = "Ингибитор вирусной ДНК-полимеразы"
NEURAMIN = "Ингибитор нейраминидазы"
ANTIMALARIAL = "Противомалярийное"
DA_AGONIST = "Агонист дофаминовых рецепторов"
SEROTONIN_AG = "Агонист серотониновых рецепторов"
NICOTINIC = "Агонист никотиновых рецепторов"
ANTIPARK = "Противопаркинсоническое"
MUSC_ANT = "Антагонист мускариновых рецепторов"
LOCAL_ANES = "Местный анестетик"
ANDROGEN = "Андроген"
ESTROGEN = "Эстроген"
STEROID_R = "Агонист стероидных рецепторов"
ANTIOX = "Антиоксидант"
ANTISEPTIC = "Антисептик"
CNS_DEPR = "Депрессант ЦНС"
MELATONIN = "Агонист мелатониновых рецепторов"
HYPNOTIC = "Снотворное"
HT3 = "Антагонист 5-HT3 рецепторов"
ANTIEMETIC = "Противорвотное"

REFERENCE_DRUGS: list[tuple[str, str, list[str]]] = [
    ("Аспирин", "CC(=O)Oc1ccccc1C(=O)O", [NSAID, COX, ANALGESIC, ANTIPYRETIC, ANTIPLATELET]),
    ("Ибупрофен", "CC(C)Cc1ccc(cc1)C(C)C(=O)O", [NSAID, COX, ANALGESIC, ANTIPYRETIC]),
    ("Напроксен", "COc1ccc2cc(ccc2c1)C(C)C(=O)O", [NSAID, COX, ANALGESIC]),
    ("Диклофенак", "OC(=O)Cc1ccccc1Nc1c(Cl)cccc1Cl", [NSAID, COX, ANALGESIC]),
    ("Целекоксиб", "Cc1ccc(cc1)-c1cc(nn1-c1ccc(cc1)S(N)(=O)=O)C(F)(F)F", [NSAID, COX]),
    ("Парацетамол", "CC(=O)Nc1ccc(O)cc1", [ANALGESIC, ANTIPYRETIC]),
    ("Морфин", "CN1CCC23C4C1CC5=C2C(=C(C=C5)O)OC3C(C=C4)O", [OPIOID, ANALGESIC]),
    ("Фентанил", "CCC(=O)N(c1ccccc1)C1CCN(CCc2ccccc2)CC1", [OPIOID, ANALGESIC]),
    ("Кофеин", "Cn1cnc2c1c(=O)n(C)c(=O)n2C", [CNS_STIM, ADENOSINE, PDE]),
    ("Диазепам", "CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21", [ANXIOLYTIC, GABA, ANTICONV]),
    ("Флуоксетин", "CNCCC(Oc1ccc(cc1)C(F)(F)F)c1ccccc1", [ANTIDEP, SERT]),
    ("Амитриптилин", "CN(C)CCC=C1c2ccccc2CCc2ccccc12", [ANTIDEP, SERT, MUSC_ANT]),
    ("Хлорпромазин", "CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc12", [ANTIPSY, D2]),
    ("Галоперидол", "OC1(CCN(CCCC(=O)c2ccc(F)cc2)CC1)c1ccc(Cl)cc1", [ANTIPSY, D2]),
    ("Пропранолол", "CC(C)NCC(O)COc1cccc2ccccc12", [BETA_BLOCK, ANTIHYP, ANTIARR]),
    ("Атенолол", "CC(C)NCC(O)COc1ccc(CC(N)=O)cc1", [BETA_BLOCK, ANTIHYP]),
    ("Сальбутамол", "CC(C)(C)NCC(O)c1ccc(O)c(CO)c1", [BETA2, BRONCHO]),
    ("Каптоприл", "CC(CS)C(=O)N1CCCC1C(O)=O", [ACE, ANTIHYP]),
    ("Лизиноприл", "NCCCCC(NC(CCc1ccccc1)C(O)=O)C(=O)N1CCCC1C(O)=O", [ACE, ANTIHYP]),
    ("Амлодипин", "CCOC(=O)C1=C(COCCN)NC(C)=C(C1c1ccccc1Cl)C(=O)OC", [CA_BLOCK, ANTIHYP, VASODIL]),
    ("Нифедипин", "COC(=O)C1=C(C)NC(C)=C(C1c1ccccc1[N+]([O-])=O)C(=O)OC", [CA_BLOCK, ANTIHYP, VASODIL]),
    ("Верапамил", "COc1ccc(CCN(C)CCCC(C#N)(C(C)C)c2ccc(OC)c(OC)c2)cc1OC", [CA_BLOCK, ANTIARR, ANTIHYP]),
    ("Лозартан", "CCCCc1nc(Cl)c(CO)n1Cc1ccc(cc1)-c1ccccc1-c1nn[nH]n1", [ARB, ANTIHYP]),
    ("Гидрохлортиазид", "NS(=O)(=O)c1cc2c(NCNS2(=O)=O)cc1Cl", [DIURETIC, ANTIHYP]),
    ("Фуросемид", "NS(=O)(=O)c1cc(C(O)=O)c(NCc2ccco2)cc1Cl", [DIURETIC]),
    ("Аторвастатин", "CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC(O)CC(O)CC(O)=O", [STATIN, LIPID]),
    ("Метформин", "CN(C)C(=N)N=C(N)N", [ANTIDIAB]),
    ("Варфарин", "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O", [ANTICOAG]),
    ("Клопидогрел", "COC(=O)C(c1ccccc1Cl)N1CCc2sccc2C1", [ANTIPLATELET, P2Y12]),
    ("Омепразол", "COc1ccc2[nH]c(nc2c1)S(=O)Cc1ncc(C)c(OC)c1C", [PPI, ULCER]),
    ("Ранитидин", "CNC(NCCSCc1ccc(CN(C)C)o1)=C[N+]([O-])=O", [H2, ULCER]),
    ("Дифенгидрамин", "CN(C)CCOC(c1ccccc1)c1ccccc1", [ANTIHIST, H1, MUSC_ANT]),
    ("Лоратадин", "CCOC(=O)N1CCC(=C2c3ccc(Cl)cc3CCc3cccnc23)CC1", [ANTIHIST, H1]),
    ("Цетиризин", "OC(=O)COCCN1CCN(CC1)C(c1ccccc1)c1ccc(Cl)cc1", [ANTIHIST, H1]),
    ("Силденафил", "CCCc1nn(C)c2c1nc([nH]c2=O)-c1cc(ccc1OCC)S(=O)(=O)N1CCN(C)CC1", [PDE5, VASODIL]),
    ("Дексаметазон", "CC1CC2C3CCC4=CC(=O)C=CC4(C)C3(F)C(O)CC2(C)C1(O)C(=O)CO", [GLUCOCORT, ANTIINFL, STEROID_R]),
    ("Преднизолон", "CC12CC(O)C3C(CCC4=CC(=O)C=CC34C)C1CCC2(O)C(=O)CO", [GLUCOCORT, ANTIINFL, STEROID_R]),
    ("Тестостерон", "CC12CCC3C(CCC4=CC(=O)CCC34C)C1CCC2O", [ANDROGEN, STEROID_R]),
    ("Эстрадиол", "CC12CCC3c4ccc(O)cc4CCC3C2CCC1O", [ESTROGEN, STEROID_R]),
    ("Тамоксифен", "CCC(=C(c1ccccc1)c1ccc(OCCN(C)C)cc1)c1ccccc1", [ANTIESTR, ANTITUMOR]),
    ("Метотрексат", "CN(Cc1cnc2nc(N)nc(N)c2n1)c1ccc(cc1)C(=O)NC(CCC(O)=O)C(O)=O", [ANTITUMOR, ANTIMETAB, DHFR]),
    ("5-Фторурацил", "O=c1[nH]cc(F)c(=O)[nH]1", [ANTITUMOR, ANTIMETAB]),
    ("Иматиниб", "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(n1)-c1cccnc1", [ANTITUMOR, KINASE]),
    ("Гефитиниб", "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1", [ANTITUMOR, KINASE]),
    ("Ципрофлоксацин", "OC(=O)C1=CN(C2CC2)c2cc(N3CCNCC3)c(F)cc2C1=O", [ANTIBACT, FQ]),
    ("Бензилпенициллин", "CC1(C)SC2C(NC(=O)Cc3ccccc3)C(=O)N2C1C(O)=O", [ANTIBACT, BETALACTAM]),
    ("Амоксициллин", "CC1(C)SC2C(NC(=O)C(N)c3ccc(O)cc3)C(=O)N2C1C(O)=O", [ANTIBACT, BETALACTAM]),
    ("Сульфаметоксазол", "Cc1cc(NS(=O)(=O)c2ccc(N)cc2)no1", [ANTIBACT, SULFA]),
    ("Триметоприм", "COc1cc(Cc2cnc(N)nc2N)cc(OC)c1OC", [ANTIBACT, DHFR]),
    ("Метронидазол", "Cc1ncc([N+]([O-])=O)n1CCO", [ANTIBACT, ANTIPROTOZOAL]),
    ("Флуконазол", "OC(Cn1cncn1)(Cn1cncn1)c1ccc(F)cc1F", [ANTIFUNGAL, CYP51]),
    ("Ацикловир", "Nc1nc2n(COCCO)cnc2c(=O)[nH]1", [ANTIVIRAL, VIRAL_POL]),
    ("Осельтамивир", "CCC(CC)OC1C=C(CC(NC(C)=O)C1N)C(=O)OCC", [ANTIVIRAL, NEURAMIN]),
    ("Хлорохин", "CCN(CC)CCCC(C)Nc1ccnc2cc(Cl)ccc12", [ANTIMALARIAL, ANTIPROTOZOAL]),
    ("Дофамин", "NCCc1ccc(O)c(O)c1", [DA_AGONIST]),
    ("Серотонин", "NCCc1c[nH]c2ccc(O)cc12", [SEROTONIN_AG]),
    ("Никотин", "CN1CCCC1c1cccnc1", [NICOTINIC, CNS_STIM]),
    ("Леводопа", "NC(Cc1ccc(O)c(O)c1)C(O)=O", [ANTIPARK, DA_AGONIST]),
    ("Карбамазепин", "NC(=O)N1c2ccccc2C=Cc2ccccc12", [ANTICONV, NA_CHANNEL]),
    ("Фенитоин", "O=C1NC(=O)C(N1)(c1ccccc1)c1ccccc1", [ANTICONV, NA_CHANNEL]),
    ("Лидокаин", "CCN(CC)CC(=O)Nc1c(C)cccc1C", [LOCAL_ANES, NA_CHANNEL, ANTIARR]),
    ("Атропин", "CN1C2CCC1CC(C2)OC(=O)C(CO)c1ccccc1", [MUSC_ANT]),
    ("Мелатонин", "COc1ccc2[nH]cc(CCNC(C)=O)c2c1", [MELATONIN, HYPNOTIC]),
    ("Ондансетрон", "Cc1nccn1CC1CCc2c(C1=O)c1ccccc1n2C", [HT3, ANTIEMETIC]),
    ("Кверцетин", "Oc1cc(O)c2c(c1)oc(-c1ccc(O)c(O)c1)c(O)c2=O", [ANTIOX]),
    ("Этанол", "CCO", [ANTISEPTIC, CNS_DEPR]),
]
