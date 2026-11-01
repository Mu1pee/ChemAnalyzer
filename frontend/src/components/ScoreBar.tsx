interface Props {
  value: number; // 0..1
  tone?: "high" | "medium" | "low";
}

export default function ScoreBar({ value, tone = "medium" }: Props) {
  const percent = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="score-bar" aria-hidden="true">
      <div
        className={`score-bar-fill tone-${tone}`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
