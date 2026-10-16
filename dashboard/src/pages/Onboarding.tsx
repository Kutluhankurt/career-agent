import { useEffect, useState, type KeyboardEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { errorMessage } from "../api/client";
import { useProfile, useSaveProfile } from "../api/hooks";
import type { Profile } from "../api/types";
import { useCopy } from "../lib/hooks";

const TOOLS = ["VS Code", "Git", "Python", "Jira", "Terminal", "Excel", "Slack", "Docker", "Confluence", "Figma", "PyCharm", "Chrome"];
const PROVIDERS: { value: Profile["ai_provider"]; label: string; hint: string }[] = [
  { value: "claude", label: "Claude", hint: "Anthropic" },
  { value: "gemini", label: "Gemini", hint: "Google" },
  { value: "openai", label: "OpenAI", hint: "GPT" },
  { value: "local", label: "Local", hint: "On this computer" },
  { value: "none", label: "Skip for now", hint: "Collect offline" },
];
const EMPTY: Profile = { name: "", job_title: "", focus: "", projects: [], tools: [], screen_understanding: false, autostart: true, ai_provider: "none", language: "en", setup_at: null };
const EASE = [0.25, 1, 0.5, 1] as const;
const STEPS = ["welcome", "privacy", "role", "focus", "projects", "tools", "ai", "start"] as const;
type Step = (typeof STEPS)[number];

function Chips({ values, onChange, placeholder }: { values: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [text, setText] = useState("");
  const add = () => {
    const v = text.trim().replace(/,$/, "").trim();
    if (v && !values.some((x) => x.toLowerCase() === v.toLowerCase())) onChange([...values, v]);
    setText("");
  };
  return (
    <>
      <input
        className="field onb-input"
        autoFocus
        aria-label={placeholder}
        placeholder={placeholder}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
          if (e.key === "," || (e.key === "Enter" && text.trim())) {
            e.preventDefault();
            e.stopPropagation();
            add();
          }
          if (e.key === "Backspace" && !text && values.length) onChange(values.slice(0, -1));
        }}
        onBlur={add}
      />
      <div className="tags" style={{ marginTop: 16 }}>
        {values.map((v) => (
          <button key={v} className="tagc removable" onClick={() => onChange(values.filter((x) => x !== v))} aria-label={`Remove ${v}`}>
            {v} <span aria-hidden>✕</span>
          </button>
        ))}
      </div>
    </>
  );
}

export default function Onboarding() {
  const existing = useProfile().data;
  const save = useSaveProfile();
  const [copied, copy] = useCopy();
  const [p, setP] = useState<Profile>(EMPTY);
  const [i, setI] = useState(0);
  const [dir, setDir] = useState(1);
  const [custom, setCustom] = useState("");
  const [error, setError] = useState<string | null>(null);
  const step: Step = STEPS[i] ?? "welcome";

  useEffect(() => {
    if (existing) setP((cur) => (cur === EMPTY ? { ...existing } : cur));
  }, [existing]);

  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP((cur) => ({ ...cur, [k]: v }));
  const valid = step === "role" ? p.name.trim().length > 0 : true;
  const go = (n: number) => {
    setDir(n > 0 ? 1 : -1);
    setI((x) => Math.min(STEPS.length - 1, Math.max(0, x + n)));
  };
  const finish = () => {
    setError(null);
    save.mutate({ ...p, name: p.name.trim(), setup_at: new Date().toISOString() }, { onError: (e) => setError(errorMessage(e)) });
  };
  const next = () => (step === "start" ? finish() : valid && go(1));

  useEffect(() => {
    const key = (e: globalThis.KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === "Escape") return go(-1);
      if (e.key === "Enter" && t.tagName !== "BUTTON" && t.tagName !== "TEXTAREA" && !(t.tagName === "INPUT" && step === "projects" && (t as HTMLInputElement).value.trim())) next();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  });

  const body: Record<Step, JSX.Element> = {
    welcome: (
      <>
        <h1>Your work, remembered.</h1>
        <p className="lede">Career Agent quietly turns your daily work into a career record. Everything stays on this computer.</p>
      </>
    ),
    privacy: (
      <>
        <h1>What I see, and what I never do.</h1>
        <div className="promise">
          <div>
            <h3>I notice</h3>
            <ul className="plain"><li>Which apps and windows are in use</li><li>File names you work on</li><li>Git commits and ticket IDs</li><li>Terminal command names</li></ul>
          </div>
          <div>
            <h3>I never record</h3>
            <ul className="plain"><li>Keystrokes</li><li>Passwords</li><li>Screenshots</li><li>Microphone or camera</li></ul>
          </div>
        </div>
        <p className="meta">Pause any time from the top bar. Fine-tune it later in Settings.</p>
      </>
    ),
    role: (
      <>
        <h1>What should I call you?</h1>
        <input className="field onb-input" autoFocus aria-label="Your name" placeholder="Your name" value={p.name} onChange={(e) => set("name", e.target.value)} />
        <input className="field onb-input" aria-label="Your role" placeholder="Your role, for example Test Engineer" value={p.job_title} onChange={(e) => set("job_title", e.target.value)} style={{ marginTop: 12 }} />
      </>
    ),
    focus: (
      <>
        <h1>What do you mainly work on?</h1>
        <input className="field onb-input" autoFocus aria-label="Your focus" placeholder="For example, testing edge AI devices" value={p.focus} onChange={(e) => set("focus", e.target.value)} />
      </>
    ),
    projects: (
      <>
        <h1>Which projects are you on?</h1>
        <p className="lede">Type a name and press Enter. You can skip this; I'll find them from your work.</p>
        <Chips values={p.projects} onChange={(v) => set("projects", v)} placeholder="Add a project" />
      </>
    ),
    tools: (
      <>
        <h1>What do you use?</h1>
        <div className="tags big-tags">
          {[...TOOLS, ...p.tools.filter((t) => !TOOLS.includes(t))].map((t) => {
            const on = p.tools.includes(t);
            return (
              <button key={t} className={`chip ${on ? "on" : ""}`} aria-pressed={on} onClick={() => set("tools", on ? p.tools.filter((x) => x !== t) : [...p.tools, t])}>{t}</button>
            );
          })}
        </div>
        <input
          className="field onb-input"
          aria-label="Add another tool"
          placeholder="Add another"
          value={custom}
          style={{ marginTop: 24 }}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && custom.trim()) {
              e.stopPropagation();
              const v = custom.trim();
              if (!p.tools.includes(v)) set("tools", [...p.tools, v]);
              setCustom("");
            }
          }}
        />
      </>
    ),
    ai: (
      <>
        <h1>Who should help understand your work?</h1>
        <div className="choices" role="radiogroup" aria-label="AI provider">
          {PROVIDERS.map((o) => (
            <button key={o.value} role="radio" aria-checked={p.ai_provider === o.value} className={`choice ${p.ai_provider === o.value ? "on" : ""}`} onClick={() => set("ai_provider", o.value)}>
              <b>{o.label}</b>
              <span className="meta">{o.hint}</span>
            </button>
          ))}
        </div>
        {p.ai_provider !== "none" && p.ai_provider !== "local" && (
          <p className="meta" style={{ marginTop: 20 }}>
            Keys never go through this page. Add yours from a terminal; it goes to your system keychain.{" "}
            <span className="cmd inline"><code>career config ai</code><button className="link" onClick={() => copy("career config ai")}>{copied ? "Copied" : "Copy"}</button></span>
          </p>
        )}
      </>
    ),
    start: (
      <>
        <h1>You're all set{p.name ? `, ${p.name.split(" ")[0]}` : ""}.</h1>
        <p className="lede">I'll watch quietly and ask a few questions in the first week.</p>
        <div className="card slist" style={{ maxWidth: 460, margin: "0 auto 8px", textAlign: "left" }}>
          <div className="srow">
            <div className="grow"><div className="sl">Open at login</div><div className="meta">Start recording when you sign in.</div></div>
            <button role="switch" aria-checked={p.autostart} aria-label="Open at login" className={`switch ${p.autostart ? "on" : ""}`} onClick={() => set("autostart", !p.autostart)}><i /></button>
          </div>
        </div>
        {error && <p className="err" role="alert">{error}</p>}
      </>
    ),
  };

  return (
    <div className="onb">
      <div className="onb-brand">Career Agent</div>
      <div className="onb-stage">
        <AnimatePresence mode="wait" custom={dir} initial={false}>
          <motion.section
            key={step}
            className="onb-step"
            custom={dir}
            variants={{
              in: (d: number) => ({ opacity: 0, x: 40 * d }),
              show: { opacity: 1, x: 0, transition: { duration: 0.5, ease: EASE } },
              out: (d: number) => ({ opacity: 0, x: -40 * d, transition: { duration: 0.2 } }),
            }}
            initial="in"
            animate="show"
            exit="out"
          >
            {body[step]}
          </motion.section>
        </AnimatePresence>
      </div>
      <div className="onb-foot">
        <div className="onb-nav">
          {i > 0 ? <button className="pill" onClick={() => go(-1)}>Back</button> : <span />}
          <button className="pill primary big" disabled={!valid || save.isPending} onClick={next}>
            {step === "welcome" ? "Get started" : step === "start" ? (save.isPending ? "Starting…" : "Start") : step === "projects" && !p.projects.length ? "Skip" : "Continue"}
          </button>
        </div>
        <div className="dots" aria-label={`Step ${i + 1} of ${STEPS.length}`} role="img">
          {STEPS.map((s, k) => <i key={s} className={k < i ? "d" : k === i ? "c" : ""} />)}
        </div>
      </div>
    </div>
  );
}
