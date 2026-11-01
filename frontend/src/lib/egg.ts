import type { Ellipse } from "../types/molecule";

/** Точки контура эллипса в координатах данных (TPSA, WLOGP). */
export function ellipsePoints(e: Ellipse, n = 240): Array<[number, number]> {
  const t = (e.angle * Math.PI) / 180;
  const c = Math.cos(t);
  const s = Math.sin(t);
  return Array.from({ length: n }, (_, i) => {
    const th = (2 * Math.PI * i) / n;
    const u = e.a * Math.cos(th);
    const v = e.b * Math.sin(th);
    return [e.cx + u * c - v * s, e.cy + u * s + v * c];
  });
}

export function isInside(x: number, y: number, e: Ellipse): boolean {
  const t = (e.angle * Math.PI) / 180;
  const dx = x - e.cx;
  const dy = y - e.cy;
  const u = dx * Math.cos(t) + dy * Math.sin(t);
  const v = -dx * Math.sin(t) + dy * Math.cos(t);
  return (u / e.a) ** 2 + (v / e.b) ** 2 <= 1;
}

export interface Bounds {
  xmin: number;
  xmax: number;
  ymin: number;
  ymax: number;
  xStep: number;
  yStep: number;
  /** Точка не помещается даже в расширенные границы — рисуется у края. */
  clipped: boolean;
}

const X_CAP = 400;
const Y_CAP = 15;

/** Границы графика: стандартные (как у SwissADME), расширяются, если точка вне них. */
export function plotBounds(tpsa: number, wlogp: number): Bounds {
  const xmax = Math.min(X_CAP, Math.max(200, Math.ceil((tpsa + 20) / 20) * 20));
  const ymin = Math.max(-Y_CAP, Math.min(-4, Math.floor(wlogp) - 1));
  const ymax = Math.min(Y_CAP, Math.max(8, Math.ceil(wlogp) + 1));
  return {
    xmin: -20,
    xmax,
    ymin,
    ymax,
    xStep: xmax - -20 > 260 ? 40 : 20,
    yStep: ymax - ymin > 14 ? 2 : 1,
    clipped: tpsa > xmax || wlogp < ymin || wlogp > ymax
  };
}

export const clamp = (v: number, lo: number, hi: number): number =>
  Math.min(hi, Math.max(lo, v));
