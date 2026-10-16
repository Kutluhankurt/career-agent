import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { errorMessage } from "../api/client";
import { useAchievements, useMemory, useMergeProject, usePatchAchievement, usePatchProject, usePatchSkill, useProject, useProjects, useSkills } from "../api/hooks";
import type { Achievement, MemoryItem, Project, Skill, TruthState } from "../api/types";
import { LineChart, Sparkline } from "../components/charts";
import { Sheet, Stagger } from "../components/Sheet";
import { useToast } from "../components/Toast";
import { Confidence, Dot, EmptyState, ErrorNote, Page, Segmented, Skeleton, TruthBadge } from "../components/ui";
import { flyToMemory } from "../lib/fly";
import { useLast } from "../lib/hooks";
import { formatDuration, formatHours, formatRange, plural, projectColor, relativeTime, stateLabel } from "../lib/format";

type Tab = "projects" | "skills" | "achievements" | "everything";
const TABS: { value: Tab; label: string }[] = [
  { value: "projects", label: "Projects" },
  { value: "skills", label: "Skills" },
  { value: "achievements", label: "Achievements" },
  { value: "everything", label: "Everything" },
];

const EASE = [0.25, 1, 0.5, 1] as const;

function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="card" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} style={{ padding: "14px 0" }}><Skeleton w={`${50 + ((i * 17) % 40)}%`} h={18} /></div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Projects */

function ProjectSheet({ project, projects, onClose }: { project: Project; projects: Project[]; onClose: () => void }) {
  const detail = useProject(project.id);
  const patch = usePatchProject();
  const merge = useMergeProject();
  const { show } = useToast();
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(project.name);
  const [mergeInto, setMergeInto] = useState("");
  const [error, setError] = useState<string | null>(null);
  const others = projects.filter((p) => p.id !== project.id && p.state !== "rejected");
  const fail = (e: unknown) => setError(errorMessage(e));

  return (
    <Stagger>
      {[
        <div key="h">
          <TruthBadge state={project.state} />
          {renaming ? (
            <div className="row-flex" style={{ marginTop: 14 }}>
              <input className="field" aria-label="Project name" autoFocus value={name} onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) patch.mutate({ id: project.id, name: name.trim() }, { onSuccess: () => { setRenaming(false); show("Renamed"); }, onError: fail }); }} />
              <button className="pill primary" disabled={!name.trim() || patch.isPending} onClick={() => patch.mutate({ id: project.id, name: name.trim() }, { onSuccess: () => { setRenaming(false); show("Renamed"); }, onError: fail })}>Save</button>
            </div>
          ) : (
            <h3>{project.name}</h3>
          )}
          <div className="meta" style={{ color: projectColor(project.color), fontWeight: 500 }}>
            {formatHours(project.active_seconds)} · {plural(project.session_count, "session")}
          </div>
        </div>,
        <div key="sp" className="grp"><div className="lbl">Last 30 days</div><Sparkline values={project.sparkline} color={projectColor(project.color)} width={360} height={56} /></div>,
        project.skills.length > 0 && (
          <div key="sk" className="grp"><div className="lbl">Skills</div><div className="tags">{project.skills.map((s) => <span key={s} className="tagc">{s}</span>)}</div></div>
        ),
        (project.tickets.length > 0 || project.repos.length > 0) && (
          <div key="tr" className="grp">
            <div className="lbl">Connected to</div>
            <div className="list">
              {project.tickets.map((t) => <div key={t}><span>{t}</span><span className="k">Ticket</span></div>)}
              {project.repos.map((r) => <div key={r}><span>{r}</span><span className="k">Repo</span></div>)}
            </div>
          </div>
        ),
        <div key="ss" className="grp">
          <div className="lbl">Recent sessions</div>
          {detail.isLoading && <Skeleton h={48} r={14} />}
          {detail.data && detail.data.sessions.length === 0 && <p className="meta">No recent sessions.</p>}
          {detail.data && detail.data.sessions.length > 0 && (
            <div className="list">
              {detail.data.sessions.slice(0, 5).map((s) => <div key={s.id}><span>{s.activity}</span><span className="k num">{formatRange(s.start, s.end)}</span></div>)}
            </div>
          )}
        </div>,
        detail.data && detail.data.achievements.length > 0 && (
          <div key="ac" className="grp"><div className="lbl">Achievements</div>
            <div className="list">{detail.data.achievements.map((a) => <div key={a.id}><span>{a.title}</span></div>)}</div>
          </div>
        ),
        <div key="ac2" className="grp">
          {error && <p className="err" role="alert">{error}</p>}
          <div className="acts" style={{ marginTop: 8 }}>
            {project.state !== "confirmed" && <button className="pill primary" onClick={() => patch.mutate({ id: project.id, state: "confirmed" }, { onSuccess: () => show("Project confirmed"), onError: fail })}>Confirm</button>}
            {!renaming && <button className="pill" onClick={() => setRenaming(true)}>Rename</button>}
            <button className="pill" onClick={() => patch.mutate({ id: project.id, state: "rejected" }, { onSuccess: () => { show("Marked as not a project"); onClose(); }, onError: fail })}>Not a project</button>
          </div>
          {others.length > 0 && (
            <div style={{ marginTop: 28 }}>
              <div className="lbl">Merge into</div>
              <div className="row-flex">
                <select className="field" aria-label="Merge into" value={mergeInto} onChange={(e) => setMergeInto(e.target.value)}>
                  <option value="">Choose a project</option>
                  {others.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <button className="pill" disabled={!mergeInto || merge.isPending} onClick={() => merge.mutate({ id: project.id, into_id: mergeInto }, { onSuccess: () => { show("Projects merged"); onClose(); }, onError: fail })}>Merge</button>
              </div>
              {mergeInto && <p className="meta" style={{ marginTop: 8 }}>Sessions, skills and achievements move to the other project. This can't be undone.</p>}
            </div>
          )}
        </div>,
      ].filter(Boolean) as JSX.Element[]}
    </Stagger>
  );
}

function ProjectsTab() {
  const q = useProjects();
  const [openId, setOpenId] = useState<string | null>(null);
  const close = useCallback(() => setOpenId(null), []);
  const list = useMemo(() => (q.data?.projects ?? []).filter((p) => p.state !== "rejected").sort((a, b) => b.active_seconds - a.active_seconds), [q.data]);
  const selected = list.find((p) => p.id === openId) ?? null;
  const shown = useLast(selected);
  if (q.isError) return <ErrorNote error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <div className="pgrid">{[0, 1, 2].map((i) => <div key={i} className="card"><Skeleton w="50%" h={20} /><Skeleton h={32} style={{ margin: "18px 0" }} /><Skeleton w="70%" h={14} /></div>)}</div>;
  if (!list.length) return <EmptyState title="No projects yet.">They appear as I recognise the repos and tickets you work on.</EmptyState>;
  return (
    <>
      <div className="pgrid in">
        {list.map((p) => (
          <button key={p.id} className="card pcard" onClick={() => setOpenId(p.id)}>
            <span className="row-flex" style={{ justifyContent: "space-between" }}>
              <b className="ptitle"><Dot color={projectColor(p.color)} /> {p.name}</b>
              {p.state === "inferred" && <TruthBadge state="inferred" />}
            </span>
            <span className="meta num">{formatHours(p.active_seconds)} · {plural(p.session_count, "session")}</span>
            <Sparkline values={p.sparkline} color={projectColor(p.color)} height={34} />
            <span className="tags">{p.skills.slice(0, 3).map((s) => <span key={s} className="tagc">{s}</span>)}</span>
          </button>
        ))}
      </div>
      <Sheet open={!!selected} onClose={close} label="Project detail">
        {shown && <ProjectSheet key={shown.id} project={shown} projects={list} onClose={close} />}
      </Sheet>
    </>
  );
}

/* -------------------------------------------------------------------- Skills */

const FACTORS: { key: keyof Skill["factors"]; label: string }[] = [
  { key: "frequency", label: "Frequency" },
  { key: "duration", label: "Duration" },
  { key: "complexity", label: "Complexity" },
  { key: "diversity", label: "Project diversity" },
  { key: "evidence", label: "Evidence" },
  { key: "confirmation", label: "Confirmed by you" },
];

function SkillSheet({ skill, onClose }: { skill: Skill; onClose: () => void }) {
  const patch = usePatchSkill();
  const { show } = useToast();
  const total = FACTORS.reduce((a, f) => a + skill.factors[f.key], 0) || 1;
  const delta = Math.round(skill.score - skill.previous_score);
  return (
    <Stagger>
      {[
        <div key="h">
          <TruthBadge state={skill.state} />
          <h3>{skill.name}</h3>
          <div className="meta">{skill.category} · <span className="num">{Math.round(skill.score)}</span>{delta ? <span style={{ color: delta > 0 ? "var(--green)" : "var(--muted)" }}> · {delta > 0 ? "+" : "−"}{Math.abs(delta)} this week</span> : null}</div>
          <p className="meta" style={{ marginTop: 10 }}>Based on evidence, not time spent.</p>
        </div>,
        <div key="f" className="grp">
          <div className="lbl">How this score is made</div>
          <div className="stackbar" role="img" aria-label={FACTORS.map((f) => `${f.label} ${Math.round(skill.factors[f.key] * 100)}%`).join(", ")}>
            {FACTORS.map((f, i) => (
              <motion.i key={f.key} style={{ background: `var(--p${i + 1})` }} initial={{ width: 0 }} animate={{ width: `${(skill.factors[f.key] / total) * 100}%` }} transition={{ duration: 0.9, delay: 0.2 + i * 0.05, ease: EASE }} />
            ))}
          </div>
          <div className="legend">
            {FACTORS.map((f, i) => (
              <div key={f.key}><span><Dot color={`var(--p${i + 1})`} /> {f.label}</span><span className="k num">{Math.round(skill.factors[f.key] * 100)}%</span></div>
            ))}
          </div>
        </div>,
        <div key="l" className="grp"><div className="lbl">Last 30 days</div><LineChart points={skill.history} /></div>,
        skill.projects.length > 0 && <div key="p" className="grp"><div className="lbl">Used in</div><div className="tags">{skill.projects.map((p) => <span key={p} className="tagc">{p}</span>)}</div></div>,
        <div key="e" className="grp"><div className="meta">Based on {plural(skill.evidence_count, "piece")} of evidence · {formatDuration(skill.active_seconds)} active</div></div>,
        <div key="a" className="acts">
          {skill.state !== "confirmed" && <button className="pill primary" onClick={() => patch.mutate({ id: skill.id, state: "confirmed" }, { onSuccess: () => { show("Added to Career Memory"); onClose(); } })}>Confirm</button>}
          {skill.state !== "rejected" && <button className="pill" onClick={() => patch.mutate({ id: skill.id, state: "rejected" }, { onSuccess: () => { show("Marked as not right"); onClose(); } })}>Not right</button>}
          {skill.state === "confirmed" && <button className="pill" onClick={onClose}>Done</button>}
        </div>,
      ].filter(Boolean) as JSX.Element[]}
    </Stagger>
  );
}

function SkillsTab() {
  const q = useSkills();
  const [openId, setOpenId] = useState<string | null>(null);
  const close = useCallback(() => setOpenId(null), []);
  const list = useMemo(() => (q.data?.skills ?? []).filter((s) => s.state !== "rejected").sort((a, b) => b.score - a.score), [q.data]);
  const selected = list.find((s) => s.id === openId) ?? null;
  const shown = useLast(selected);
  if (q.isError) return <ErrorNote error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <ListSkeleton />;
  if (!list.length) return <EmptyState title="No skills yet.">Skills grow from evidence in confirmed sessions.</EmptyState>;
  return (
    <>
      <div className="card in">
        <p className="meta" style={{ marginBottom: 8 }}>Based on evidence, not time spent.</p>
        <div className="mem">
          {list.map((s) => {
            const d = Math.round(s.score - s.previous_score);
            return (
              <button key={s.id} className="r skrow" onClick={() => setOpenId(s.id)}>
                <span className="skname"><b>{s.name}</b><span className="meta">{s.category}</span></span>
                <span className="track skt"><motion.i initial={{ width: `${s.previous_score}%` }} animate={{ width: `${s.score}%` }} transition={{ duration: 1.1, delay: 0.2, ease: EASE }} /></span>
                <span className="num skscore">{Math.round(s.score)}</span>
                <span className={`num trend ${d > 0 ? "up" : ""}`}>{d > 0 ? `▲ ${d}` : d < 0 ? `▼ ${Math.abs(d)}` : "–"}</span>
                <TruthBadge state={s.state} label={false} />
              </button>
            );
          })}
        </div>
      </div>
      <Sheet open={!!selected} onClose={close} label="Skill detail">
        {shown && <SkillSheet key={shown.id} skill={shown} onClose={close} />}
      </Sheet>
    </>
  );
}

/* -------------------------------------------------------------- Achievements */

function AchievementCard({ a }: { a: Achievement }) {
  const patch = usePatchAchievement();
  const { show } = useToast();
  const [impact, setImpact] = useState(a.impact ?? "");
  const [error, setError] = useState<string | null>(null);
  const saveImpact = () => {
    const v = impact.trim();
    if (v === (a.impact ?? "")) return;
    patch.mutate({ id: a.id, impact: v || null }, { onSuccess: () => show(v ? "Impact saved" : "Impact removed"), onError: (e) => setError(errorMessage(e)) });
  };
  return (
    <article className="card ach in">
      <div className="row-flex" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h3>{a.title}</h3>
          <div className="meta">
            {a.project && <><Dot color={projectColor(a.project.color)} /> {a.project.name} · </>}
            {a.ticket && <>{a.ticket} · </>}
            <Confidence value={a.confidence} />
          </div>
        </div>
        <TruthBadge state={a.on_cv ? "confirmed" : a.state} />
      </div>

      <ol className="steps" aria-label="How this was done">
        {a.steps.map((s) => (
          <li key={s.name} className={s.done ? "lit" : ""} title={s.done ? s.evidence.map((e) => e.value).join(", ") : "No evidence yet"}>
            <i aria-hidden>{s.done ? "✓" : ""}</i>
            <span>{s.name[0]?.toUpperCase()}{s.name.slice(1)}<span className="sr">{s.done ? ", done" : ", no evidence yet"}</span></span>
          </li>
        ))}
      </ol>

      <label className="impact">
        <span className="lbl">Impact</span>
        <input className="field" value={impact} placeholder="Optional, for example “Cut a test run from 3h to 40m”" onChange={(e) => setImpact(e.target.value)} onBlur={saveImpact} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
        <span className="meta">Impact numbers are never generated. Add one only if you can back it up.</span>
      </label>
      {error && <p className="err" role="alert">{error}</p>}

      <div className="acts" style={{ marginTop: 20 }}>
        {a.state !== "confirmed" && <button className="pill primary" onClick={(e) => { flyToMemory((e.currentTarget.closest(".ach") as HTMLElement | null) ?? null); patch.mutate({ id: a.id, state: "confirmed" }, { onSuccess: () => show("Added to Career Memory") }); }}>Confirm</button>}
        {a.state !== "rejected" && <button className="pill" onClick={() => patch.mutate({ id: a.id, state: "rejected" }, { onSuccess: () => show("Marked as not right") })}>Not right</button>}
        <button className="pill" disabled={a.state !== "confirmed" || patch.isPending} title={a.state !== "confirmed" ? "Confirm it first" : undefined} onClick={() => patch.mutate({ id: a.id, on_cv: !a.on_cv }, { onSuccess: () => show(a.on_cv ? "Removed from your CV" : "Added to your CV") })}>
          {a.on_cv ? "On CV · Remove" : "Add to CV"}
        </button>
      </div>
    </article>
  );
}

function AchievementsTab() {
  const q = useAchievements();
  if (q.isError) return <ErrorNote error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <ListSkeleton />;
  const list = q.data.achievements.filter((a) => a.state !== "rejected");
  if (!list.length) return <EmptyState title="No achievements yet.">When a piece of work has a clear problem, fix and result, it shows up here.</EmptyState>;
  return <div className="stack-list">{list.map((a) => <AchievementCard key={a.id} a={a} />)}</div>;
}

/* ---------------------------------------------------------------- Everything */

type Filter = "all" | TruthState;
const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "inferred", label: "Needs review" },
  { value: "confirmed", label: "Confirmed" },
  { value: "observed", label: "Observed" },
  { value: "rejected", label: "Not right" },
];

function EverythingTab() {
  const q = useMemory();
  const [filter, setFilter] = useState<Filter>("all");
  const [limit, setLimit] = useState(60);
  if (q.isError) return <ErrorNote error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <ListSkeleton rows={6} />;
  const { items, counts } = q.data;
  const rows: MemoryItem[] = items.filter((i) => (filter === "all" ? i.state !== "rejected" : i.state === filter));
  const countFor = (f: Filter) => (f === "all" ? items.filter((i) => i.state !== "rejected").length : counts[f] ?? 0);
  return (
    <div className="in">
      <div className="chips" role="group" aria-label="Filter by state">
        {FILTERS.map((f) => (
          <button key={f.value} className={`chip ${filter === f.value ? "on" : ""}`} aria-pressed={filter === f.value} onClick={() => { setFilter(f.value); setLimit(60); }}>
            {f.label} <span className="num">{countFor(f.value)}</span>
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <EmptyState title="Nothing here.">{filter === "all" ? "Career Memory fills up as you confirm what the agent saw." : `No items are marked “${stateLabel(filter as TruthState)}”.`}</EmptyState>
      ) : (
        <div className="card tbl-card">
          <table className="tbl">
            <thead>
              <tr><th>Name</th><th>State</th><th className="c-type">Type</th><th className="c-proj">Project</th><th className="c-detail">Detail</th><th className="c-upd">Updated</th></tr>
            </thead>
            <tbody>
              {rows.slice(0, limit).map((i) => (
                <tr key={i.id}>
                  <td className="nm">{i.name}</td>
                  <td><TruthBadge state={i.state} /></td>
                  <td className="c-type muted">{i.type}</td>
                  <td className="c-proj muted">{i.project ?? "–"}</td>
                  <td className="c-detail muted num">{i.detail}</td>
                  <td className="c-upd muted">{relativeTime(i.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > limit && <button className="link" style={{ margin: "16px 0 0" }} onClick={() => setLimit((l) => l + 60)}>Show more ›</button>}
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------- Page */

export default function MemoryPage() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab: Tab = TABS.some((t) => t.value === raw) ? (raw as Tab) : "projects";
  return (
    <Page eyebrow="Career Memory" title="What you've confirmed." lede="Only confirmed and observed facts reach your CV.">
      <div className="tabs-row in">
        <Segmented<Tab> label="Memory sections" value={tab} options={TABS} onChange={(t) => setParams(t === "projects" ? {} : { tab: t }, { replace: true })} />
      </div>
      {tab === "projects" && <ProjectsTab />}
      {tab === "skills" && <SkillsTab />}
      {tab === "achievements" && <AchievementsTab />}
      {tab === "everything" && <EverythingTab />}
    </Page>
  );
}
