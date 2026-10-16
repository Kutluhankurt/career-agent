import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";

const EASE = [0.25, 1, 0.5, 1] as const;

/** Floating rounded sheet that settles in from the right. */
export function Sheet({ open, onClose, label, children }: { open: boolean; onClose: () => void; label: string; children: ReactNode }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const returnTo = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return;
    returnTo.current = document.activeElement;
    const t = setTimeout(() => closeRef.current?.focus(), 60);
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", key);
      (returnTo.current as HTMLElement | null)?.focus?.();
    };
  }, [open, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="scrim"
            className="scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: EASE }}
            onClick={onClose}
          />
          <motion.aside
            key="sheet"
            className="sheet"
            role="dialog"
            aria-modal="true"
            aria-label={label}
            initial={{ x: "calc(100% + 24px)", opacity: 0.6 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "calc(100% + 24px)", opacity: 0 }}
            transition={{ duration: 0.55, ease: EASE }}
          >
            <button ref={closeRef} className="x" onClick={onClose} aria-label="Close">
              ✕
            </button>
            {children}
          </motion.aside>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** Staggered reveal for sheet sections. */
export function Stagger({ children }: { children: ReactNode[] }) {
  return (
    <>
      {children.map((c, i) => (
        <div key={i} className="in-s" style={{ animationDelay: `${0.1 + i * 0.05}s` }}>
          {c}
        </div>
      ))}
    </>
  );
}
