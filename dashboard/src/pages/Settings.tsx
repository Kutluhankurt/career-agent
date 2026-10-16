import { useState, type ReactNode } from "react";
import { errorMessage } from "../api/client";
import { useAnalyze, useSaveSettings, useSettings, useStatus } from "../api/hooks";
import type { Settings } from "../api/types";
import { Segmented, ErrorNote, Page, Skeleton } from "../components/ui";
import { useToast } from "../components/Toast";
import { getTheme, setTheme, useCopy, type ThemeChoice } from "../lib/hooks";
import { formatDuration } from "../lib/format";

function Group({ title, children, footer }: { title: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <section className="sgroup in">
      <h2 className="stitle">{title}</h2>
      <div className="card slist">{children}</div>
      {footer && <p className="sfoot">{footer}</p>}
    </section>
  );
}

function Row({ label, hint, children }: { label: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="srow">
      <div className="grow">
        <div className="sl">{label}</div>
        {hint && <div className="meta">{hint}</div>}
      </div>
      {children}
    </div>
  );
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} className={`switch ${on ? "on" : ""}`} onClick={() => onChange(!on)}>
      <i />
    </button>
  );
}

function Stepper({ value, onChange, step = 60, min = 60, max = 3600, label }: { value: number; onChange: (v: number) => void; step?: number; min?: number; max?: number; label: string }) {
  return (
    <div className="stepper" role="group" aria-label={label}>
      <button aria-label={`Decrease ${label}`} disabled={value <= min} onClick={() => onChange(Math.max(min, value - step))}>−</button>
      <span className="num">{formatDuration(value)}</span>
      <button aria-label={`Increase ${label}`} disabled={value >= max} onClick={() => onChange(Math.min(max, value + step))}>+</button>
    </div>
  );
}

function Cmd({ cmd }: { cmd: string }) {
  const [copied, copy] = useCopy();
  return (
    <span className="cmd">
      <code>{cmd}</code>
      <button className="link" onClick={() => copy(cmd)}>{copied ? "Copied" : "Copy"}</button>
    </span>
  );
}

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export default function SettingsPage() {
  const q = useSettings();
  const status = useStatus().data;
  const save = useSaveSettings();
  const analyze = useAnalyze();
  const { show } = useToast();
  const [theme, setThemeState] = useState<ThemeChoice>(getTheme);

  if (q.isError) return <ErrorNote error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data)
    return (
      <Page title="Settings">
        <div aria-busy="true" aria-label="Loading">{[0, 1, 2].map((i) => <div key={i} className="card" style={{ marginBottom: 28 }}><Skeleton h={90} r={12} /></div>)}</div>
      </Page>
    );
  const s = q.data;
  const update = (next: Settings) => save.mutate(next, { onError: (e) => show(errorMessage(e)) });
  const privacy = (k: keyof Settings["privacy"], v: boolean) => update({ ...s, privacy: { ...s.privacy, [k]: v } });
  const provider = s.ai.provider === "none" ? "None" : s.ai.provider[0]?.toUpperCase() + s.ai.provider.slice(1);

  return (
    <Page eyebrow="Settings" title="Settings." lede="Everything stays on this computer. Change what is recorded, any time.">
      <Group title="Appearance">
        <Row label="Theme" hint="Follows your system unless you choose.">
          <Segmented<ThemeChoice> label="Theme" value={theme} options={THEMES} onChange={(t) => { setTheme(t); setThemeState(t); }} />
        </Row>
      </Group>

      <Group title="Tracking & Privacy" footer="Keystrokes, passwords, screenshots, microphone and camera are never recorded.">
        <Row label="Files" hint="Notes which files you work on, by name.">
          <Toggle label="Files" on={s.privacy.file_tracking} onChange={(v) => privacy("file_tracking", v)} />
        </Row>
        <Row label="Browser" hint="Notes the pages and tickets you visit, by title.">
          <Toggle label="Browser" on={s.privacy.browser_tracking} onChange={(v) => privacy("browser_tracking", v)} />
        </Row>
        <Row label="Screen understanding" hint="Off by default. Lets the agent look at what's on screen to understand your work.">
          <Toggle label="Screen understanding" on={s.privacy.screen_understanding} onChange={(v) => privacy("screen_understanding", v)} />
        </Row>
        <Row label="Skipped apps" hint={s.collector.excluded_apps.length ? s.collector.excluded_apps.join(", ") : "None"} />
      </Group>

      <Group title="AI" footer="Keys are never typed here. They are stored in your system keychain from the terminal.">
        <Row label="Provider" hint={status && !status.ai.available && s.ai.provider !== "none" ? "Offline right now. Collection continues." : undefined}><span className="val">{provider}</span></Row>
        <Row label="Model"><span className="val">{s.ai.model || "Default"}</span></Row>
        <Row label="Key"><span className="val" style={{ color: s.ai.key_configured ? "var(--green)" : "var(--muted)" }}>{s.ai.key_configured ? "Key configured" : "No key set"}</span></Row>
        <Row label="Set or change the key"><Cmd cmd="career config ai" /></Row>
        <Row label="Analyze every" hint="How often new sessions are sent for understanding.">
          <Stepper label="analysis interval" value={s.ai.analysis_interval} step={300} min={300} max={7200} onChange={(v) => update({ ...s, ai: { ...s.ai, analysis_interval: v } })} />
        </Row>
        <Row label="Analyze now" hint={status ? `${status.ai.pending_sessions} waiting` : undefined}>
          <button className="pill" disabled={analyze.isPending} onClick={() => analyze.mutate(undefined, { onSuccess: (r) => show(r.analyzed ? `Analyzed ${r.analyzed} ${r.analyzed === 1 ? "session" : "sessions"}` : "Nothing waiting"), onError: (e) => show(errorMessage(e)) })}>
            {analyze.isPending ? "Analyzing…" : "Analyze"}
          </button>
        </Row>
      </Group>

      <Group title="Sessions" footer="How the agent decides where one piece of work ends and the next begins.">
        <Row label="New session after a break of" hint="A gap this long starts a new session.">
          <Stepper label="split gap" value={s.sessions.split_gap} onChange={(v) => update({ ...s, sessions: { ...s.sessions, split_gap: v } })} />
        </Row>
        <Row label="Switch counts after" hint="Quick glances at another app don't split a session.">
          <Stepper label="switch minimum" value={s.sessions.switch_min} onChange={(v) => update({ ...s, sessions: { ...s.sessions, switch_min: v } })} />
        </Row>
        <Row label="Shortest session" hint="Anything briefer is folded into its neighbours.">
          <Stepper label="shortest session" value={s.sessions.min_session} onChange={(v) => update({ ...s, sessions: { ...s.sessions, min_session: v } })} />
        </Row>
        <Row label="Idle after" hint="No activity for this long counts as idle.">
          <Stepper label="idle threshold" value={s.collector.idle_threshold} onChange={(v) => update({ ...s, collector: { ...s.collector, idle_threshold: v } })} />
        </Row>
      </Group>

      <Group title="Data" footer="Nothing leaves this computer unless you export it.">
        <Row label="Export everything" hint="Writes your career memory to a file."><Cmd cmd="career export" /></Row>
        <Row label="Back up" hint="Saves a copy of the local database."><Cmd cmd="career backup" /></Row>
      </Group>

      <Group title="About">
        <Row label="Version"><span className="val num">{status?.version ?? "–"}</span></Row>
        <Row label="Platform"><span className="val">{status?.platform ?? "–"}</span></Row>
        <Row label="Address"><span className="val num">{s.server.host}:{s.server.port}</span></Row>
        <Row label="Time zone"><span className="val">{s.general.timezone}</span></Row>
      </Group>
    </Page>
  );
}
