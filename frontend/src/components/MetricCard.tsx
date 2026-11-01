interface Props {
  label: string;
  value: string | number;
  unit?: string;
}

export default function MetricCard({ label, value, unit }: Props) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>
        {value}
        {unit && <small>{unit}</small>}
      </strong>
    </div>
  );
}
