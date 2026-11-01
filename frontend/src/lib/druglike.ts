/**
 * Оценка drug-likeness: PASS / WARNING / FAIL по каждому показателю.
 * Это эвристики для первичной ориентации, а НЕ медицинское заключение.
 */

export type Verdict = "pass" | "warn" | "fail";

export interface Criterion {
  key: "mw" | "logp" | "hbd" | "hba" | "tpsa" | "rotb";
  label: string;
  value: number;
  limit: number;
  rule: "Липински" | "Вебер";
  verdict: Verdict;
  explanation: string;
}

export interface DruglikeInput {
  molecular_weight: number;
  logp: number;
  hbd: number;
  hba: number;
  tpsa: number;
  rotatable_bonds: number;
}

/** Показатель в пределах нормы, но вплотную к границе (≥ 90% лимита). */
export const WARN_FRACTION = 0.9;

export function verdictFor(value: number, limit: number): Verdict {
  if (value > limit) return "fail";
  if (value >= limit * WARN_FRACTION) return "warn";
  return "pass";
}

function explain(label: string, value: number, limit: number, verdict: Verdict): string {
  if (verdict === "fail") {
    return `${label} ${value} выше предела ${limit}: такие молекулы реже хорошо всасываются при приёме внутрь.`;
  }
  if (verdict === "warn") {
    return `${label} ${value} близко к пределу ${limit}.`;
  }
  return `${label} ${value} в пределах нормы (≤ ${limit}).`;
}

export function evaluateCriteria(r: DruglikeInput): Criterion[] {
  const defs: Array<[Criterion["key"], string, number, number, Criterion["rule"]]> = [
    ["mw", "Молекулярная масса", r.molecular_weight, 500, "Липински"],
    ["logp", "LogP", r.logp, 5, "Липински"],
    ["hbd", "Доноры H-связи (HBD)", r.hbd, 5, "Липински"],
    ["hba", "Акцепторы H-связи (HBA)", r.hba, 10, "Липински"],
    ["tpsa", "TPSA", r.tpsa, 140, "Вебер"],
    ["rotb", "Вращаемые связи", r.rotatable_bonds, 10, "Вебер"]
  ];

  return defs.map(([key, label, value, limit, rule]) => {
    const verdict = verdictFor(value, limit);
    return { key, label, value, limit, rule, verdict, explanation: explain(label, value, limit, verdict) };
  });
}

export interface LipinskiSummary {
  violations: number;
  verdict: Verdict;
  text: string;
}

/** Правило пяти: 0 нарушений — PASS, 1 — WARNING (допускается), ≥2 — FAIL. */
export function summarizeLipinski(criteria: Criterion[]): LipinskiSummary {
  const violations = criteria.filter((c) => c.rule === "Липински" && c.verdict === "fail").length;

  if (violations === 0) {
    return {
      violations,
      verdict: "pass",
      text: "Молекула укладывается в правило пяти Липински."
    };
  }
  if (violations === 1) {
    return {
      violations,
      verdict: "warn",
      text: "Правило пяти допускает одно нарушение, но стоит присмотреться к этому показателю."
    };
  }
  return {
    violations,
    verdict: "fail",
    text: "Для приёма внутрь такие молекулы чаще оказываются проблемными."
  };
}

export function qedVerdict(qed: number): Verdict {
  if (qed >= 0.67) return "pass";
  if (qed >= 0.34) return "warn";
  return "fail";
}

export const VERDICT_LABEL: Record<Verdict, string> = {
  pass: "PASS",
  warn: "WARNING",
  fail: "FAIL"
};

export const DRUGLIKE_DISCLAIMER =
  "Это эвристические правила по расчётным дескрипторам. Они не являются " +
  "медицинским заключением и не заменяют эксперимент.";
