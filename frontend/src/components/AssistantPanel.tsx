import { useEffect, useMemo, useRef, useState } from "react";
import { getAssistantStatus, streamChat } from "../api/assistant";
import type {
  ActivityResponse,
  AdmeResponse,
  AssistantMode,
  AssistantStatus,
  AsyncState,
  ChatMessage,
  ChemblResponse,
  IdentificationResult,
  MoleculeResponse
} from "../types/molecule";

interface Props {
  result: MoleculeResponse | null;
  identification: IdentificationResult | null;
  adme: AsyncState<AdmeResponse>;
  activity: AsyncState<ActivityResponse>;
  chembl: AsyncState<ChemblResponse>;
}

const PROMPTS: Record<AssistantMode, string[]> = {
  review: [
    "Проверь мой анализ",
    "Какие результаты вызывают сомнение?",
    "Что стоит перепроверить экспериментально?"
  ],
  learn: [
    "Объясни результаты простыми словами",
    "Что такое LogP и TPSA на этом примере?",
    "Проверь меня: задай мне вопрос",
    "Чем QSAR отличается от PASS?"
  ]
};

/** Компактный срез результатов, который видит ассистент. */
function buildContext(
  result: MoleculeResponse | null,
  identification: IdentificationResult | null,
  adme: AdmeResponse | null,
  activity: ActivityResponse | null,
  chembl: ChemblResponse | null
): Record<string, unknown> | null {
  if (!result) return null;

  return {
    structure: {
      canonical_smiles: result.canonical_smiles,
      formula: result.formula,
      molecular_weight: result.molecular_weight,
      logp: result.logp,
      tpsa: result.tpsa,
      hbd: result.hbd,
      hba: result.hba,
      rotatable_bonds: result.rotatable_bonds,
      rings: result.rings,
      heavy_atoms: result.heavy_atoms,
      lipinski_violations: result.lipinski_violations,
      identification: identification && {
        status: identification.status,
        match_type: identification.match_type,
        title:
          identification.found && identification.match_type === "exact"
            ? identification.title
            : null,
        iupac_name:
          identification.found && identification.match_type === "exact"
            ? identification.iupac_name
            : null,
        candidate_title:
          identification.found && identification.match_type === "connectivity"
            ? identification.title
            : null,
        candidate_iupac_name:
          identification.found && identification.match_type === "connectivity"
            ? identification.iupac_name
            : null,
        cid: identification.match_type === "exact" ? identification.cid : null,
        candidate_cid:
          identification.match_type === "connectivity" ? identification.cid : null,
        note: "Название подтверждено только при точном совпадении структуры; совпадение по связности указывает лишь на кандидата."
      }
    },
    adme: adme && {
      note: "BOILED-Egg (WLOGP и TPSA с S и P); P-gp и CYP не рассчитываются",
      gi_absorption: adme.pharmacokinetics.gi_absorption,
      bbb_permeant: adme.pharmacokinetics.bbb_permeant,
      esol_logs: adme.solubility.esol_logs,
      esol_class: adme.solubility.esol_class,
      radar_out_of_range: adme.radar.filter((a) => !a.in_range).map((a) => a.key),
      rules: adme.druglikeness.map((r) => ({ rule: r.name, passed: r.passed, violations: r.violations })),
      lead_likeness: adme.medchem.lead_likeness.passed
    },
    similarity_activity: activity && {
      note: "оценка по сходству Tanimoto, не вероятность",
      top: activity.activities.slice(0, 8).map((a) => ({
        activity: a.name,
        score: a.score,
        confidence: a.confidence
      })),
      nearest_drugs: activity.nearest.slice(0, 3)
    },
    qsar: activity && {
      available: activity.qsar.available,
      message: activity.qsar.message,
      predictions: activity.qsar.predictions.slice(0, 8).map((p) => ({
        target: p.target_name,
        probability: p.probability,
        domain: p.domain,
        max_similarity: p.max_similarity,
        cv_auc: p.cv_auc
      }))
    },
    druglikeness: activity && {
      qed: activity.druglikeness.qed,
      rules: activity.druglikeness.rules.map((r) => ({
        rule: r.name,
        passed: r.passed,
        violations: r.violations
      })),
      gi_absorption: activity.druglikeness.gi_absorption,
      bbb_permeant: activity.druglikeness.bbb_permeant,
      pains: activity.druglikeness.pains_alerts,
      brenk: activity.druglikeness.brenk_alerts
    },
    chembl: chembl && {
      found: chembl.found,
      name: chembl.name,
      max_phase: chembl.max_phase,
      mechanisms: chembl.mechanisms.slice(0, 5).map((m) => m.action),
      indications: chembl.indications.slice(0, 6).map((i) => i.name),
      top_targets: chembl.targets.slice(0, 5).map((t) => ({
        target: t.target_name,
        best_pchembl: t.best_pchembl
      })),
      message: chembl.message
    }
  };
}

export default function AssistantPanel({
  result,
  identification,
  adme,
  activity,
  chembl
}: Props) {
  const [mode, setMode] = useState<AssistantMode>("review");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<AssistantStatus | null | undefined>(
    undefined
  );

  const abortRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    getAssistantStatus().then(setStatus);
    return () => abortRef.current?.abort();
  }, []);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const context = useMemo(
    () => buildContext(result, identification, adme.data, activity.data, chembl.data),
    [result, identification, adme.data, activity.data, chembl.data]
  );

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;

    const history: ChatMessage[] = [
      ...messages,
      { role: "user", content: question }
    ];
    setMessages([...history, { role: "assistant", content: "" }]);
    setInput("");
    setError("");
    setBusy(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        mode,
        history,
        context,
        (chunk) =>
          setMessages((current) => {
            const next = current.slice();
            const last = next[next.length - 1];
            next[next.length - 1] = {
              ...last,
              content: last.content + chunk
            };
            return next;
          }),
        controller.signal
      );
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setError(
          err instanceof Error ? err.message : "Не удалось получить ответ."
        );
      }
    } finally {
      // Пустой ответ ассистента (ошибка/отмена) не храним в истории.
      setMessages((current) =>
        current.length && current[current.length - 1].content === ""
          ? current.slice(0, -1)
          : current
      );
      setBusy(false);
      abortRef.current = null;
    }
  }

  const unavailable = status === null;
  const notConfigured = status !== undefined && status !== null && !status.configured;

  return (
    <section className="assistant-panel" id="assistant">
      <div className="assistant-head">
        <div>
          <div className="section-label">Ассистент Claude</div>
          <h2>Проверка анализа и помощь в изучении</h2>
        </div>
        <div className="mode-switch" role="tablist">
          {(["review", "learn"] as AssistantMode[]).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              className={`tab-button${mode === m ? " active" : ""}`}
              onClick={() => setMode(m)}
            >
              {m === "review" ? "Проверка" : "Обучение"}
            </button>
          ))}
        </div>
      </div>

      {notConfigured && (
        <div className="tab-note">
          <strong>Ассистент не настроен.</strong> Скопируйте{" "}
          <code>backend/.env.example</code> в <code>backend/.env</code>, впишите
          свой <code>ANTHROPIC_API_KEY</code> и перезапустите backend.
        </div>
      )}
      {unavailable && (
        <div className="tab-note tab-note-error">
          Нет связи с backend — ассистент недоступен.
        </div>
      )}

      <div className="chat-log" ref={logRef} aria-live="polite">
        {messages.length === 0 ? (
          <p className="chat-empty">
            {result
              ? "Ассистент видит результаты текущего анализа. Выберите подсказку или задайте свой вопрос."
              : "Нарисуйте молекулу и нажмите «Анализировать» — тогда ассистент увидит результаты. Общие вопросы по химии можно задавать и сейчас."}
          </p>
        ) : (
          messages.map((message, index) => (
            <div
              key={index}
              className={`chat-message chat-${message.role}`}
            >
              <span>{message.role === "user" ? "Вы" : "Claude"}</span>
              <p>
                {message.content ||
                  (busy && index === messages.length - 1 ? "…" : "")}
              </p>
            </div>
          ))
        )}
      </div>

      {error && <div className="tab-note tab-note-error">{error}</div>}

      <div className="chip-row prompt-row">
        {PROMPTS[mode].map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="chip chip-button"
            disabled={busy || notConfigured || unavailable}
            onClick={() => send(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>

      <form
        className="chat-input"
        onSubmit={(event: { preventDefault(): void }) => {
          event.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          maxLength={4000}
          placeholder="Задайте вопрос ассистенту…"
          disabled={notConfigured || unavailable}
          onChange={(event: { target: { value: string } }) =>
            setInput(event.target.value)
          }
        />
        {busy ? (
          <button
            type="button"
            className="ghost-button"
            onClick={() => abortRef.current?.abort()}
          >
            Стоп
          </button>
        ) : (
          <button
            type="submit"
            className="primary-button"
            disabled={!input.trim() || notConfigured || unavailable}
          >
            Отправить
          </button>
        )}
        {messages.length > 0 && !busy && (
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              setMessages([]);
              setError("");
            }}
          >
            Очистить
          </button>
        )}
      </form>

      <p className="chat-privacy">
        При отправке вопроса структура и результаты анализа передаются в API
        Anthropic. Ассистент может ошибаться — важные выводы перепроверяйте.
      </p>
    </section>
  );
}
