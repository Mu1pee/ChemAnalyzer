import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchConformer,
  fetchProtein,
  fetchTargetProteins,
  proteinDownloadUrl
} from "../api/structure";
import type {
  ChemblResponse,
  ConformerResponse,
  ProteinStructure,
  QsarPrediction
} from "../types/molecule";
import { saveText } from "../lib/exporters";
import MolViewer, { type ViewStyle } from "./MolViewer";

interface Props {
  smiles: string;
  qsar: QsarPrediction[];
  chembl: ChemblResponse | null;
}

interface Candidate {
  id: string;
  name: string;
}

// Кэш конформеров на время сессии: повторное открытие вкладки без пересчёта.
const conformerCache = new Map<string, ConformerResponse>();

function plddtTone(value: number | null): string {
  if (value === null) return "badge-low";
  if (value >= 90) return "badge-high";
  if (value >= 70) return "badge-medium";
  return "badge-low";
}

export default function StructureTab({ smiles, qsar, chembl }: Props) {
  // ---------- малая молекула ----------
  const [conformer, setConformer] = useState<ConformerResponse | null>(
    conformerCache.get(smiles) ?? null
  );
  const [confLoading, setConfLoading] = useState(false);
  const [confError, setConfError] = useState("");
  const [ligandStyle, setLigandStyle] = useState<ViewStyle>("ballstick");

  // Номер последнего запроса: ответ на запрос для прежней молекулы игнорируется.
  const conformerRun = useRef(0);

  // Смена молекулы: показываем сохранённый конформер, иначе ждём нажатия кнопки.
  useEffect(() => {
    conformerRun.current += 1;
    setConformer(conformerCache.get(smiles) ?? null);
    setConfError("");
    setConfLoading(false);
  }, [smiles]);

  async function buildConformer(regenerate: boolean) {
    const run = ++conformerRun.current;
    setConfLoading(true);
    setConfError("");
    try {
      // При перестроении берём новое зерно: RDKit даёт другую стартовую геометрию.
      const seed = regenerate ? Math.floor(Math.random() * 1_000_000) : 42;
      const data = await fetchConformer(smiles, seed);
      conformerCache.set(smiles, data);
      if (run === conformerRun.current) setConformer(data);
    } catch (err) {
      if (run === conformerRun.current) {
        setConfError(
          err instanceof Error ? err.message : "3D-конформация не была построена."
        );
      }
    } finally {
      if (run === conformerRun.current) setConfLoading(false);
    }
  }

  // ---------- белок-мишень ----------
  const candidates = useMemo<Candidate[]>(() => {
    const map = new Map<string, string>();
    qsar.forEach((p) => map.set(p.target_id, p.target_name));
    chembl?.targets.forEach((t) => {
      if (!map.has(t.target_id)) map.set(t.target_id, t.target_name ?? t.target_id);
    });
    chembl?.mechanisms.forEach((m) => {
      if (m.target_id && !map.has(m.target_id)) {
        map.set(m.target_id, m.target_name ?? m.target_id);
      }
    });
    return Array.from(map, ([id, name]) => ({ id, name }));
  }, [qsar, chembl]);

  const [selected, setSelected] = useState("");
  const [manual, setManual] = useState("");
  const [protein, setProtein] = useState<ProteinStructure | null>(null);
  const [protLoading, setProtLoading] = useState(false);
  const [protError, setProtError] = useState("");
  const [proteinStyle, setProteinStyle] = useState<ViewStyle>("plddt");

  async function loadProtein(resolve: () => Promise<string>) {
    setProtLoading(true);
    setProtError("");
    try {
      const accession = await resolve();
      setProtein(await fetchProtein(accession));
    } catch (err) {
      setProtein(null);
      setProtError(
        err instanceof Error ? err.message : "Не удалось загрузить структуру."
      );
    } finally {
      setProtLoading(false);
    }
  }

  function loadTarget() {
    if (!selected) return;
    loadProtein(async () => {
      const target = await fetchTargetProteins(selected);
      if (target.proteins.length === 0) {
        throw new Error(
          "Для этой мишени в ChEMBL не указан белок UniProt " +
            "(например, это комплекс или клеточная линия)."
        );
      }
      return target.proteins[0].accession;
    });
  }

  function loadManual() {
    const value = manual.trim();
    if (value) loadProtein(async () => value);
  }

  return (
    <div>
      {/* ----- малая молекула ----- */}
      <div className="section-label">3D-модель молекулы</div>

      {!conformer && !confLoading && (
        <div className="tab-state">
          <p>3D-конформер строится по запросу (RDKit, ETKDG + MMFF94).</p>
          <button
            type="button"
            className="primary-button"
            onClick={() => buildConformer(false)}
          >
            Построить 3D
          </button>
        </div>
      )}

      {confLoading && (
        <div className="tab-state">
          <div className="spinner" />
          <p>Строим 3D-конформер…</p>
        </div>
      )}
      {confError && (
        <div className="tab-note tab-note-error">
          {confError}{" "}
          <button
            type="button"
            className="text-button"
            onClick={() => buildConformer(true)}
          >
            Повторить
          </button>
        </div>
      )}

      {conformer && !confLoading && (
        <>
          <div className="viewer-controls">
            <select
              value={ligandStyle}
              onChange={(e: { target: { value: string } }) =>
                setLigandStyle(e.target.value as ViewStyle)
              }
            >
              <option value="ballstick">Шарики и палочки</option>
              <option value="stick">Палочки</option>
              <option value="sphere">Ван-дер-Ваальс</option>
              <option value="lines">Линии</option>
            </select>
            <button
              type="button"
              className="ghost-button"
              onClick={() => buildConformer(true)}
            >
              Перестроить 3D
            </button>
          </div>
          <MolViewer
            data={conformer.molblock}
            format="mol"
            kind="ligand"
            style={ligandStyle}
          />
          <div className="result-actions">
            <button
              type="button"
              className="ghost-button"
              onClick={() => saveText("chemanalyzer-3d.sdf", conformer.sdf)}
            >
              Скачать SDF
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => saveText("chemanalyzer-3d.mol", conformer.molblock)}
            >
              Скачать MOL
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => saveText("chemanalyzer-3d.pdb", conformer.pdb)}
            >
              Скачать PDB
            </button>
          </div>
          {conformer.warnings.map((w) => (
            <div className="tab-note tab-note-warn" key={w}>
              {w}
            </div>
          ))}
          <div className="tab-note">
            Метод: {conformer.method}, атомов: {conformer.num_atoms}.{" "}
            {conformer.note}
          </div>
        </>
      )}

      {/* ----- белок ----- */}
      <div className="section-label">Белок-мишень (AlphaFold)</div>
      <div className="tab-note" style={{ marginTop: 0 }}>
        AlphaFold предсказывает структуры белков, а не малых молекул. Здесь
        показываются готовые модели белков-мишеней из базы AlphaFold.
      </div>

      <div className="protein-picker">
        <select
          value={selected}
          onChange={(e: { target: { value: string } }) =>
            setSelected(e.target.value)
          }
        >
          <option value="">
            {candidates.length
              ? "Выберите мишень из результатов…"
              : "Мишеней в результатах пока нет"}
          </option>
          {candidates.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="primary-button"
          disabled={!selected || protLoading}
          onClick={loadTarget}
        >
          Показать
        </button>
      </div>

      <div className="protein-picker">
        <input
          value={manual}
          maxLength={12}
          placeholder="или UniProt ID, например P35354"
          onChange={(e: { target: { value: string } }) =>
            setManual(e.target.value)
          }
          onKeyDown={(e: { key: string }) => {
            if (e.key === "Enter") loadManual();
          }}
        />
        <button
          type="button"
          className="ghost-button"
          disabled={!manual.trim() || protLoading}
          onClick={loadManual}
        >
          Загрузить
        </button>
      </div>

      {protLoading && (
        <div className="tab-state">
          <div className="spinner" />
          <p>Загружаем модель из AlphaFold…</p>
        </div>
      )}
      {protError && <div className="tab-note tab-note-error">{protError}</div>}

      {protein && !protLoading && (
        <>
          <div className="compound-card" style={{ marginTop: 14 }}>
            <div className="compound-status">AlphaFold DB</div>
            <h3>{protein.gene ?? protein.uniprot}</h3>
            <div className="compound-meta">
              <span>{protein.uniprot}</span>
              {protein.organism && <span>{protein.organism}</span>}
              {protein.residues && <span>{protein.residues} аа</span>}
            </div>
            {protein.description && (
              <p className="protein-desc">{protein.description}</p>
            )}
            {protein.mean_plddt !== null && (
              <span className={`badge ${plddtTone(protein.mean_plddt)}`}>
                средний pLDDT {protein.mean_plddt} · {protein.plddt_label}
              </span>
            )}
          </div>

          <div className="viewer-controls">
            <select
              value={proteinStyle}
              onChange={(e: { target: { value: string } }) =>
                setProteinStyle(e.target.value as ViewStyle)
              }
            >
              <option value="plddt">Цвет по достоверности (pLDDT)</option>
              <option value="spectrum">Радуга (N → C конец)</option>
              <option value="lines">Линии (все атомы)</option>
            </select>
          </div>
          <MolViewer
            data={protein.pdb}
            format="pdb"
            kind="protein"
            style={proteinStyle}
            height={360}
          />

          <div className="result-actions">
            <a
              className="ghost-button"
              href={proteinDownloadUrl(protein.uniprot, "pdb")}
            >
              Скачать PDB
            </a>
            <a
              className="ghost-button"
              href={proteinDownloadUrl(protein.uniprot, "cif")}
            >
              Скачать mmCIF
            </a>
          </div>
          {protein.fragments > 1 && (
            <div className="tab-note">
              Белок длинный, в AlphaFold он разбит на {protein.fragments}{" "}
              фрагментов; показан первый.
            </div>
          )}
          <div className="tab-note">{protein.disclaimer}</div>
          <div className="tab-note">{protein.attribution}</div>
        </>
      )}
    </div>
  );
}
