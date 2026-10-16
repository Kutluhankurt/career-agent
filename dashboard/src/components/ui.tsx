import { useId, type CSSProperties, type ReactNode } from "react";
import { motion } from "motion/react";
import type { TruthState } from "../api/types";
import { confidenceLabel, stateLabel } from "../lib/format";

/** Truth state as a small dot + word. Needs review = orange ring, Confirmed = green dot. */
export function TruthBadge({ state, label = true }: { state: TruthState; label?: boolean }) {
  return (
    <span className={`state s-${state}`}>
      <i aria-hidden />
      {label ? stateLabel(state) : <span className="sr">{stateLabel(state)}</span>}
    </span>
  );
}

export function Confidence({ value }: { value: number }) {
  const [word, pct] = confidenceLabel(value).split(" · ");
  return (
    <span>
      {word} <span className="meta num">· {pct}</span>
    </span>
  );
}

export function Skeleton({ w, h = 16, r, style, className = "" }: { w?: number | string; h?: number | string; r?: number | string; style?: CSSProperties; className?: string }) {
  return <span className={`skel ${className}`} style={{ width: w, height: h, borderRadius: r, ...style }} aria-hidden />;
}

export function Dot({ color }: { color: string }) {
  return <span className="pdot" style={{ background: color }} aria-hidden />;
}

export interface SegOption<T extends string> {
  value: T;
  label: string;
  badge?: number | null;
  badgeGrey?: boolean;
  bump?: boolean;
  attrs?: Record<string, string>;
}

/** Segmented control with a spring-driven thumb shared between options (layoutId). */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  className = "",
}: {
  value: T;
  options: SegOption<T>[];
  onChange: (v: T) => void;
  label: string;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={`seg ${className}`} role="tablist" aria-label={label}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={on}
            aria-current={on ? "page" : undefined}
            className={o.bump ? "bump" : undefined}
            onClick={() => onChange(o.value)}
            {...o.attrs}
          >
            {on && <motion.span layoutId={`thumb-${id}`} className="thumb" transition={{ type: "spring", stiffness: 380, damping: 32 }} />}
            <span className="seg-l">
              {o.label}
              {o.badge != null && o.badge > 0 && <span className={`badge num ${o.badgeGrey ? "grey" : ""}`}>{o.badge}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function Page({ eyebrow, title, lede, children }: { eyebrow?: string; title: string; lede?: ReactNode; children: ReactNode }) {
  return (
    <>
      {eyebrow && <p className="eyebrow in">{eyebrow}</p>}
      <h1 className="in">{title}</h1>
      {lede && <p className="lede in">{lede}</p>}
      {children}
    </>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card empty in">
      <div className="empty-ring" aria-hidden />
      <h3>{title}</h3>
      {children && <p className="meta">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="card empty in" role="alert">
      <h3>Couldn't load this.</h3>
      <p className="meta">{error instanceof Error ? error.message : "Something went wrong."}</p>
      {onRetry && (
        <button className="pill" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

const ico = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;
export const Icons = {
  today: (
    <svg {...ico} aria-hidden>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l3 2" />
    </svg>
  ),
  timeline: (
    <svg {...ico} aria-hidden>
      <rect x="4" y="5" width="16" height="15" rx="3" />
      <path d="M4 10h16M9 3v4M15 3v4" />
    </svg>
  ),
  review: (
    <svg {...ico} aria-hidden>
      <circle cx="12" cy="12" r="8" />
      <path d="m8.5 12 2.5 2.5 4.5-5" />
    </svg>
  ),
  memory: (
    <svg {...ico} aria-hidden>
      <path d="M5 7.5 12 4l7 3.5-7 3.5z" />
      <path d="m5 12 7 3.5 7-3.5M5 16.5 12 20l7-3.5" />
    </svg>
  ),
  cv: (
    <svg {...ico} aria-hidden>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M10 12h5M10 16h5" />
    </svg>
  ),
  more: (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <circle cx="6" cy="12" r="1.7" />
      <circle cx="12" cy="12" r="1.7" />
      <circle cx="18" cy="12" r="1.7" />
    </svg>
  ),
};
