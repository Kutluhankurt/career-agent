import type { TruthState } from "../api/types";

const pad = (n: number) => String(n).padStart(2, "0");

/** "6h 42m", "1h", "42m", "<1m". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s === 0) return "0m";
  if (s < 60) return "<1m";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h === 0) return `${m}m`;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

/** "00:32:14" */
export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
}

/** Hours with one decimal for compact stats: "43h". */
export function formatHours(seconds: number): string {
  const h = seconds / 3600;
  return h >= 10 ? `${Math.round(h)}h` : `${Math.round(h * 10) / 10}h`;
}

export function confidencePercent(c: number): number {
  return Math.round(Math.min(1, Math.max(0, c)) * 100);
}

/** ≥95 Very likely, ≥80 Likely, ≥60 Possibly, else Unsure. */
export function confidenceWord(c: number): string {
  const p = confidencePercent(c);
  if (p >= 95) return "Very likely";
  if (p >= 80) return "Likely";
  if (p >= 60) return "Possibly";
  return "Unsure";
}

/** "Likely · 86%" */
export function confidenceLabel(c: number): string {
  return `${confidenceWord(c)} · ${confidencePercent(c)}%`;
}

export function stateLabel(s: TruthState): string {
  switch (s) {
    case "confirmed":
      return "Confirmed";
    case "observed":
      return "Observed";
    case "inferred":
      return "Needs review";
    case "rejected":
      return "Not right";
  }
}

/** "09:12" in local time. */
export function formatTime(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatRange(start: string, end: string): string {
  return `${formatTime(start)} – ${formatTime(end)}`;
}

/** Local "YYYY-MM-DD". */
export function dateKey(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function parseDateKey(key: string): Date {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1);
}

export function addDays(key: string, n: number): string {
  const d = parseDateKey(key);
  d.setDate(d.getDate() + n);
  return dateKey(d);
}

export function formatLongDate(key: string): string {
  return parseDateKey(key).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
}

export function weekdayLetter(key: string): string {
  return parseDateKey(key).toLocaleDateString("en-GB", { weekday: "narrow" });
}

export function greeting(hour: number): string {
  if (hour < 5) return "Good evening";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function relativeTime(iso: string, now: Date = new Date()): string {
  const diff = (now.getTime() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  const days = Math.floor(diff / 86400);
  return days === 1 ? "Yesterday" : `${days}d ago`;
}

export function projectColor(index: number | null | undefined): string {
  if (index == null) return "var(--faint)";
  return `var(--p${(((index % 8) + 8) % 8) + 1})`;
}

/** Minutes since local midnight for an ISO timestamp. */
export function minutesOfDay(iso: string | Date): number {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
