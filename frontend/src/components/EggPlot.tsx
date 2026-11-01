import { useMemo } from "react";
import { clamp, ellipsePoints, plotBounds } from "../lib/egg";
import type { BoiledEggModel, Ellipse } from "../types/molecule";

const W = 560;
const H = 380;
const M = { l: 46, r: 14, t: 12, b: 40 };

// Цвета фиксированные (не зависят от темы): белок должен быть белым, желток — жёлтым.
const COLORS = {
  plot: "#f1f3f6",
  grid: "#dde2e9",
  axis: "#4b5563",
  white: "#ffffff",
  whiteStroke: "#cfd5de",
  yolk: "#f7c948",
  yolkStroke: "#d9a521"
};

export default function EggPlot({ egg }: { egg: BoiledEggModel }) {
  const b = useMemo(() => plotBounds(egg.tpsa, egg.wlogp), [egg.tpsa, egg.wlogp]);

  const px = (x: number) =>
    M.l + ((x - b.xmin) / (b.xmax - b.xmin)) * (W - M.l - M.r);
  const py = (y: number) =>
    H - M.b - ((y - b.ymin) / (b.ymax - b.ymin)) * (H - M.t - M.b);

  const path = (e: Ellipse) =>
    ellipsePoints(e)
      .map(([x, y], i) => `${i === 0 ? "M" : "L"}${px(x).toFixed(1)},${py(y).toFixed(1)}`)
      .join(" ") + " Z";

  const xs: number[] = [];
  for (let x = Math.ceil(b.xmin / b.xStep) * b.xStep; x <= b.xmax; x += b.xStep) xs.push(x);
  const ys: number[] = [];
  for (let y = Math.ceil(b.ymin / b.yStep) * b.yStep; y <= b.ymax; y += b.yStep) ys.push(y);

  const dotX = px(clamp(egg.tpsa, b.xmin, b.xmax));
  const dotY = py(clamp(egg.wlogp, b.ymin, b.ymax));

  return (
    <svg
      className="egg-svg"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`BOILED-Egg: TPSA ${egg.tpsa}, WLOGP ${egg.wlogp}`}
    >
      <rect x={M.l} y={M.t} width={W - M.l - M.r} height={H - M.t - M.b} fill={COLORS.plot} />

      {xs.map((x) => (
        <g key={`x${x}`}>
          <line x1={px(x)} x2={px(x)} y1={M.t} y2={H - M.b} stroke={COLORS.grid} strokeWidth="1" />
          <text x={px(x)} y={H - M.b + 15} textAnchor="middle" fontSize="11" fill={COLORS.axis}>
            {x}
          </text>
        </g>
      ))}
      {ys.map((y) => (
        <g key={`y${y}`}>
          <line x1={M.l} x2={W - M.r} y1={py(y)} y2={py(y)} stroke={COLORS.grid} strokeWidth="1" />
          <text x={M.l - 7} y={py(y) + 4} textAnchor="end" fontSize="11" fill={COLORS.axis}>
            {y}
          </text>
        </g>
      ))}

      {/* белок (ЖКТ), поверх него желток (ГЭБ) — как в SwissADME */}
      <path d={path(egg.white)} fill={COLORS.white} stroke={COLORS.whiteStroke} strokeWidth="1.5" />
      <path d={path(egg.yolk)} fill={COLORS.yolk} fillOpacity="0.92" stroke={COLORS.yolkStroke} strokeWidth="1.5" />

      <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke={COLORS.axis} strokeWidth="1.2" />
      <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke={COLORS.axis} strokeWidth="1.2" />
      <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" fontSize="12" fontWeight="600" fill={COLORS.axis}>
        TPSA, Å²
      </text>
      <text
        transform={`translate(13 ${(M.t + H - M.b) / 2}) rotate(-90)`}
        textAnchor="middle"
        fontSize="12"
        fontWeight="600"
        fill={COLORS.axis}
      >
        WLOGP
      </text>

      {/* молекула; цвет не кодирует P-gp — он не рассчитывается */}
      <circle cx={dotX} cy={dotY} r="7" fill="#ffffff" stroke="#111827" strokeWidth="2.6">
        <title>{`TPSA ${egg.tpsa} Å², WLOGP ${egg.wlogp}`}</title>
      </circle>
      <circle cx={dotX} cy={dotY} r="2.2" fill="#111827" />
    </svg>
  );
}
