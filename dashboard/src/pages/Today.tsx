import { Fragment } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { useAnalyze, useResume, useStatus, useToday } from "../api/hooks";
import type { Session, Today } from "../api/types";
import { EmptyState, ErrorNote, Page, Skeleton, TruthBadge } from "../components/ui";
import { useCountUp, useNow } from "../lib/hooks";
import { confidenceLabel, formatClock, formatDuration, formatLongDate, formatTime, greeting, plural, projectColor, weekdayLetter } from "../lib/format";

function Hero({ today }: { today: Today }) {
  const v = useCountUp(today.active_seconds, 900);
  const minutes = Math.floor(v / 60);
  const navigate = useNavigate();
  const items = today.ribbon;
  const first = items[0];
  const last = items[items.length - 1];
  const t0 = first ? new Date(first.start).getTime() : 0;
  const t1 = last ? new Date(last.end).getTime() : 0;
  const mid = new Date((t0 + t1) / 2);
  const live = !!today.current_session;
  return (
    <div className="card">
      <div className="meta">Meaningful work today</div>
      <div className="big num" aria-label={formatDuration(today.active_seconds)}>
        <span aria-hidden>{Math.floor(minutes / 60)}</span>
        <span className="u" aria-hidden>h</span>
        <span aria-hidden>{String(minutes % 60).padStart(2, "0")}</span>
        <span className="u" aria-hidden>m</span>
      </div>
      <div className="meta">
        {plural(today.session_count, "session")} across {plural(today.project_count, "project")}
      </div>
      <div className="ribbon" role="list" aria-label="Today's sessions">
        {items.map((r, i) => {
          const prev = items[i - 1];
          const gap = prev ? new Date(r.start).getTime() - new Date(prev.end).getTime() : 0;
          return (
            <Fragment key={`${r.start}-${i}`}>
              {gap > 0 && <span style={{ flex: gap }} />}
              <button
                role="listitem"
                title={`${r.label} · ${formatTime(r.start)}`}
                aria-label={`${r.label}, ${formatTime(r.start)}`}
                style={{ flex: Math.max(1, new Date(r.end).getTime() - new Date(r.start).getTime()), background: projectColor(r.color), animationDelay: `${0.3 + i * 0.07}s` }}
                onClick={() => navigate("/timeline")}
              />
            </Fragment>
          );
        })}
      </div>
      {first && (
        <div className="axis num">
          <span>{formatTime(first.start)}</span>
          <span>{formatTime(mid)}</span>
          <span>{live ? "Now" : formatTime(last?.end ?? first.end)}</span>
        </div>
      )}
    </div>
  );
}

function NowCard({ session, running }: { session: Session | null; running: boolean }) {
  const now = useNow(1000);
  if (!session)
    return (
      <div className="card now idle">
        <div className="tag quiet">Now</div>
        <h3>Nothing in progress</h3>
        <div className="meta">A new session starts when you pick up work.</div>
      </div>
    );
  const elapsed = running ? (now.getTime() - new Date(session.start).getTime()) / 1000 : session.active_seconds;
  const app = Object.keys(session.applications)[0];
  const meta = [session.project?.name, app, session.files[0]].filter(Boolean).join(" · ");
  return (
    <div className="card now">
      <div className="tag" style={running ? undefined : { color: "var(--orange)" }}>
        <span className={`dot ${running ? "" : "still"}`} aria-hidden style={running ? undefined : { background: "var(--orange)" }} />
        {running ? "Now" : "Paused"}
      </div>
      <motion.h3 key={session.activity} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}>
        {session.activity}
      </motion.h3>
      <div className="meta">{meta}</div>
      <div className="timer num" role="timer" aria-label="Time in this session">
        {formatClock(elapsed)}
      </div>
    </div>
  );
}

function TodaySkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <Skeleton w={160} h={20} className="in" />
      <Skeleton w="min(460px,80%)" h={52} style={{ margin: "10px 0 14px" }} className="in" />
      <Skeleton w="min(340px,70%)" h={24} style={{ marginBottom: 48 }} className="in" />
      <div className="hero">
        <div className="card">
          <Skeleton w={140} h={14} />
          <Skeleton w={260} h={86} r={14} style={{ margin: "14px 0 10px" }} />
          <Skeleton w={190} h={14} />
          <Skeleton h={8} style={{ margin: "32px 0 10px" }} />
        </div>
        <div className="card">
          <Skeleton w={60} h={14} />
          <Skeleton w="80%" h={30} style={{ margin: "16px 0 10px" }} />
          <Skeleton w="55%" h={14} />
        </div>
      </div>
      <div className="duo">
        <div className="card"><Skeleton w={160} h={24} style={{ marginBottom: 24 }} /><Skeleton h={50} /></div>
        <div className="card"><Skeleton w={160} h={24} style={{ marginBottom: 24 }} /><Skeleton h={100} /></div>
      </div>
    </div>
  );
}

export default function TodayPage() {
  const today = useToday();
  const status = useStatus().data;
  const navigate = useNavigate();
  const resume = useResume();
  const analyze = useAnalyze();

  if (today.isError) return <ErrorNote error={today.error} onRetry={() => void today.refetch()} />;
  if (!today.data) return <TodaySkeleton />;
  const t = today.data;
  const hour = new Date().getHours();
  const empty = t.session_count === 0 && !t.current_session;
  const running = status?.state !== "paused";
  const weekMax = Math.max(8 * 3600, ...t.week.map((d) => d.active_seconds));

  return (
    <Page eyebrow={formatLongDate(t.date)} title={`${greeting(hour)}${t.name ? `, ${t.name}` : ""}.`} lede={empty ? "Quietly watching. Nothing for you to do." : "Your day so far, understood."}>
      {status?.state === "paused" && (
        <div className="card banner in">
          <span className="dot still" style={{ background: "var(--orange)" }} aria-hidden />
          <span>
            <b>Tracking is paused</b>
            {status.paused_until && <span className="meta"> until {formatTime(status.paused_until)}. Nothing is being recorded.</span>}
          </span>
          <button className="pill" onClick={() => resume.mutate()}>Resume</button>
        </div>
      )}
      {status?.state === "stopped" && (
        <div className="card banner in">
          <span className="dot still" style={{ background: "var(--faint)" }} aria-hidden />
          <span>
            <b>The agent is stopped.</b> <span className="meta">Start it with <code>career start</code>.</span>
          </span>
        </div>
      )}
      {status && !status.ai.available && status.ai.pending_sessions > 0 && (
        <div className="card banner in">
          <span>
            <b>AI is offline.</b> <span className="meta">Collection continues. {plural(status.ai.pending_sessions, "session")} waiting for analysis.</span>
          </span>
          <button className="pill" disabled={analyze.isPending} onClick={() => analyze.mutate()}>Analyze when online</button>
        </div>
      )}

      {empty ? (
        <EmptyState title="I'm observing.">Your first sessions will appear here in about 30 minutes.</EmptyState>
      ) : (
        <div className="hero in">
          <Hero today={t} />
          <NowCard session={t.current_session} running={running} />
        </div>
      )}

      {t.review_count > 0 && (
        <button className="card row-cta in" onClick={() => navigate("/review")}>
          <span className="n num">{t.review_count}</span>
          <span>
            <b>{t.review_count === 1 ? "Thing to review" : "Things to review"}</b>
            <span className="meta">Confirm what the agent understood today.</span>
          </span>
          <span className="link">Review ›</span>
        </button>
      )}

      <div className="duo in">
        <div className="card">
          <h2>Skills this week</h2>
          {t.top_skills.length === 0 && <p className="meta">Skills show up once a few sessions are confirmed.</p>}
          {t.top_skills.map((s) => {
            const prev = Math.max(0, s.score - s.delta);
            return (
              <div className="sk" key={s.name}>
                <span>{s.name}</span>
                <span className="d num" style={{ opacity: s.delta ? undefined : 0 }}>
                  {s.delta > 0 ? `+${s.delta}%` : s.delta < 0 ? `${s.delta}%` : ""}
                </span>
                <div className="track">
                  <motion.i initial={{ width: `${prev}%` }} animate={{ width: `${s.score}%` }} transition={{ duration: 1.1, delay: 0.25, ease: [0.25, 1, 0.5, 1] }} />
                </div>
              </div>
            );
          })}
          <button className="link" onClick={() => navigate("/memory?tab=skills")}>All skills ›</button>
        </div>
        <div className="card">
          <h2>{formatDuration(t.week_total_seconds)} this week</h2>
          <div className="week" role="img" aria-label={`Active time this week: ${t.week.map((d) => `${weekdayLetter(d.date)} ${formatDuration(d.active_seconds)}`).join(", ")}`}>
            {t.week.map((d, i) => (
              <div key={d.date}>
                <motion.span
                  className={d.date === t.date ? "t" : undefined}
                  style={{ height: `${d.active_seconds ? (d.active_seconds / weekMax) * 100 : 3}%`, transformOrigin: "bottom" }}
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={{ duration: 0.9, delay: 0.2 + i * 0.06, ease: [0.25, 1, 0.5, 1] }}
                />
                {weekdayLetter(d.date)}
              </div>
            ))}
          </div>
          <button className="link" style={{ marginTop: 18 }} onClick={() => navigate("/insights")}>Insights ›</button>
        </div>
      </div>

      {t.potential_achievements.length > 0 && (
        <div className="card in" style={{ marginTop: 24 }}>
          <h2>Potential achievements</h2>
          <div className="plist">
            {t.potential_achievements.map((a) => (
              <button key={a.id} className="prow" onClick={() => navigate("/memory?tab=achievements")}>
                <span className="pdot" style={{ background: projectColor(a.project?.color) }} aria-hidden />
                <span className="grow">
                  <b>{a.title}</b>
                  <span className="meta">{[a.project?.name, confidenceLabel(a.confidence)].filter(Boolean).join(" · ")}</span>
                </span>
                <TruthBadge state={a.state} />
              </button>
            ))}
          </div>
        </div>
      )}

      {status?.learning.active && (
        <p className="quiet-note in">
          Day {status.learning.day} of {status.learning.days_total} · I'm still learning your work
        </p>
      )}
    </Page>
  );
}
