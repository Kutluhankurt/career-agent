import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { errorMessage, MOCK } from "../api/client";
import { usePatchBullet, useRegenerateCV, useCV } from "../api/hooks";
import type { CV, CVBullet, Evidence } from "../api/types";
import { useToast } from "../components/Toast";
import { EmptyState, ErrorNote, Page, Skeleton, Dot } from "../components/ui";
import { useDismiss } from "../lib/hooks";
import { confidenceLabel, projectColor, relativeTime } from "../lib/format";

interface Line {
  d: string;
  key: string;
}

function toMarkdown(cv: CV): string {
  const lines = [`# ${cv.name}`, cv.title, "", cv.summary, "", "## Experience"];
  for (const e of cv.experience) lines.push("", `### ${e.project}`, ...e.bullets.map((b) => `- ${b.text}`));
  lines.push("", "## Skills", cv.skills.join(", "), "");
  return lines.join("\n");
}

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

function ExportMenu({ cv }: { cv: CV }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { show } = useToast();
  useDismiss(open, () => setOpen(false), ref);
  const items: { f: "md" | "docx" | "pdf" | "json"; label: string }[] = [
    { f: "md", label: "Markdown" },
    { f: "docx", label: "Word" },
    { f: "pdf", label: "PDF" },
    { f: "json", label: "JSON" },
  ];
  return (
    <div className="more" ref={ref}>
      <button className="pill" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>Export ▾</button>
      <AnimatePresence>
        {open && (
          <motion.div className="menu left" role="menu" initial={{ opacity: 0, y: -6, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, transition: { duration: 0.12 } }} transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}>
            {items.map((i) => (
              <a
                key={i.f}
                role="menuitem"
                href={`/api/cv/export?format=${i.f}`}
                download
                onClick={(e) => {
                  setOpen(false);
                  if (!MOCK) return;
                  e.preventDefault();
                  if (i.f === "md") download("cv.md", toMarkdown(cv), "text/markdown");
                  else if (i.f === "json") download("cv.json", JSON.stringify(cv, null, 2), "application/json");
                  else show(`${i.label} export needs the real server.`);
                }}
              >
                {i.label}
              </a>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Bullet({ b, fresh, active, onHover, onEdit, editing, onCancel, onSave, saving, error }: {
  b: CVBullet; fresh: boolean; active: boolean; editing: boolean; saving: boolean; error: string | null;
  onHover: (id: string | null) => void; onEdit: () => void; onCancel: () => void; onSave: (t: string) => void;
}) {
  const [text, setText] = useState(b.text);
  useEffect(() => {
    if (editing) setText(b.text);
  }, [editing, b.text]);
  return (
    <motion.div
      layout="position"
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.5, ease: [0.25, 1, 0.5, 1] }}
      style={{ overflow: "hidden" }}
    >
      {editing ? (
        <div className="bl editing">
          <textarea
            className="field"
            aria-label="Edit line"
            autoFocus
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && text.trim()) {
                e.preventDefault();
                onSave(text.trim());
              }
              if (e.key === "Escape") {
                e.stopPropagation();
                onCancel();
              }
            }}
          />
          <div className="row-flex" style={{ marginTop: 8 }}>
            <button className="pill primary" disabled={saving || !text.trim()} onClick={() => onSave(text.trim())}>Save</button>
            <button className="pill" onClick={onCancel}>Cancel</button>
            <span className="meta">Enter to save · Esc to cancel</span>
          </div>
          {error && <p className="err" role="alert">{error}</p>}
        </div>
      ) : (
        <div
          className={`bl ${fresh ? "fresh" : ""} ${active ? "on" : ""}`}
          data-bullet={b.id}
          role="button"
          tabIndex={0}
          aria-label={`${b.text} Click to edit.`}
          onMouseEnter={() => onHover(b.id)}
          onMouseLeave={() => onHover(null)}
          onFocus={() => onHover(b.id)}
          onBlur={() => onHover(null)}
          onClick={onEdit}
          onKeyDown={(e) => e.key === "Enter" && onEdit()}
        >
          {b.state !== "confirmed" && b.state !== "observed" && <span className="state s-inferred" title="Needs review"><i aria-hidden /><span className="sr">Needs review. </span></span>}
          {b.text}
          {b.weak && <span className="w">Needs more evidence</span>}
        </div>
      )}
    </motion.div>
  );
}

function CVSkeleton() {
  return (
    <div className="cv" aria-busy="true" aria-label="Loading">
      <div className="paper">
        <Skeleton w="50%" h={34} />
        <Skeleton w="35%" h={16} style={{ margin: "10px 0 36px" }} />
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} h={16} style={{ marginBottom: 14, width: `${95 - i * 12}%` }} />)}
      </div>
      <div><Skeleton w={80} h={14} />{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} h={16} style={{ marginTop: 22 }} />)}</div>
    </div>
  );
}

export default function CVPage() {
  const q = useCV();
  const regen = useRegenerateCV();
  const patch = usePatchBullet();
  const { show } = useToast();
  const [hover, setHover] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const wrapRef = useRef<HTMLDivElement>(null);
  const cv = q.data;

  const bullets = useMemo(() => (cv ? cv.experience.flatMap((e) => e.bullets) : []), [cv]);
  const evidence = useMemo(() => {
    const m = new Map<string, Evidence>();
    for (const b of bullets) for (const e of b.evidence) if (!m.has(e.id)) m.set(e.id, e);
    return [...m.values()];
  }, [bullets]);
  const hovered = bullets.find((b) => b.id === hover) ?? null;
  const lit = useMemo(() => new Set(hovered?.evidence.map((e) => e.id)), [hovered]);

  // Thin curved connectors from the hovered line to what proves it (hidden under 860px by CSS).
  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || !hovered || getComputedStyle(wrap.querySelector(".lines") as Element).display === "none") {
      setLines([]);
      return;
    }
    const W = wrap.getBoundingClientRect();
    const el = wrap.querySelector<HTMLElement>(`[data-bullet="${hovered.id}"]`);
    if (!el) return;
    const br = el.getBoundingClientRect();
    setLines(
      hovered.evidence.flatMap((e) => {
        const t = wrap.querySelector<HTMLElement>(`[data-ev="${e.id}"]`);
        if (!t) return [];
        const r = t.getBoundingClientRect();
        const x1 = br.right - W.left + 12;
        const y1 = br.top + br.height / 2 - W.top;
        const x2 = r.left - W.left - 8;
        const y2 = r.top + r.height / 2 - W.top;
        const mx = (x1 + x2) / 2;
        return [{ key: `${hovered.id}-${e.id}`, d: `M${x1} ${y1} C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}` }];
      }),
    );
  }, [hovered, cv]);

  const regenerate = useCallback(() => {
    const before = new Set(bullets.map((b) => b.id));
    regen.mutate(undefined, {
      onSuccess: (next) => {
        const added = next.experience.flatMap((e) => e.bullets).filter((b) => !before.has(b.id)).map((b) => b.id);
        setFresh(new Set(added));
        setTimeout(() => setFresh(new Set()), 5000);
        show(added.length ? `${added.length} new ${added.length === 1 ? "line" : "lines"} written from your work` : "Nothing new to add");
      },
      onError: (e) => show(errorMessage(e)),
    });
  }, [bullets, regen, show]);

  const save = (id: string, text: string) => {
    setError(null);
    patch.mutate({ id, text }, { onSuccess: () => { setEditing(null); show("Saved and confirmed"); }, onError: (e) => setError(errorMessage(e)) });
  };

  return (
    <Page eyebrow="CV" title="Written from real work." lede="Point at any line to see what proves it.">
      {q.isError ? (
        <ErrorNote error={q.error} onRetry={() => void q.refetch()} />
      ) : !cv ? (
        <CVSkeleton />
      ) : (
        <>
          <div className="row-flex in" style={{ marginBottom: 28 }}>
            <button className="pill primary" disabled={regen.isPending} onClick={regenerate}>{regen.isPending ? "Writing…" : "Regenerate"}</button>
            <ExportMenu cv={cv} />
            {cv.generated_at && <span className="meta">Last written {relativeTime(cv.generated_at)}</span>}
          </div>
          {bullets.length === 0 ? (
            <EmptyState title="Nothing to write yet." action={<button className="pill primary" onClick={regenerate}>Regenerate</button>}>
              Once a few sessions are confirmed, your experience lines will be written here from real evidence.
            </EmptyState>
          ) : (
            <div className="cv in" ref={wrapRef}>
              <article className="paper">
                <div className="name">{cv.name}</div>
                <div className="role">{cv.title}</div>
                {cv.summary && <p className="summary">{cv.summary}</p>}
                <div className="sec">Experience</div>
                {cv.experience.map((e) => (
                  <section key={e.project}>
                    <div className="pj"><Dot color={projectColor(e.color)} /> {e.project}</div>
                    <AnimatePresence initial={false}>
                      {e.bullets.map((b) => (
                        <Bullet
                          key={b.id}
                          b={b}
                          fresh={fresh.has(b.id)}
                          active={hover === b.id}
                          editing={editing === b.id}
                          saving={patch.isPending}
                          error={error}
                          onHover={setHover}
                          onEdit={() => { setError(null); setEditing(b.id); }}
                          onCancel={() => setEditing(null)}
                          onSave={(t) => save(b.id, t)}
                        />
                      ))}
                    </AnimatePresence>
                  </section>
                ))}
                {cv.skills.length > 0 && (
                  <>
                    <div className="sec">Skills</div>
                    <div className="skills-line">{cv.skills.join(" · ")}</div>
                  </>
                )}
              </article>

              <aside className={`evi ${hovered ? "focus" : ""}`} aria-label="Evidence">
                <div className="lbl">
                  {hovered ? `${confidenceLabel(hovered.confidence)} · ${hovered.evidence.length} ${hovered.evidence.length === 1 ? "proof" : "proofs"}` : "Evidence"}
                </div>
                {evidence.map((e) => (
                  <div key={e.id} data-ev={e.id} className={`e ${lit.has(e.id) ? "lit" : ""}`}>
                    <span className="ty">{e.label}</span>
                    {e.value}
                  </div>
                ))}
                {!hovered && <p className="meta" style={{ marginTop: 18 }}>Lines without enough evidence are marked, so you never claim more than you can show.</p>}
              </aside>
              <svg className="lines" aria-hidden>
                {lines.map((l) => <path key={l.key} d={l.d} />)}
              </svg>
            </div>
          )}
        </>
      )}
    </Page>
  );
}
