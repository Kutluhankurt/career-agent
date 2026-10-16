import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";

interface ToastOpts {
  undo?: () => void;
  ms?: number;
}
interface ToastState extends ToastOpts {
  id: number;
  message: string;
}
const Ctx = createContext<{ show: (message: string, opts?: ToastOpts) => void; hide: () => void }>({ show: () => {}, hide: () => {} });
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const timer = useRef<number>(0);
  const seq = useRef(0);
  const hide = useCallback(() => {
    window.clearTimeout(timer.current);
    setToast(null);
  }, []);
  const show = useCallback((message: string, opts: ToastOpts = {}) => {
    window.clearTimeout(timer.current);
    setToast({ id: ++seq.current, message, ...opts });
    timer.current = window.setTimeout(() => setToast(null), opts.ms ?? 4000);
  }, []);
  const value = useMemo(() => ({ show, hide }), [show, hide]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toast-host" aria-live="polite">
        <AnimatePresence>
          {toast && (
            <motion.div
              key={toast.id}
              className="toast"
              initial={{ opacity: 0, y: 20, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.97, transition: { duration: 0.2 } }}
              transition={{ duration: 0.45, ease: [0.25, 1, 0.5, 1] }}
            >
              <span>{toast.message}</span>
              {toast.undo && (
                <button
                  onClick={() => {
                    toast.undo?.();
                    hide();
                  }}
                >
                  Undo
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Ctx.Provider>
  );
}
