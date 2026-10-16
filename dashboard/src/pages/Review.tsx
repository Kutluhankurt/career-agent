import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { useReview, useReviewItem, useSetStatus, useStatus, type ReviewBody } from "../api/hooks";
import type { ReviewItem } from "../api/types";
import { useToast } from "../components/Toast";
import { ErrorNote, Page, Skeleton } from "../components/ui";
import { bumpMemory, flyToMemory } from "../lib/fly";
import { confidenceLabel, plural, projectColor } from "../lib/format";

const UNDO_MS = 4000;
const EASE = [0.25, 1, 0.5, 1] as const;

type Exit = "confirm" | "reject";
interface Pending {
  timer: number;
  body: ReviewBody & { id: string };
  accepted: boolean;
}

const isYes = (o: string) => /^yes/i.test(o);
const isNo = (o: string) => /^no\b/i.test(o);

const exitVariants = {
  exit: (e: Exit) => (e === "reject" ? { x: -60, opacity: 0, transition: { duration: 0.35, ease: EASE } } : { opacity: 0, transition: { duration: 0.05 } }),
};

const depthAnim = [
  { y: 0, scale: 1, opacity: 1 },
  { y: 14, scale: 0.95, opacity: 0.6 },
  { y: 28, scale: 0.9, opacity: 0.3 },
];

function Card({ item, depth, exit, onAct, cardRef }: { item: ReviewItem; depth: number; exit: Exit; onAct: (a: ReviewBody) => void; cardRef?: React.Ref<HTMLElement> }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(item.title);
  const top = depth === 0;
  const evidence = item.evidence.slice(0, 4).map((e) => e.value);
  const question = item.options && item.options.length > 0;

  return (
    <motion.article
      ref={cardRef}
      className="rc"
      aria-hidden={!top}
      style={{ zIndex: 10 - depth, pointerEvents: top ? "auto" : "none" }}
      custom={exit}
      initial={{ opacity: 0, y: 24, scale: 0.97 }}
      animate={{ ...depthAnim[depth], transition: { type: "spring", stiffness: 380, damping: 32 } }}
      variants={exitVariants}
      exit="exit"
    >
      <div className="k">{item.subtitle}</div>
      {editing ? (
        <h3>
          <input
            className="field big-field"
            aria-label="Title"
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && title.trim()) onAct({ action: "edit", title: title.trim() });
              if (e.key === "Escape") setEditing(false);
            }}
          />
        </h3>
      ) : (
        <h3>{item.title}</h3>
      )}
      <p className="why">
        {item.project && <><span className="pdot" style={{ background: projectColor(item.project.color) }} aria-hidden /> {item.project.name} · </>}
        {confidenceLabel(item.confidence)}
      </p>
      {item.skills.length > 0 && <p className="why">Skills: {item.skills.join(" · ")}</p>}
      {evidence.length > 0 && <p className="ev">Based on {evidence.join(", ")}</p>}
      {item.kind === "achievement" && <p className="why">Impact numbers are never generated. Add one only if you can back it up.</p>}
      <div className="acts">
        {editing ? (
          <>
            <button className="pill primary" disabled={!title.trim()} onClick={() => onAct({ action: "edit", title: title.trim() })}>Save and confirm</button>
            <button className="pill" onClick={() => setEditing(false)}>Cancel</button>
          </>
        ) : question ? (
          item.options?.map((o, i) => (
            <button key={o} className={`pill ${i === 0 ? "primary" : ""}`} tabIndex={top ? 0 : -1} onClick={() => onAct({ action: "answer", answer: o })}>
              {o}
              {isYes(o) && <kbd>Y</kbd>}
              {isNo(o) && <kbd>N</kbd>}
            </button>
          ))
        ) : (
          <>
            <button className="pill primary" tabIndex={top ? 0 : -1} onClick={() => onAct({ action: "confirm" })}>Confirm<kbd>Y</kbd></button>
            <button className="pill" tabIndex={top ? 0 : -1} onClick={() => setEditing(true)} data-edit>Edit<kbd>E</kbd></button>
            <button className="pill" tabIndex={top ? 0 : -1} onClick={() => onAct({ action: "reject" })}>Not right<kbd>N</kbd></button>
          </>
        )}
      </div>
    </motion.article>
  );
}

export default function ReviewPage() {
  const q = useReview();
  const status = useStatus().data;
  const send = useReviewItem();
  const sendRef = useRef(send.mutateAsync);
  sendRef.current = send.mutateAsync;
  const setStatus = useSetStatus();
  const { show } = useToast();
  const navigate = useNavigate();
  const [handled, setHandled] = useState<ReadonlySet<string>>(new Set());
  const [added, setAdded] = useState(0);
  const [exit, setExit] = useState<Exit>("reject");
  const pending = useRef(new Map<string, Pending>());
  const lastId = useRef<string | null>(null);
  const topRef = useRef<HTMLElement | null>(null);

  const items = (q.data?.items ?? []).filter((i) => !handled.has(i.id));
  const total = items.length + handled.size;
  const top = items[0];

  const adjustReview = useCallback((n: number) => setStatus((s) => ({ ...s, review_count: Math.max(0, s.review_count + n) })), [setStatus]);

  const flush = useCallback((id: string) => {
    const p = pending.current.get(id);
    if (!p) return;
    window.clearTimeout(p.timer);
    pending.current.delete(id);
    sendRef.current(p.body).catch(() => {
      setHandled((h) => {
        const n = new Set(h);
        n.delete(id);
        return n;
      });
      if (p.accepted) {
        setAdded((a) => a - 1);
        bumpMemory(-1);
      }
      adjustReview(1);
      show("Couldn't save that. It's back in your queue.");
    });
  }, [adjustReview, show]);

  // Anything still waiting for its undo window is sent when leaving the page.
  useEffect(() => {
    const map = pending.current;
    return () => {
      for (const id of [...map.keys()]) {
        const p = map.get(id);
        if (!p) continue;
        window.clearTimeout(p.timer);
        map.delete(id);
        void sendRef.current(p.body).catch(() => undefined);
      }
    };
  }, []);

  const act = useCallback(
    (item: ReviewItem, body: ReviewBody) => {
      const accepted = body.action === "confirm" || body.action === "edit" || (body.action === "answer" && isYes(body.answer ?? ""));
      setExit(accepted ? "confirm" : "reject");
      if (accepted) flyToMemory(topRef.current);
      const full = { id: item.id, ...body };
      const timer = window.setTimeout(() => flush(item.id), UNDO_MS);
      pending.current.set(item.id, { timer, body: full, accepted });
      lastId.current = item.id;
      setHandled((h) => new Set(h).add(item.id));
      if (accepted) setAdded((a) => a + 1);
      adjustReview(-1);
      show(accepted ? "Added to Career Memory" : "Marked as not right", {
        ms: UNDO_MS,
        undo: () => {
          const p = pending.current.get(item.id);
          if (!p) return;
          window.clearTimeout(p.timer);
          pending.current.delete(item.id);
          setHandled((h) => {
            const n = new Set(h);
            n.delete(item.id);
            return n;
          });
          if (accepted) {
            setAdded((a) => a - 1);
            bumpMemory(-1);
          }
          adjustReview(1);
        },
      });
    },
    [adjustReview, flush, show],
  );

  // Keyboard: Y confirm / yes, N not right / no, E edit.
  useEffect(() => {
    if (!top) return;
    const key = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (top.options && top.options.length) {
        const o = k === "y" ? top.options.find(isYes) : k === "n" ? top.options.find(isNo) : undefined;
        if (o) act(top, { action: "answer", answer: o });
      } else if (k === "y") act(top, { action: "confirm" });
      else if (k === "n") act(top, { action: "reject" });
      else if (k === "e") document.querySelector<HTMLButtonElement>(".rc[aria-hidden='false'] [data-edit]")?.click();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [top, act]);

  if (q.isError) return <ErrorNote error={q.error} onRetry={() => void q.refetch()} />;

  const done = !!q.data && items.length === 0;
  const doneCount = handled.size;

  return (
    <Page
      eyebrow="Review"
      title="Is this right?"
      lede={status?.learning.active ? "Confirmed items become part of your career record. I'm still learning, so a few are questions." : "Confirmed items become part of your career record."}
    >
      {total > 0 && (
        <div className="rv-top in">
          <div className="dots" aria-hidden>
            {Array.from({ length: Math.min(total, 20) }, (_, k) => (
              <i key={k} className={k < doneCount ? "d" : k === doneCount ? "c" : ""} />
            ))}
          </div>
          <span className="meta" aria-live="polite">{items.length ? `${items.length} left` : ""}</span>
        </div>
      )}

      {!q.data ? (
        <div className="stack in" aria-busy="true" aria-label="Loading">
          <div className="rc"><Skeleton w={160} h={14} /><Skeleton h={38} style={{ margin: "14px 0 28px" }} /><Skeleton w="60%" h={16} /></div>
        </div>
      ) : (
        <div className="stack in">
          <AnimatePresence custom={exit}>
            {items.slice(0, 3).map((it, i) => (
              <Card key={it.id} item={it} depth={i} exit={exit} onAct={(b) => act(it, b)} cardRef={i === 0 ? topRef : undefined} />
            ))}
          </AnimatePresence>
          {done && (
            <motion.div className="rc done" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: 0.1 }}>
              <div className="k">All done</div>
              <h3>You're up to date.</h3>
              <p className="why" style={{ marginBottom: 28 }}>
                {added > 0 ? `${plural(added, "item")} added to your Career Memory.` : "Nothing needs your attention right now."}
              </p>
              <button className="pill primary" onClick={() => navigate("/memory")}>Open Career Memory</button>
            </motion.div>
          )}
        </div>
      )}
    </Page>
  );
}
