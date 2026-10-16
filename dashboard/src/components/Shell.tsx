import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate, useOutlet } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { usePause, useResume, useSetStatus, useStatus } from "../api/hooks";
import type { Status } from "../api/types";
import { useDismiss } from "../lib/hooks";
import { MEMORY_BUMP, MEMORY_UNBUMP } from "../lib/fly";
import { formatTime } from "../lib/format";
import { Icons, Segmented, type SegOption } from "./ui";
import { useToast } from "./Toast";

type Tab = "today" | "timeline" | "review" | "memory" | "cv";
const PATHS: Record<Tab, string> = { today: "/", timeline: "/timeline", review: "/review", memory: "/memory", cv: "/cv" };
const LABELS: Record<Tab, string> = { today: "Today", timeline: "Timeline", review: "Review", memory: "Memory", cv: "CV" };
const TABS: Tab[] = ["today", "timeline", "review", "memory", "cv"];

function activeTab(pathname: string): Tab | "" {
  if (pathname === "/") return "today";
  return TABS.find((t) => t !== "today" && pathname.startsWith(PATHS[t])) ?? "";
}

export function StatusPill({ status }: { status: Status }) {
  const pause = usePause();
  const resume = useResume();
  const { show } = useToast();
  const { state } = status;
  const label = state === "running" ? "Recording" : state === "paused" ? "Paused · Resume" : "Stopped";
  const until = status.paused_until ? formatTime(status.paused_until) : null;
  const onClick = () => {
    if (state === "running") pause.mutate(60, { onSuccess: () => show("Tracking paused for 1 hour") });
    else if (state === "paused") resume.mutate(undefined, { onSuccess: () => show("Tracking resumed") });
  };
  return (
    <button
      className={`status ${state}`}
      onClick={onClick}
      disabled={state === "stopped"}
      title={state === "running" ? "Pause for 1 hour" : state === "paused" ? `Paused until ${until ?? "later"}. Click to resume.` : "The agent is stopped. Run `career start`."}
    >
      <span className="dot" aria-hidden />
      <span>{label}</span>
    </button>
  );
}

function MoreMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { pathname } = useLocation();
  useDismiss(open, () => setOpen(false), ref);
  useEffect(() => {
    setOpen(false);
  }, [pathname]);
  return (
    <div className="more" ref={ref}>
      <button className="icon-btn" aria-label="More" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {Icons.more}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            className="menu"
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98, transition: { duration: 0.12 } }}
            transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
          >
            <NavLink role="menuitem" to="/insights">
              Insights
            </NavLink>
            <NavLink role="menuitem" to="/settings">
              Settings
            </NavLink>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function Shell() {
  const { data: status } = useStatus();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const outlet = useOutlet();
  const setStatus = useSetStatus();
  const [bump, setBump] = useState(false);

  useEffect(() => {
    let t = 0;
    const up = () => {
      setStatus((s) => ({ ...s, memory_count: s.memory_count + 1 }));
      setBump(true);
      window.clearTimeout(t);
      t = window.setTimeout(() => setBump(false), 700);
    };
    const down = () => setStatus((s) => ({ ...s, memory_count: Math.max(0, s.memory_count - 1) }));
    window.addEventListener(MEMORY_BUMP, up);
    window.addEventListener(MEMORY_UNBUMP, down);
    return () => {
      window.removeEventListener(MEMORY_BUMP, up);
      window.removeEventListener(MEMORY_UNBUMP, down);
      window.clearTimeout(t);
    };
  }, [setStatus]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [pathname]);

  const current = activeTab(pathname);
  const review = status?.review_count ?? 0;
  const memory = status?.memory_count ?? 0;
  const options: SegOption<Tab>[] = TABS.map((t) => ({
    value: t,
    label: LABELS[t],
    badge: t === "review" ? review : t === "memory" ? memory : null,
    badgeGrey: t === "memory",
    bump: t === "memory" && bump,
    attrs: t === "memory" ? { "data-mem-target": "" } : undefined,
  }));
  const tabIcon: Record<Tab, JSX.Element> = { today: Icons.today, timeline: Icons.timeline, review: Icons.review, memory: Icons.memory, cv: Icons.cv };

  return (
    <>
      <header className="bar">
        <div className="bar-in">
          <NavLink to="/" className="wordmark">
            Career Agent
          </NavLink>
          <Segmented<Tab> className="nav-seg" label="Sections" value={current as Tab} options={options} onChange={(t) => navigate(PATHS[t])} />
          <div className="bar-right">
            {status && <StatusPill status={status} />}
            <MoreMenu />
          </div>
        </div>
      </header>

      <main className="page">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={pathname} className="view" initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { duration: 0.24 } }} exit={{ opacity: 0, transition: { duration: 0.12 } }}>
            {outlet}
          </motion.div>
        </AnimatePresence>
      </main>

      <nav className="tabbar" aria-label="Sections">
        {TABS.map((t) => (
          <NavLink
            key={t}
            to={PATHS[t]}
            end
            aria-current={current === t ? "page" : undefined}
            className={t === "memory" && bump ? "bump" : undefined}
            {...(t === "memory" ? { "data-mem-target": "" } : {})}
          >
            {tabIcon[t]}
            {LABELS[t]}
            {t === "review" && review > 0 && <span className="badge num">{review}</span>}
          </NavLink>
        ))}
      </nav>
    </>
  );
}
