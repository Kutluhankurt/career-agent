import { motion } from "motion/react";
import { formatDuration, weekdayLetter, parseDateKey } from "../lib/format";

/** Tiny line, to scale between its own min and max. */
export function Sparkline({ values, color = "var(--blue)", width = 120, height = 32 }: { values: number[]; color?: string; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1);
  const pad = 2;
  const step = (width - pad * 2) / (values.length - 1);
  const pts = values.map((v, i) => [pad + i * step, height - pad - (v / max) * (height - pad * 2)] as const);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none" role="img" aria-label={`Last ${values.length} days, peak ${formatDuration(max)}`}>
      <motion.path d={d} fill="none" stroke={color} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1, ease: [0.25, 1, 0.5, 1] }} />
    </svg>
  );
}

/** Bars by day, to scale from zero. The final day is highlighted. */
export function DayBars({ data, height = 150 }: { data: { date: string; active_seconds: number }[]; height?: number }) {
  const n = data.length;
  const W = 600;
  const gap = n > 10 ? 4 : 14;
  const bw = (W - gap * (n - 1)) / n;
  const max = Math.max(...data.map((d) => d.active_seconds), 3600);
  const H = height - 22;
  const total = data.reduce((a, d) => a + d.active_seconds, 0);
  return (
    <svg viewBox={`0 0 ${W} ${height}`} width="100%" role="img" aria-label={`Active time per day, ${formatDuration(total)} in total`} className="daybars">
      {data.map((d, i) => {
        const h = Math.max(3, (d.active_seconds / max) * H);
        const x = i * (bw + gap);
        const last = i === n - 1;
        return (
          <g key={d.date}>
            <motion.rect
              x={x}
              y={H - h}
              width={bw}
              height={h}
              rx={Math.min(6, bw / 2)}
              fill={last ? "var(--blue)" : "var(--fill)"}
              style={{ transformBox: "fill-box", transformOrigin: "bottom" }}
              initial={{ scaleY: 0 }}
              animate={{ scaleY: 1 }}
              transition={{ duration: 0.9, delay: 0.1 + i * (n > 10 ? 0.015 : 0.05), ease: [0.25, 1, 0.5, 1] }}
            >
              <title>{`${d.date}: ${formatDuration(d.active_seconds)}`}</title>
            </motion.rect>
            {(n <= 10 || i % 7 === 0 || last) && (
              <text x={x + bw / 2} y={height - 4} textAnchor="middle" fontSize={n > 10 ? 11 : 12} fill="var(--faint)">
                {n > 10 ? parseDateKey(d.date).getDate() : weekdayLetter(d.date)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/** 30-day score history. */
export function LineChart({ points, height = 120 }: { points: { date: string; score: number }[]; height?: number }) {
  if (points.length < 2) return null;
  const W = 360;
  const pad = 6;
  const lo = Math.min(...points.map((p) => p.score)) - 3;
  const hi = Math.max(...points.map((p) => p.score)) + 3;
  const xy = points.map((p, i) => [pad + (i / (points.length - 1)) * (W - pad * 2), height - pad - ((p.score - lo) / (hi - lo)) * (height - pad * 2)] as const);
  const d = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const last = xy[xy.length - 1];
  const first = points[0];
  const end = points[points.length - 1];
  return (
    <svg viewBox={`0 0 ${W} ${height}`} width="100%" role="img" aria-label={`Score over the last ${points.length} days, from ${first?.score} to ${end?.score}`}>
      <line x1={pad} x2={W - pad} y1={height - pad} y2={height - pad} stroke="var(--hair)" />
      <motion.path d={d} fill="none" stroke="var(--blue)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.1, ease: [0.25, 1, 0.5, 1] }} />
      {last && <motion.circle cx={last[0]} cy={last[1]} r={4} fill="var(--blue)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }} />}
    </svg>
  );
}
