import type { RadarAxis } from "../types/molecule";

// Область просмотра шире самого радара: справа и слева остаётся место для подписей.
const VB_W = 380;
const VB_H = 300;
const CX = VB_W / 2;
const CY = VB_H / 2;
const R = 88; // радиус внешнего края
const PINK = 0.72; // доля R, где проходит граница оптимальной зоны

/**
 * Как в SwissADME: центр = нижняя граница оптимума, край розового шестиугольника =
 * верхняя граница. Значение ниже нижней границы схлопывается в центр, выше верхней —
 * выходит за розовую зону (до внешнего края).
 */
export function radarFraction(axis: RadarAxis, value: number): number {
  const span = axis.ok_max - axis.ok_min;
  const t = (value - axis.ok_min) / span; // 0 — нижняя граница, 1 — верхняя
  if (t <= 0) return 0;
  if (t <= 1) return t * PINK;
  return Math.min(1, PINK + (t - 1) * PINK * 0.6);
}

function polar(index: number, fraction: number): [number, number] {
  // Первая ось — сверху, дальше по часовой стрелке (как в SwissADME).
  const angle = ((-90 + index * 60) * Math.PI) / 180;
  return [CX + R * fraction * Math.cos(angle), CY + R * fraction * Math.sin(angle)];
}

const poly = (points: Array<[number, number]>) =>
  points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ") + " Z";

export default function RadarChart({ axes }: { axes: RadarAxis[] }) {
  const pink = poly(axes.map((_, i) => polar(i, PINK)));
  const molecule = axes.map((a, i) => polar(i, radarFraction(a, a.value)));

  return (
    <svg className="radar-svg" viewBox={`0 0 ${VB_W} ${VB_H}`} role="img" aria-label="Радар биодоступности">
      {[1 / 3, 2 / 3, 1].map((f) => (
        <path
          key={f}
          d={poly(axes.map((_, i) => polar(i, f * 1)))}
          fill="none"
          stroke="currentColor"
          strokeOpacity="0.12"
        />
      ))}
      {axes.map((_, i) => {
        const [x, y] = polar(i, 1);
        return <line key={i} x1={CX} y1={CY} x2={x} y2={y} stroke="currentColor" strokeOpacity="0.14" />;
      })}

      {/* розовая зона — оптимум для приёма внутрь */}
      <path d={pink} fill="#f472b6" fillOpacity="0.26" stroke="#ec4899" strokeOpacity="0.55" />

      <path d={poly(molecule)} fill="#ef4444" fillOpacity="0.18" stroke="#dc2626" strokeWidth="2" />
      {molecule.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="3.4" fill={axes[i].in_range ? "#dc2626" : "#7f1d1d"} />
      ))}

      {axes.map((a, i) => {
        const [x, y] = polar(i, 1.2);
        const anchor = Math.abs(x - CX) < 6 ? "middle" : x > CX ? "start" : "end";
        return (
          <g key={a.key}>
            <title>{`${a.label}: ${a.value}${a.unit ? ` ${a.unit}` : ""} (оптимум ${a.ok_min} … ${a.ok_max})`}</title>
            <text x={x} y={y - 2} textAnchor={anchor} fontSize="11" fontWeight="700" fill={a.in_range ? "currentColor" : "#dc2626"}>
              {a.key}
            </text>
            <text x={x} y={y + 11} textAnchor={anchor} fontSize="10" fill="currentColor" fillOpacity="0.7">
              {a.value}
              {a.unit ? ` ${a.unit}` : ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
