import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { useInsights } from "../api/hooks";
import { DayBars } from "../components/charts";
import { Dot, EmptyState, ErrorNote, Page, Segmented, Skeleton, TruthBadge } from "../components/ui";
import { formatDuration, parseDateKey, plural, projectColor } from "../lib/format";

type Period = "week" | "month";
const PERIODS: { value: Period; label: string }[] = [
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
];
const EASE = [0.25, 1, 0.5, 1] as const;
const short = (k: string) => parseDateKey(k).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

function List({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="meta">{empty}</p>;
  return (
    <ul className="plain">
      {items.map((i) => <li key={i}>{i}</li>)}
    </ul>
  );
}

export default function InsightsPage() {
  const [period, setPeriod] = useState<Period>("week");
  const q = useInsights(period);
  const d = q.data;
  const projects = d?.projects ?? [];

  return (
    <Page eyebrow="Insights" title={period === "week" ? "Your week." : "Your month."} lede="Plain answers from your confirmed and observed work.">
      <div className="tabs-row in">
        <Segmented<Period> label="Period" value={period} options={PERIODS} onChange={setPeriod} />
        {d && <span className="meta num">{short(d.start)} – {short(d.end)}</span>}
      </div>

      {q.isError ? (
        <ErrorNote error={q.error} onRetry={() => void q.refetch()} />
      ) : !d ? (
        <div className="stack-list" aria-busy="true" aria-label="Loading">
          {[160, 200, 120].map((h) => <div key={h} className="card"><Skeleton w="40%" h={24} /><Skeleton h={h - 60} style={{ marginTop: 20 }} r={12} /></div>)}
        </div>
      ) : d.session_count === 0 ? (
        <EmptyState title="Nothing in this period yet.">Come back after a few sessions.</EmptyState>
      ) : (
        <div key={period} className="stack-list">
          <section className="card in">
            <h2>What did I work on?</h2>
            <div className="meta" style={{ marginBottom: 18 }}>{formatDuration(d.active_seconds)} across {plural(d.session_count, "session")}</div>
            <div className="share" role="img" aria-label={projects.map((p) => `${p.name} ${Math.round(p.share * 100)}%`).join(", ")}>
              {projects.map((p, i) => (
                <motion.i key={p.name} style={{ background: projectColor(p.color) }} initial={{ width: 0 }} animate={{ width: `${p.share * 100}%` }} transition={{ duration: 0.9, delay: 0.1 + i * 0.07, ease: EASE }} title={p.name} />
              ))}
            </div>
            <div className="legend" style={{ marginTop: 16 }}>
              {projects.map((p) => (
                <div key={p.name}><span><Dot color={projectColor(p.color)} /> {p.name}</span><span className="k num">{formatDuration(p.seconds)} · {Math.round(p.share * 100)}%</span></div>
              ))}
            </div>
            {d.top_activities.length > 0 && (
              <>
                <div className="lbl" style={{ margin: "26px 0 10px" }}>Most time went to</div>
                <div className="legend">
                  {d.top_activities.map((a) => <div key={a.name}><span>{a.name}</span><span className="k num">{formatDuration(a.seconds)} · {plural(a.count, "session")}</span></div>)}
                </div>
              </>
            )}
          </section>

          <section className="card in">
            <h2>Active time by day</h2>
            <DayBars data={d.by_day} />
          </section>

          <div className="duo in">
            <section className="card">
              <h2>Which skills grew?</h2>
              {d.skills_up.length === 0 ? <p className="meta">No skill moved up in this period.</p> : (
                <div className="legend">
                  {d.skills_up.map((s) => <div key={s.name}><span>{s.name}</span><span className="num" style={{ color: "var(--green)" }}>+{s.delta}%</span></div>)}
                </div>
              )}
              {d.skills_down.length > 0 && <p className="meta" style={{ marginTop: 14 }}>Quieter: {d.skills_down.map((s) => `${s.name} ${s.delta}%`).join(", ")}</p>}
            </section>
            <section className="card">
              <h2>What did I accomplish?</h2>
              {d.achievements.length === 0 ? <p className="meta">Nothing confirmed yet. Achievements need a clear problem, fix and result.</p> : (
                <div className="plist">
                  {d.achievements.map((a) => (
                    <div key={a.id} className="prow static">
                      <span className="grow"><b>{a.title}</b><span className="meta">{a.project?.name}</span></span>
                      <TruthBadge state={a.state} />
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className="duo in">
            <section className="card"><h2>What do I keep doing?</h2><List items={d.repeated} empty="No clear pattern yet." /></section>
            <section className="card"><h2>What did I stop?</h2><List items={d.stopped} empty="Nothing dropped off." /></section>
          </div>

          <section className="card row-cta in static">
            <span className="n num">{d.cv_candidates}</span>
            <span>
              <h2 style={{ margin: 0, fontSize: 21 }}>What can go on my CV?</h2>
              <span className="meta">{d.cv_candidates > 0 ? `${plural(d.cv_candidates, "line")} to look over, each backed by evidence.` : "Everything that has evidence is already on it."}</span>
            </span>
            <Link className="link" to="/cv">Open CV ›</Link>
          </section>
        </div>
      )}
    </Page>
  );
}
