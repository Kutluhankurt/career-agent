import { useCallback, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useProjects, useReviewSession, useSessionDetail, useSessions } from "../api/hooks";
import { errorMessage } from "../api/client";
import type { Session } from "../api/types";
import { Sheet, Stagger } from "../components/Sheet";
import { useToast } from "../components/Toast";
import { Confidence, EmptyState, ErrorNote, Page, Skeleton, TruthBadge } from "../components/ui";
import { flyToMemory } from "../lib/fly";
import { useLast, useNow } from "../lib/hooks";
import { addDays, dateKey, formatDuration, formatLongDate, formatRange, formatTime, minutesOfDay, projectColor } from "../lib/format";

const PX = 1.7;

function SessionSheet({ session, onClose }: { session: Session; onClose: () => void }) {
  const [raw, setRaw] = useState(false);
  const [editing, setEditing] = useState(false);
  const [activity, setActivity] = useState(session.activity);
  const [projectId, setProjectId] = useState(session.project?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const detail = useSessionDetail(session.id, raw);
  const projects = useProjects();
  const review = useReviewSession();
  const { show } = useToast();
  const confirmRef = useRef<HTMLButtonElement>(null);
  const color = projectColor(session.project?.color);

  const send = (body: Parameters<typeof review.mutate>[0], done: string, fly?: boolean) => {
    setError(null);
    if (fly) flyToMemory(confirmRef.current);
    review.mutate(body, {
      onSuccess: () => {
        show(done);
        onClose();
      },
      onError: (e) => setError(errorMessage(e)),
    });
  };

  return (
    <>
      <Stagger>
        {[
          <div key="h">
            <div className="row-flex">
              <TruthBadge state={session.state} />
              <span className="meta num">{formatRange(session.start, session.end)}</span>
            </div>
            {editing ? (
              <input className="field" aria-label="Activity" value={activity} onChange={(e) => setActivity(e.target.value)} autoFocus style={{ marginTop: 14 }} />
            ) : (
              <h3>{session.activity}</h3>
            )}
            {editing ? (
              <select className="field" aria-label="Project" value={projectId} onChange={(e) => setProjectId(e.target.value)} style={{ marginTop: 10 }}>
                <option value="">No project</option>
                {(projects.data?.projects ?? []).filter((p) => p.state !== "rejected").map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            ) : (
              <div className="meta" style={{ color, fontWeight: 500 }}>
                {session.project?.name ?? "No project"} <span style={{ color: "var(--muted)", fontWeight: 400 }}>· {formatDuration(session.active_seconds)} active</span>
              </div>
            )}
          </div>,
          session.skills.length > 0 && (
            <div key="s" className="grp">
              <div className="lbl">Skills</div>
              <div className="tags">{session.skills.map((k) => <span key={k} className="tagc">{k}</span>)}</div>
            </div>
          ),
          session.evidence.length > 0 && (
            <div key="e" className="grp">
              <div className="lbl">Based on</div>
              <div className="list">
                {session.evidence.map((e) => (
                  <div key={e.id}><span>{e.value}</span><span className="k">{e.label}</span></div>
                ))}
              </div>
            </div>
          ),
          <div key="c" className="grp">
            <div className="lbl">Confidence</div>
            <div style={{ fontSize: 15 }}><Confidence value={session.confidence} /></div>
          </div>,
          <div key="r" className="grp">
            <button className="link" aria-expanded={raw} onClick={() => setRaw((r) => !r)}>{raw ? "Hide observations" : "Show what was observed ›"}</button>
            {raw && (
              <div className="raw" style={{ marginTop: 12 }}>
                {detail.isLoading && <Skeleton h={60} />}
                {detail.isError && <span>Couldn't load observations.</span>}
                {detail.data?.raw_events.length === 0 && <span>Nothing recorded for this session.</span>}
                {detail.data?.raw_events.map((ev, i) => (
                  <div key={i}>{`${formatTime(ev.timestamp)}  ${(ev.application ?? ev.type).padEnd(9)}  ${ev.title ?? ""}`}</div>
                ))}
              </div>
            )}
          </div>,
          <div key="a">
            {error && <p className="err" role="alert">{error}</p>}
            {session.is_open ? (
              <p className="meta" style={{ marginTop: 28 }}>Still in progress. You can review it once it ends.</p>
            ) : editing ? (
              <div className="acts">
                <button className="pill primary" disabled={review.isPending || !activity.trim()} onClick={() => send({ id: session.id, action: "edit", activity: activity.trim(), ...(projectId ? { project_id: projectId } : {}) }, "Saved and confirmed", true)}>Save and confirm</button>
                <button className="pill" onClick={() => setEditing(false)}>Cancel</button>
              </div>
            ) : (
              <div className="acts">
                {session.state !== "confirmed" && <button ref={confirmRef} className="pill primary" disabled={review.isPending} onClick={() => send({ id: session.id, action: "confirm" }, "Added to Career Memory", true)}>Confirm</button>}
                <button className="pill" onClick={() => setEditing(true)}>Edit</button>
                {session.state !== "rejected" && <button className="pill" disabled={review.isPending} onClick={() => send({ id: session.id, action: "reject" }, "Marked as not right")}>Not right</button>}
                {session.state === "confirmed" && <button className="pill" onClick={onClose}>Done</button>}
              </div>
            )}
          </div>,
        ].filter(Boolean) as JSX.Element[]}
      </Stagger>
    </>
  );
}

function TimelineSkeleton() {
  return (
    <div className="tl" aria-busy="true" aria-label="Loading">
      <div />
      <div style={{ display: "grid", gap: 12 }}>
        {[90, 64, 80, 110, 70].map((h, i) => <Skeleton key={i} h={h} r={12} />)}
      </div>
    </div>
  );
}

export default function TimelinePage() {
  const [params, setParams] = useSearchParams();
  const todayKey = dateKey(new Date());
  const date = params.get("date") || todayKey;
  const setDate = (d: string) => setParams(d === todayKey ? {} : { date: d }, { replace: true });
  const q = useSessions(date);
  const [openId, setOpenId] = useState<string | null>(null);
  const now = useNow(15_000);
  const close = useCallback(() => setOpenId(null), []);

  const sessions = useMemo(() => (q.data?.sessions ?? []).filter((s) => s.state !== "rejected"), [q.data]);
  const endOf = (s: Session) => (s.is_open ? Math.max(minutesOfDay(s.end), minutesOfDay(now)) : minutesOfDay(s.end));
  const selected = (q.data?.sessions ?? []).find((s) => s.id === openId) ?? null;
  const shown = useLast(selected);

  const layout = useMemo(() => {
    if (!sessions.length) return null;
    const first = Math.min(...sessions.map((s) => minutesOfDay(s.start)));
    const last = Math.max(...sessions.map(endOf));
    const t0 = Math.floor(Math.min(first, 9 * 60) / 60) * 60;
    const t1 = Math.max(Math.ceil(last / 60) * 60, t0 + 180);
    const hours: number[] = [];
    for (let h = t0; h <= t1; h += 60) hours.push(h);
    return { t0, t1, hours };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions, now]);

  return (
    <Page eyebrow={formatLongDate(date)} title="Timeline" lede="Every session, and exactly what it was based on.">
      <div className="datebar in">
        <button className="icon-btn" aria-label="Previous day" onClick={() => setDate(addDays(date, -1))}>‹</button>
        <input type="date" className="field datepick" aria-label="Pick a day" value={date} max={todayKey} onChange={(e) => e.target.value && setDate(e.target.value)} />
        <button className="icon-btn" aria-label="Next day" disabled={date >= todayKey} onClick={() => setDate(addDays(date, 1))}>›</button>
        {date !== todayKey && <button className="link" onClick={() => setDate(todayKey)}>Today</button>}
      </div>

      {q.isError ? (
        <ErrorNote error={q.error} onRetry={() => void q.refetch()} />
      ) : !q.data ? (
        <TimelineSkeleton />
      ) : !layout ? (
        <EmptyState title={date === todayKey ? "Nothing yet today." : "Nothing recorded this day."}>
          {date === todayKey ? "Sessions appear here as you work." : "Use the arrows to look at another day."}
        </EmptyState>
      ) : (
        <div className="tl in">
          <div className="tl-axis" style={{ height: (layout.t1 - layout.t0) * PX }}>
            {layout.hours.map((h) => (
              <span key={h} className="num" style={{ top: (h - layout.t0) * PX }}>{String(Math.floor(h / 60) % 24).padStart(2, "0")}:00</span>
            ))}
          </div>
          <div className="tl-track" style={{ height: (layout.t1 - layout.t0) * PX }}>
            {layout.hours.map((h) => <div key={h} className="hr" style={{ top: (h - layout.t0) * PX }} />)}
            {sessions.map((s, i) => {
              const a = minutesOfDay(s.start);
              const b = endOf(s);
              const top = (a - layout.t0) * PX + 3;
              const h = Math.max(30, (b - a) * PX - 6);
              const prev = sessions[i - 1];
              const gap = prev ? a - endOf(prev) : 0;
              return (
                <div key={s.id}>
                  {prev && gap >= 20 && (
                    <div className="brk" style={{ top: (a - gap - layout.t0) * PX + 3, height: gap * PX - 6 }}>
                      Break · {formatDuration(gap * 60)}
                    </div>
                  )}
                  <button
                    className={`blk ${s.is_open ? "live" : ""}`}
                    style={{ top, height: h, ["--pc" as string]: projectColor(s.project?.color) }}
                    onClick={() => setOpenId(s.id)}
                    aria-label={`${s.activity}, ${formatRange(s.start, s.end)}`}
                  >
                    <span className="t num">{formatTime(s.start)}</span>
                    <span style={{ minWidth: 0 }}>
                      <span className="n">{s.activity}</span>
                      {h > 46 && <span className="p">{s.project?.name ?? "No project"}{s.is_open ? " · Now" : ""}</span>}
                    </span>
                    {h > 46 && <span className="s"><TruthBadge state={s.state} /></span>}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <Sheet open={!!selected} onClose={close} label="Session detail">
        {shown && <SessionSheet key={shown.id} session={shown} onClose={close} />}
      </Sheet>
    </Page>
  );
}
