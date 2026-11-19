import type { ApplicabilityTest } from "../types/molecule";

export default function ApplicabilityTestSummary({ test }: { test?: ApplicabilityTest | null }) {
  if (!test || test.status === "not_recorded") {
    return <div className="activity-support">Отдельной оценки для молекул с прогнозом пока нет.</div>;
  }
  const metric = test.value == null ? "нет оценки" : test.metric === "r2"
    ? `R² ${test.value.toFixed(3)}`
    : `BA ${(100 * test.value).toFixed(2)}%`;
  return <div className="activity-support">
    Допустимый для прогноза поднабор · {metric} · {test.molecules ?? "—"} из {test.total_molecules ?? "—"} молекул
    {" · "}Групп каркасов {test.scaffolds ?? "—"}
  </div>;
}
