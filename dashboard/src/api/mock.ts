// In-memory implementation of docs/API.md. Enabled by VITE_MOCK=1 (npm run dev:mock).
// Every endpoint is implemented, including mutations, so the dashboard can be built and
// demoed without the Python backend. State lives for the lifetime of the page.
import { addDays, dateKey, formatHours, formatTime, parseDateKey } from "../lib/format";
import type {
  Achievement,
  CV,
  CVBullet,
  Evidence,
  EvidenceType,
  Insights,
  MemoryItem,
  Profile,
  Project,
  ProjectRef,
  RawEvent,
  ReviewItem,
  Session,
  Settings,
  Skill,
  SkillSummary,
  Status,
  Today,
  TruthState,
} from "./types";

export interface MockOptions {
  now?: Date;
  /** Simulated network latency in ms. */
  latency?: number;
  /** Start with an incomplete profile so onboarding shows. */
  onboarding?: boolean;
  /** Start with no sessions, as on a first day. */
  empty?: boolean;
  /** Behave as if the server is not running. */
  offline?: boolean;
}

export class MockHttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export class MockUnreachable extends Error {}

const DAY = 86400;
const min = (m: number) => m * 60000;

function isoLocal(d: Date): string {
  const p = (n: number, w = 2) => String(Math.abs(n)).padStart(w, "0");
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}${sign}${p(Math.floor(Math.abs(off) / 60))}:${p(Math.abs(off) % 60)}`;
}

/** Small deterministic pseudo-random for repeatable fixtures. */
function rng(seed: number) {
  let s = seed >>> 0 || 1;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

interface Tpl {
  s: string;
  e: string;
  activity: string;
  label: string;
  category: string;
  project: string;
  state: TruthState;
  conf: number;
  skills: string[];
  ev: [EvidenceType, string, string][];
  apps: Record<string, number>;
  files: string[];
  tickets: string[];
  ws: string[];
  raw: [string, string, string][];
  live?: boolean;
}

const mins = (t: string) => {
  const [h, m] = t.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
};

const TEMPLATES: Tpl[] = [
  {
    s: "09:12", e: "10:04", activity: "Supervisor temperature testing", label: "supervisor · AI-1842", category: "Testing",
    project: "p-supervisor", state: "inferred", conf: 0.94, skills: ["Test automation", "Python", "Test analysis"],
    ev: [["ticket", "Ticket", "AI-1842"], ["file", "File", "temperature_test.py"], ["command", "Command", "pytest"], ["file", "File", "Temperature_Result.xlsx"]],
    apps: { "VS Code": 1500, Chrome: 900, Terminal: 520 }, files: ["temperature_test.py", "Temperature_Result.xlsx"], tickets: ["AI-1842"], ws: ["supervisor"],
    raw: [["09:12", "Chrome", "AI-1842 Temperature Test - Jira"], ["09:14", "VS Code", "temperature_test.py"], ["09:31", "Terminal", "pytest tests/test_temperature.py"], ["09:52", "Excel", "Temperature_Result.xlsx saved"], ["10:03", "Terminal", "git checkout feature/temperature-test"]],
  },
  {
    s: "10:08", e: "10:46", activity: "Python test development", label: "supervisor · test_supervisor.py", category: "Development",
    project: "p-supervisor", state: "confirmed", conf: 0.88, skills: ["Python", "pytest"],
    ev: [["file", "File", "test_supervisor.py"], ["git", "Commit", "abc123 Fix temperature validation"]],
    apps: { "VS Code": 2000, Terminal: 280 }, files: ["test_supervisor.py"], tickets: [], ws: ["supervisor"],
    raw: [["10:08", "VS Code", "test_supervisor.py"], ["10:44", "Terminal", "git commit abc123"]],
  },
  {
    s: "10:50", e: "11:22", activity: "Bug investigation", label: "mobile-ai · MAI-311", category: "Investigation",
    project: "p-mobile", state: "observed", conf: 0.72, skills: ["Debugging"],
    ev: [["ticket", "Ticket", "MAI-311"], ["browser", "Site", "jira.company.com"]],
    apps: { Chrome: 1700, Slack: 120 }, files: [], tickets: ["MAI-311"], ws: ["mobile-ai"],
    raw: [["10:50", "Chrome", "MAI-311 Camera freeze - Jira"], ["11:02", "Chrome", "Confluence - Camera pipeline"]],
  },
  {
    s: "11:30", e: "12:05", activity: "Firmware rollout", label: "version-updater · main.py", category: "Operations",
    project: "p-field", state: "confirmed", conf: 0.91, skills: ["SSH", "Embedded Linux"],
    ev: [["file", "File", "version_updater.py"], ["file", "File", "updated_devices.csv"]],
    apps: { Terminal: 1800, "VS Code": 200 }, files: ["version_updater.py", "updated_devices.csv"], tickets: [], ws: ["VersionUpdater_v2.3"],
    raw: [["11:30", "Terminal", "python3 main.py"], ["11:58", "Terminal", "updated_devices.csv saved"]],
  },
  {
    s: "13:15", e: "14:40", activity: "Supervisor test execution", label: "supervisor · pytest", category: "Testing",
    project: "p-supervisor", state: "inferred", conf: 0.86, skills: ["Test execution", "Test analysis"],
    ev: [["command", "Command", "pytest"], ["file", "File", "Temperature_Result.xlsx"]],
    apps: { Terminal: 3200, Excel: 1300 }, files: ["Temperature_Result.xlsx"], tickets: ["AI-1842"], ws: ["supervisor"],
    raw: [["13:15", "Terminal", "pytest -k temperature"], ["14:31", "Excel", "Temperature_Result.xlsx saved"]],
  },
  {
    s: "14:45", e: "15:20", activity: "Device log analysis", label: "logParser_v2 · parse.py", category: "Investigation",
    project: "p-field", state: "inferred", conf: 0.64, skills: ["Log analysis", "Python"],
    ev: [["file", "File", "parse.py"], ["file", "File", "device_0412.tm"]],
    apps: { Terminal: 900, "VS Code": 1000 }, files: ["parse.py", "device_0412.tm"], tickets: [], ws: ["logParser_v2"],
    raw: [["14:45", "Terminal", "python3 parse.py"], ["14:52", "VS Code", "Logs/device_0412.txt"]],
  },
  {
    s: "15:47", e: "16:20", activity: "Camera test automation", label: "mobile-ai · test_camera.py", category: "Testing",
    project: "p-mobile", state: "inferred", conf: 0.81, skills: ["Test automation", "Python"],
    ev: [["file", "File", "test_camera.py"]],
    apps: { "VS Code": 1500, Terminal: 400 }, files: ["test_camera.py"], tickets: ["MAI-311"], ws: ["mobile-ai"],
    raw: [["15:47", "VS Code", "test_camera.py"], ["16:12", "Terminal", "pytest tests/test_camera.py"]],
    live: true,
  },
];

export function createMockApi(opts: MockOptions = {}) {
  const now = () => opts.now ?? new Date();
  const started = now();
  const latency = opts.latency ?? 140;
  let offline = !!opts.offline;
  const todayKey = dateKey(started);

  // -- Projects --------------------------------------------------------------------
  const spark = (seed: number, base: number) => {
    const r = rng(seed);
    return Array.from({ length: 30 }, (_, i) => (i % 7 === 5 || i % 7 === 6 ? 0 : Math.round(base * (0.5 + r()) * 3600)));
  };
  const projects: Project[] = [
    { id: "p-supervisor", name: "Supervisor", state: "confirmed", color: 0, aliases: ["supervisor", "AI-"], active_seconds: 43 * 3600 + 900, session_count: 31, tickets: ["AI-1842", "AI-1790"], repos: ["supervisor"], skills: ["Test automation", "Python", "pytest", "Test analysis"], achievement_count: 1, sparkline: spark(11, 2.6), last_active: null },
    { id: "p-mobile", name: "Mobile AI", state: "confirmed", color: 1, aliases: ["mobile-ai", "MAI-"], active_seconds: 21 * 3600 + 1200, session_count: 17, tickets: ["MAI-311"], repos: ["mobile-ai"], skills: ["Debugging", "Test automation", "Python"], achievement_count: 1, sparkline: spark(23, 1.4), last_active: null },
    { id: "p-field", name: "Field Updates", state: "confirmed", color: 2, aliases: ["VersionUpdater_v2.3", "logParser_v2"], active_seconds: 17 * 3600 + 1800, session_count: 14, tickets: [], repos: ["VersionUpdater_v2.3", "logParser_v2"], skills: ["SSH", "Embedded Linux", "Log analysis"], achievement_count: 1, sparkline: spark(37, 1.1), last_active: null },
    { id: "p-logs", name: "Log Parser", state: "inferred", color: 3, aliases: ["logParser_v2"], active_seconds: 5 * 3600, session_count: 6, tickets: [], repos: ["logParser_v2"], skills: ["Log analysis", "Python"], achievement_count: 1, sparkline: spark(41, 0.5), last_active: null },
  ];
  const refOf = (id: string | null): ProjectRef | null => {
    const p = projects.find((x) => x.id === id);
    return p ? { id: p.id, name: p.name, color: p.color } : null;
  };

  // -- Sessions --------------------------------------------------------------------
  const sessions = new Map<string, Session>();
  const rawBySession = new Map<string, RawEvent[]>();
  const generated = new Set<string>();

  // Anchor today's schedule so the live session started 32m14s ago.
  const nowMin = started.getHours() * 60 + started.getMinutes() + started.getSeconds() / 60;
  const shift = Math.max(Math.round(nowMin - 32.23 - mins("15:47")), 10 - mins("09:12"));

  function ensureDay(key: string): Session[] {
    if (!generated.has(key)) {
      generated.add(key);
      const isToday = key === todayKey;
      const dow = parseDateKey(key).getDay();
      const skip = opts.empty || (key > todayKey) || (!isToday && (dow === 0 || dow === 6));
      if (!skip) {
        const base = parseDateKey(key).getTime();
        TEMPLATES.forEach((t, i) => {
          if (t.live && !isToday) return;
          const sh = isToday ? shift : 0;
          const start = new Date(base + min(mins(t.s) + sh));
          let end = new Date(base + min(mins(t.e) + sh));
          const open = !!t.live && isToday;
          if (open) end = now();
          const dur = Math.max(60, (end.getTime() - start.getTime()) / 1000);
          const id = `s-${key}-${i}`;
          const state: TruthState = isToday ? t.state : t.state === "inferred" ? "observed" : t.state;
          const evidence: Evidence[] = t.ev.map(([type, label, value], k) => ({
            id: `ev-${id}-${k}`, type, label, value, observed_at: isoLocal(new Date(start.getTime() + min(5 + k * 7))), session_id: id,
          }));
          sessions.set(id, {
            id, start: isoLocal(start), end: isoLocal(end), active_seconds: Math.round(dur * 0.93), idle_seconds: Math.round(dur * 0.07),
            is_open: open, label: t.label, activity: t.activity, category: t.category, project: refOf(t.project), state,
            confidence: t.conf, score: Math.min(1, t.conf + 0.04), skills: [...t.skills], evidence, applications: { ...t.apps },
            files: [...t.files], tickets: [...t.tickets], workspaces: [...t.ws], analyzed_by: open ? null : "claude",
          });
          rawBySession.set(
            id,
            t.raw.map(([hm, app, title]) => ({
              timestamp: isoLocal(new Date(base + min(mins(hm) + sh))),
              type: app === "Terminal" ? "command" : title.includes(".") ? "file" : "window",
              application: app, title,
            })),
          );
        });
      }
    }
    return [...sessions.values()].filter((s) => s.id.startsWith(`s-${key}-`)).sort((a, b) => a.start.localeCompare(b.start));
  }
  const liveSync = () => {
    for (const s of sessions.values()) {
      if (s.is_open) {
        s.end = isoLocal(now());
        const dur = (now().getTime() - new Date(s.start).getTime()) / 1000;
        s.active_seconds = Math.max(0, Math.round(dur * 0.97));
      }
    }
  };
  const activeOn = (key: string) => ensureDay(key).filter((s) => s.state !== "rejected").reduce((a, s) => a + s.active_seconds, 0);

  ensureDay(todayKey);
  for (const p of projects) {
    p.last_active = isoLocal(new Date(started.getTime() - min(p.id === "p-logs" ? 60 * 24 * 14 : p.id === "p-mobile" ? 5 : 40)));
  }

  // -- Skills ----------------------------------------------------------------------
  const skillSeed: [string, string, number, number, TruthState, string[]][] = [
    ["Python", "Language", 78, 75, "confirmed", ["Supervisor", "Mobile AI", "Field Updates"]],
    ["Test automation", "Practice", 65, 62, "confirmed", ["Supervisor", "Mobile AI"]],
    ["Log analysis", "Practice", 58, 51, "inferred", ["Field Updates", "Log Parser"]],
    ["Git", "Tool", 52, 52, "observed", ["Supervisor", "Field Updates"]],
    ["pytest", "Tool", 61, 58, "confirmed", ["Supervisor"]],
    ["SSH", "Tool", 44, 40, "observed", ["Field Updates"]],
    ["Embedded Linux", "Domain", 40, 38, "inferred", ["Field Updates"]],
    ["Debugging", "Practice", 47, 50, "observed", ["Mobile AI"]],
  ];
  const skills: Skill[] = skillSeed.map(([name, category, score, prev, state, pj], i) => {
    const r = rng(100 + i);
    const f = (b: number) => Math.round(Math.min(1, Math.max(0.05, b + (r() - 0.5) * 0.3)) * 100) / 100;
    return {
      id: `k-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`, name, category, state, score, previous_score: prev,
      factors: { frequency: f(score / 100), duration: f(score / 120), complexity: f(0.5), diversity: f(pj.length / 4), evidence: f(score / 100), confirmation: state === "confirmed" ? f(0.85) : f(0.2) },
      history: Array.from({ length: 30 }, (_, d) => {
        const t = d / 29;
        const base = prev - 5 + (score - prev + 5) * t;
        return { date: addDays(todayKey, d - 29), score: Math.round((base + (r() - 0.5) * 1.4) * 10) / 10 };
      }),
      projects: pj, evidence_count: Math.round(score / 3) + 4, active_seconds: Math.round(score * 1700),
    };
  });
  // Make each history end exactly on the current score.
  for (const k of skills) k.history[k.history.length - 1] = { date: todayKey, score: k.score };

  // -- Achievements ----------------------------------------------------------------
  const evi = (id: string, type: EvidenceType, label: string, value: string): Evidence => ({ id, type, label, value, observed_at: isoLocal(started), session_id: null });
  const step = (name: Achievement["steps"][number]["name"], done: boolean, ev: Evidence[] = []) => ({ name, done, evidence: done ? ev : [] });
  const achievements: Achievement[] = opts.empty
    ? []
    : [
        {
          id: "a-temp", title: "Investigated and validated temperature-related test behavior in Supervisor", project: refOf("p-supervisor"), ticket: "AI-1842", state: "inferred", confidence: 0.83,
          steps: [step("problem", true, [evi("ae1", "ticket", "Ticket", "AI-1842")]), step("investigation", true, [evi("ae2", "file", "File", "Temperature_Result.xlsx")]), step("implementation", true, [evi("ae3", "git", "Commit", "abc123 Fix temperature validation")]), step("testing", true, [evi("ae4", "command", "Command", "pytest, 23 runs")]), step("verification", false)],
          impact: null, on_cv: false, created_at: isoLocal(started),
        },
        {
          id: "a-roll", title: "Rolled out firmware 1.4 to 38 field devices", project: refOf("p-field"), ticket: null, state: "confirmed", confidence: 0.91,
          steps: [step("problem", true, [evi("ae5", "file", "File", "devices.csv")]), step("investigation", true, [evi("ae6", "file", "File", "version_updater.py")]), step("implementation", true, [evi("ae7", "git", "Commit", "version_updater.py, 9 commits")]), step("testing", true, [evi("ae8", "command", "Command", "python3 main.py")]), step("verification", true, [evi("ae9", "file", "File", "updated_devices.csv, 38 devices")])],
          impact: "38 devices updated in one afternoon", on_cv: true, created_at: isoLocal(new Date(started.getTime() - DAY * 2000)),
        },
        {
          id: "a-cam", title: "Built an automated camera regression check", project: refOf("p-mobile"), ticket: "MAI-311", state: "inferred", confidence: 0.62,
          steps: [step("problem", true, [evi("ae10", "ticket", "Ticket", "MAI-311")]), step("investigation", true, [evi("ae11", "browser", "Site", "jira.company.com")]), step("implementation", true, [evi("ae12", "file", "File", "test_camera.py, 6 edits")]), step("testing", false), step("verification", false)],
          impact: null, on_cv: false, created_at: isoLocal(started),
        },
        {
          id: "a-log", title: "Wrote a parser that turns device .tm logs into readable reports", project: refOf("p-logs"), ticket: null, state: "confirmed", confidence: 0.88,
          steps: [step("problem", true, [evi("ae13", "file", "File", "device_0412.tm")]), step("investigation", true, [evi("ae14", "file", "File", "parse.py")]), step("implementation", true, [evi("ae15", "file", "File", "parse.py, 4 edits")]), step("testing", true, [evi("ae16", "command", "Command", "python3 parse.py")]), step("verification", false)],
          impact: null, on_cv: false, created_at: isoLocal(new Date(started.getTime() - DAY * 12000)),
        },
      ];

  // -- Review ----------------------------------------------------------------------
  const reviews: ReviewItem[] = [];
  const sessionReview = (s: Session, off: number): ReviewItem => ({
    id: `rv-${s.id}`, kind: "session", ref_id: s.id, title: s.activity, subtitle: `Session · ${formatTime(s.start)}–${formatTime(s.end)}`,
    project: s.project, confidence: s.confidence, skills: s.skills, evidence: s.evidence, options: null, created_at: isoLocal(new Date(started.getTime() - off)),
  });
  if (!opts.empty) {
    const t = ensureDay(todayKey);
    const at = (i: number) => t[i];
    const s0 = at(0), s4 = at(4), s5 = at(5);
    if (s0) reviews.push(sessionReview(s0, min(300)));
    reviews.push({
      id: "rv-q1", kind: "question", ref_id: "q-1", title: "Is the supervisor folder your Supervisor project?", subtitle: "Question from Learning mode", project: refOf("p-supervisor"),
      confidence: 0.77, skills: [], evidence: [evi("qe1", "file", "Folder", "supervisor/"), evi("qe2", "ticket", "Ticket", "AI-1842")], options: ["Yes", "No"], created_at: isoLocal(new Date(started.getTime() - min(240))),
    });
    if (s4) reviews.push(sessionReview(s4, min(120)));
    const a1 = achievements[0];
    if (a1)
      reviews.push({
        id: "rv-a-temp", kind: "achievement", ref_id: a1.id, title: a1.title, subtitle: "Possible achievement", project: a1.project, confidence: a1.confidence, skills: [],
        evidence: a1.steps.flatMap((s) => s.evidence).slice(0, 3), options: null, created_at: isoLocal(new Date(started.getTime() - min(90))),
      });
    if (s5) reviews.push(sessionReview(s5, min(60)));
  }

  // -- CV --------------------------------------------------------------------------
  const cvEv: Record<string, Evidence> = {
    e1: evi("e1", "ticket", "Ticket", "AI-1842 Temperature Test"), e2: evi("e2", "file", "File", "temperature_test.py, 14 edits"),
    e3: evi("e3", "command", "Command", "pytest, 23 runs"), e4: evi("e4", "git", "Commit", "abc123 Fix temperature validation"),
    e5: evi("e5", "file", "File", "Temperature_Result.xlsx"), e6: evi("e6", "file", "File", "test_camera.py, 6 edits"),
    e7: evi("e7", "ticket", "Ticket", "MAI-311 Camera freeze"), e8: evi("e8", "git", "Commit", "version_updater.py, 9 commits"),
    e9: evi("e9", "file", "File", "updated_devices.csv, 38 devices"), e10: evi("e10", "file", "File", "parse.py, 4 edits"),
  };
  const bullet = (id: string, text: string, conf: number, state: TruthState, ev: string[], weak = false): CVBullet => ({
    id, text, confidence: conf, state, weak, evidence: ev.map((k) => cvEv[k] as Evidence),
  });
  const cvVariants = (v: number): CV["experience"] => [
    {
      project: "Supervisor Platform", color: 0,
      bullets: v === 0
        ? [bullet("b-sup-1", "Designed and executed temperature testing workflows for edge devices.", 0.94, "confirmed", ["e1", "e2", "e3", "e5"]), bullet("b-sup-2", "Developed Python-based test automation with pytest.", 0.88, "confirmed", ["e2", "e3", "e4"])]
        : [bullet("b-sup-1", "Designed and executed temperature testing workflows for edge devices.", 0.94, "confirmed", ["e1", "e2", "e3", "e5"]), bullet("b-sup-3", "Validated temperature-related behavior across firmware builds, tracked in AI-1842.", 0.83, "inferred", ["e1", "e2", "e5"]), bullet("b-sup-4", "Built pytest suites covering sensor validation and result reporting.", 0.86, "inferred", ["e2", "e3", "e4"])],
    },
    {
      project: "Mobile AI", color: 1,
      bullets: v === 0
        ? [bullet("b-mob-1", "Automated camera regression checks across firmware builds.", 0.68, "inferred", ["e6", "e7"], true)]
        : [bullet("b-mob-1", "Automated camera regression checks across firmware builds.", 0.68, "inferred", ["e6", "e7"], true), bullet("b-mob-2", "Investigated a camera freeze reported in MAI-311.", 0.58, "inferred", ["e7"], true)],
    },
    {
      project: "Field Updates", color: 2,
      bullets: v === 0
        ? [bullet("b-fld-1", "Ran parallel firmware rollouts over SSH to TrueAI and MobilAI fleets.", 0.91, "confirmed", ["e8", "e9"])]
        : [bullet("b-fld-1", "Ran parallel firmware rollouts over SSH to TrueAI and MobilAI fleets.", 0.91, "confirmed", ["e8", "e9"]), bullet("b-fld-2", "Built a log parser that turns device .tm files into readable reports.", 0.79, "inferred", ["e10"])],
    },
  ];
  let cvVersion = 0;
  const buildCV = (generatedAt: string | null): CV => ({
    name: profile.name || "Your name", title: profile.job_title || "Your title",
    summary: "Test engineer working on edge AI devices. Builds Python test automation, investigates field issues and ships firmware updates to device fleets.",
    experience: cvExp, skills: ["Python", "Test automation", "pytest", "Git", "Embedded Linux", "Log analysis"], generated_at: generatedAt,
  });
  let cvExp = cvVariants(0);
  let cvGeneratedAt: string | null = isoLocal(new Date(started.getTime() - min(55)));

  // -- Profile / settings / status -------------------------------------------------
  let profile: Profile = opts.onboarding
    ? { name: "", job_title: "", focus: "", projects: [], tools: [], screen_understanding: false, autostart: true, ai_provider: "none", language: "en", setup_at: null }
    : { name: "Alex Morgan", job_title: "Test Engineer", focus: "Testing edge AI devices", projects: ["Supervisor", "Mobile AI", "Field Updates"], tools: ["VS Code", "Git", "Python", "Jira"], screen_understanding: false, autostart: true, ai_provider: "claude", language: "en", setup_at: isoLocal(new Date(started.getTime() - DAY * 3000)) };
  let settings: Settings = {
    general: { language: "en", timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
    collector: { interval: 5, idle_threshold: 300, repo_roots: ["~/Work"], excluded_apps: ["Banking", "KeePass"] },
    sessions: { split_gap: 300, switch_min: 120, min_session: 180 },
    privacy: { screen_understanding: false, browser_tracking: true, file_tracking: true },
    ai: { provider: "claude", model: "claude-sonnet-5-5", analysis_interval: 900, key_configured: true },
    server: { host: "127.0.0.1", port: 7342 },
  };
  let paused: Date | null = null;
  let stopped = false;
  const touched = new Map<string, string>();
  const touch = (id: string) => touched.set(id, isoLocal(now()));

  // -- Memory ----------------------------------------------------------------------
  function memoryItems(): MemoryItem[] {
    const items: MemoryItem[] = [];
    for (const p of projects)
      items.push({ id: `m-${p.id}`, type: "project", name: p.name, state: p.state, project: null, detail: `${formatHours(p.active_seconds)} · ${p.session_count} sessions`, updated_at: touched.get(p.id) ?? p.last_active ?? isoLocal(started) });
    for (const k of skills)
      items.push({ id: `m-${k.id}`, type: k.category === "Language" || k.category === "Tool" ? "technology" : "skill", name: k.name, state: k.state, project: k.projects[0] ?? null, detail: `${k.category} · ${Math.round(k.score)}`, updated_at: touched.get(k.id) ?? isoLocal(new Date(started.getTime() - DAY * 1000)) });
    for (const a of achievements)
      items.push({ id: `m-${a.id}`, type: "achievement", name: a.title, state: a.state, project: a.project?.name ?? null, detail: a.ticket ?? (a.on_cv ? "On CV" : "Achievement"), updated_at: touched.get(a.id) ?? a.created_at });
    const seen = new Set<string>();
    for (const key of [todayKey, addDays(todayKey, -1)])
      for (const s of ensureDay(key)) {
        if (s.is_open) continue;
        items.push({ id: `m-${s.id}`, type: "session", name: s.activity, state: s.state, project: s.project?.name ?? null, detail: `${formatTime(s.start)}–${formatTime(s.end)} · ${Math.round(s.active_seconds / 60)}m`, updated_at: touched.get(s.id) ?? s.end });
        for (const e of s.evidence)
          if (!seen.has(e.value) && e.type !== "user_confirmation") {
            seen.add(e.value);
            items.push({ id: `m-${e.id}`, type: "evidence", name: e.value, state: s.state === "rejected" ? "rejected" : "observed", project: s.project?.name ?? null, detail: e.label, updated_at: e.observed_at ?? s.end });
          }
      }
    return items.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  }

  function status(): Status {
    if (paused && paused <= now()) paused = null;
    const live = [...sessions.values()].find((s) => s.is_open);
    const mem = memoryItems();
    return {
      version: "0.1.0", platform: "Linux", state: stopped ? "stopped" : paused ? "paused" : "running", pid: stopped ? null : 4182,
      uptime_seconds: stopped ? null : Math.round((now().getTime() - started.getTime()) / 1000) + 5 * 3600 + 412, paused_until: paused ? isoLocal(paused) : null,
      events_today: opts.empty ? 0 : 1284, sessions_today: ensureDay(todayKey).length, review_count: reviews.length,
      memory_count: mem.filter((m) => m.state === "confirmed" || m.state === "observed").length,
      current: live && !paused ? { application: "VS Code", title: "test_camera.py", project: live.project?.name ?? null, since: live.start } : null,
      ai: { provider: settings.ai.provider, available: true, pending_sessions: 0 },
      learning: { active: !opts.empty, day: opts.empty ? 1 : 3, days_total: 7 },
      profile_complete: profile.setup_at != null,
    };
  }

  // -- Mutations -------------------------------------------------------------------
  function removeReview(refId: string) {
    const i = reviews.findIndex((r) => r.ref_id === refId);
    if (i >= 0) reviews.splice(i, 1);
  }
  function reviewSession(id: string, body: { action: string; activity?: string; project_id?: string; skills?: string[] }): Session {
    const s = sessions.get(id);
    if (!s) throw new MockHttpError(404, "Session not found");
    if (body.action === "confirm") {
      s.state = "confirmed";
      s.confidence = Math.max(s.confidence, 0.9);
    } else if (body.action === "reject") s.state = "rejected";
    else if (body.action === "edit") {
      if (body.activity) s.activity = body.activity;
      if (body.project_id) s.project = refOf(body.project_id);
      if (body.skills) s.skills = body.skills;
      s.state = "confirmed";
    } else throw new MockHttpError(422, "Unknown action");
    if (s.state === "confirmed")
      s.evidence = [...s.evidence, { id: `ev-${s.id}-uc`, type: "user_confirmation", label: "You", value: "Confirmed by you", observed_at: isoLocal(now()), session_id: s.id }];
    touch(s.id);
    removeReview(s.id);
    return s;
  }
  function reviewItem(id: string, body: { action: string; title?: string; answer?: string }) {
    const item = reviews.find((r) => r.id === id);
    if (!item) throw new MockHttpError(404, "Review item not found");
    const accept = body.action === "confirm" || body.action === "edit" || (body.action === "answer" && /^y/i.test(body.answer ?? ""));
    const state: TruthState = accept ? "confirmed" : "rejected";
    if (body.action === "answer" && item.kind === "question" && accept) {
      const p = projects.find((x) => x.id === item.project?.id);
      if (p) p.state = "confirmed";
    }
    if (item.kind === "session") {
      reviewSession(item.ref_id, body.action === "edit" ? { action: "edit", activity: body.title } : { action: state === "confirmed" ? "confirm" : "reject" });
    } else if (item.kind === "achievement") {
      const a = achievements.find((x) => x.id === item.ref_id);
      if (a) {
        a.state = state;
        if (body.title) a.title = body.title;
        touch(a.id);
      }
    } else if (item.kind === "skill") {
      const k = skills.find((x) => x.id === item.ref_id);
      if (k) k.state = state;
    } else if (item.kind === "project") {
      const p = projects.find((x) => x.id === item.ref_id);
      if (p) p.state = state;
    }
    removeReview(item.ref_id);
    const i = reviews.findIndex((r) => r.id === id);
    if (i >= 0) reviews.splice(i, 1);
    return { ok: true as const, remaining: reviews.length };
  }

  // -- Aggregates ------------------------------------------------------------------
  const summary = (k: Skill): SkillSummary => ({ name: k.name, score: k.score, delta: Math.round(k.score - k.previous_score) });
  function today(key: string): Today {
    liveSync();
    const list = ensureDay(key).filter((s) => s.state !== "rejected");
    const mondayOffset = (parseDateKey(key).getDay() + 6) % 7;
    const monday = addDays(key, -mondayOffset);
    const week = Array.from({ length: 7 }, (_, i) => {
      const d = addDays(monday, i);
      return { date: d, active_seconds: d > todayKey ? 0 : activeOn(d) };
    });
    return {
      date: key, name: profile.name.split(" ")[0] || null, active_seconds: list.reduce((a, s) => a + s.active_seconds, 0), session_count: list.length,
      project_count: new Set(list.map((s) => s.project?.id).filter(Boolean)).size,
      ribbon: list.map((s) => ({ start: s.start, end: s.end, color: s.project?.color ?? null, label: s.activity })),
      current_session: key === todayKey ? (list.find((s) => s.is_open) ?? null) : null, review_count: reviews.length,
      top_skills: [...skills].sort((a, b) => b.score - a.score).slice(0, 4).map(summary), week, week_total_seconds: week.reduce((a, d) => a + d.active_seconds, 0),
      potential_achievements: achievements.filter((a) => a.state === "inferred").slice(0, 3),
    };
  }
  function insights(period: "week" | "month"): Insights {
    liveSync();
    const n = period === "week" ? 7 : 30;
    const start = addDays(todayKey, -(n - 1));
    const days = Array.from({ length: n }, (_, i) => addDays(start, i));
    const list = days.flatMap((d) => ensureDay(d)).filter((s) => s.state !== "rejected");
    const total = list.reduce((a, s) => a + s.active_seconds, 0);
    const byProject = new Map<string, { name: string; color: number; seconds: number }>();
    const byActivity = new Map<string, { name: string; seconds: number; count: number }>();
    for (const s of list) {
      const p = s.project;
      if (p) {
        const cur = byProject.get(p.id) ?? { name: p.name, color: p.color, seconds: 0 };
        cur.seconds += s.active_seconds;
        byProject.set(p.id, cur);
      }
      const a = byActivity.get(s.activity) ?? { name: s.activity, seconds: 0, count: 0 };
      a.seconds += s.active_seconds;
      a.count += 1;
      byActivity.set(s.activity, a);
    }
    const testing = list.filter((s) => s.category === "Testing" && s.project?.id === "p-supervisor").length;
    const lastLogs = parseDateKey(addDays(todayKey, -14)).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    return {
      period, start, end: todayKey, active_seconds: total, session_count: list.length,
      projects: [...byProject.values()].sort((a, b) => b.seconds - a.seconds).map((p) => ({ ...p, share: total ? p.seconds / total : 0 })),
      top_activities: [...byActivity.values()].sort((a, b) => b.seconds - a.seconds).slice(0, 4),
      skills_up: skills.filter((k) => k.score > k.previous_score).sort((a, b) => b.score - b.previous_score - (a.score - a.previous_score)).slice(0, 4).map(summary),
      skills_down: skills.filter((k) => k.score < k.previous_score).map(summary),
      achievements: achievements.filter((a) => a.state !== "rejected" && a.created_at.slice(0, 10) >= (period === "week" ? start : addDays(todayKey, -29))),
      repeated: testing ? [`${testing} testing sessions on Supervisor`, `Python in ${Math.max(1, list.filter((s) => s.skills.includes("Python")).length)} sessions`] : [],
      stopped: period === "month" ? [`No Log Parser work since ${lastLogs}`] : [],
      cv_candidates: cvExp.flatMap((e) => e.bullets).filter((b) => b.state === "inferred").length,
      by_day: days.map((d) => ({ date: d, active_seconds: activeOn(d) })),
    };
  }
  function projectDetail(id: string) {
    const p = projects.find((x) => x.id === id);
    if (!p) throw new MockHttpError(404, "Project not found");
    const recent = Array.from({ length: 5 }, (_, i) => ensureDay(addDays(todayKey, -i))).flat().filter((s) => s.project?.id === id && s.state !== "rejected");
    return { ...p, sessions: recent.slice().reverse(), achievements: achievements.filter((a) => a.project?.id === id) };
  }

  // -- Router ----------------------------------------------------------------------
  function handle(method: string, url: string, body: any): unknown {
    const u = new URL(url, "http://mock.local");
    const path = u.pathname.replace(/^\/api/, "");
    const q = u.searchParams;
    const m = (re: RegExp) => re.exec(path);
    let r: RegExpExecArray | null;
    const key = q.get("date") || todayKey;

    if (path === "/status" && method === "GET") return status();
    if (path === "/agent/pause" && method === "POST") {
      paused = new Date(now().getTime() + min(Number(body?.minutes) || 60));
      stopped = false;
      return status();
    }
    if (path === "/agent/resume" && method === "POST") {
      paused = null;
      stopped = false;
      return status();
    }
    if (path === "/today" && method === "GET") return today(key);
    if (path === "/sessions" && method === "GET") {
      liveSync();
      return { date: key, sessions: ensureDay(key) };
    }
    if ((r = m(/^\/sessions\/([^/]+)$/)) && method === "GET") {
      liveSync();
      const s = sessions.get(r[1] as string);
      if (!s) throw new MockHttpError(404, "Session not found");
      return { ...s, raw_events: rawBySession.get(s.id) ?? [] };
    }
    if ((r = m(/^\/sessions\/([^/]+)\/review$/)) && method === "POST") return reviewSession(r[1] as string, body);
    if (path === "/review" && method === "GET") return { items: reviews };
    if ((r = m(/^\/review\/([^/]+)$/)) && method === "POST") return reviewItem(r[1] as string, body);
    if (path === "/projects" && method === "GET") return { projects };
    if ((r = m(/^\/projects\/([^/]+)\/merge$/)) && method === "POST") {
      const from = projects.find((x) => x.id === r?.[1]);
      const into = projects.find((x) => x.id === body?.into_id);
      if (!from || !into || from === into) throw new MockHttpError(422, "Pick another project to merge into");
      into.active_seconds += from.active_seconds;
      into.session_count += from.session_count;
      into.achievement_count += from.achievement_count;
      into.aliases = [...new Set([...into.aliases, ...from.aliases, from.name])];
      into.tickets = [...new Set([...into.tickets, ...from.tickets])];
      into.repos = [...new Set([...into.repos, ...from.repos])];
      into.skills = [...new Set([...into.skills, ...from.skills])];
      into.sparkline = into.sparkline.map((v, i) => v + (from.sparkline[i] ?? 0));
      for (const s of sessions.values()) if (s.project?.id === from.id) s.project = refOf(into.id);
      for (const a of achievements) if (a.project?.id === from.id) a.project = refOf(into.id);
      projects.splice(projects.indexOf(from), 1);
      touch(into.id);
      return into;
    }
    if ((r = m(/^\/projects\/([^/]+)$/))) {
      if (method === "GET") return projectDetail(r[1] as string);
      if (method === "PATCH") {
        const p = projects.find((x) => x.id === r?.[1]);
        if (!p) throw new MockHttpError(404, "Project not found");
        if (body?.name) p.name = String(body.name);
        if (body?.state) p.state = body.state;
        touch(p.id);
        for (const s of sessions.values()) if (s.project?.id === p.id) s.project = refOf(p.id);
        for (const a of achievements) if (a.project?.id === p.id) a.project = refOf(p.id);
        return p;
      }
    }
    if (path === "/skills" && method === "GET") return { skills };
    if ((r = m(/^\/skills\/([^/]+)$/)) && method === "PATCH") {
      const k = skills.find((x) => x.id === r?.[1]);
      if (!k) throw new MockHttpError(404, "Skill not found");
      k.state = body.state;
      touch(k.id);
      return k;
    }
    if (path === "/achievements" && method === "GET") return { achievements };
    if ((r = m(/^\/achievements\/([^/]+)$/)) && method === "PATCH") {
      const a = achievements.find((x) => x.id === r?.[1]);
      if (!a) throw new MockHttpError(404, "Achievement not found");
      if (body.title != null) a.title = body.title;
      if (body.state != null) {
        a.state = body.state;
        removeReview(a.id);
      }
      if ("impact" in body) a.impact = body.impact ? String(body.impact).trim() || null : null;
      if (body.on_cv != null) a.on_cv = !!body.on_cv;
      touch(a.id);
      return a;
    }
    if (path === "/memory" && method === "GET") {
      const type = q.get("type");
      const state = q.get("state");
      const byType = memoryItems().filter((i) => !type || i.type === type);
      const counts: Record<TruthState, number> = { observed: 0, inferred: 0, confirmed: 0, rejected: 0 };
      for (const i of byType) counts[i.state] += 1;
      return { items: byType.filter((i) => !state || i.state === state), counts };
    }
    if (path === "/insights" && method === "GET") return insights(q.get("period") === "month" ? "month" : "week");
    if (path === "/cv" && method === "GET") return buildCV(cvGeneratedAt);
    if (path === "/cv/regenerate" && method === "POST") {
      cvVersion = (cvVersion + 1) % 2;
      cvExp = cvVariants(cvVersion);
      cvGeneratedAt = isoLocal(now());
      return buildCV(cvGeneratedAt);
    }
    if ((r = m(/^\/cv\/bullets\/([^/]+)$/)) && method === "PATCH") {
      const b = cvExp.flatMap((e) => e.bullets).find((x) => x.id === r?.[1]);
      if (!b) throw new MockHttpError(404, "Bullet not found");
      b.text = String(body.text);
      b.state = "confirmed";
      return buildCV(cvGeneratedAt);
    }
    if (path === "/profile" && method === "GET") return profile;
    if (path === "/profile" && method === "PUT") {
      profile = { ...body, setup_at: profile.setup_at ?? isoLocal(now()) };
      settings.ai.provider = profile.ai_provider;
      return profile;
    }
    if (path === "/settings" && method === "GET") return settings;
    if (path === "/settings" && method === "PUT") {
      settings = body;
      return settings;
    }
    if (path === "/analyze" && method === "POST") return { analyzed: 0, pending: 0 };
    throw new MockHttpError(404, `No mock for ${method} ${path}`);
  }

  return {
    setOffline(v: boolean) {
      offline = v;
    },
    async request<T>(method: string, url: string, body?: unknown): Promise<T> {
      if (latency) await new Promise((res) => setTimeout(res, latency));
      if (offline) throw new MockUnreachable("offline");
      return structuredClone(handle(method, url, body)) as T;
    },
  };
}

export type MockApi = ReturnType<typeof createMockApi>;
