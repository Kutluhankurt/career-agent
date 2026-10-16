import { motion } from "motion/react";
import { useCopy } from "../lib/hooks";

export default function Offline() {
  const [copied, copy] = useCopy();
  return (
    <main className="center-screen">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.25, 1, 0.5, 1] }} style={{ textAlign: "center" }}>
        <span className="dot still" style={{ background: "var(--faint)", display: "inline-block", marginBottom: 24 }} aria-hidden />
        <h1>Career Agent isn't running.</h1>
        <p className="lede" style={{ margin: "0 auto 32px" }}>Start it from a terminal, then this page reconnects by itself.</p>
        <span className="cmd big">
          <code>career dashboard</code>
          <button className="pill" onClick={() => copy("career dashboard")}>{copied ? "Copied" : "Copy"}</button>
        </span>
      </motion.div>
    </main>
  );
}
