/** Signature moment: a confirmed card shrinks and flies into the Memory tab, which then bumps. */
export const MEMORY_BUMP = "ca-memory-bump";
export const MEMORY_UNBUMP = "ca-memory-unbump";

export function bumpMemory(delta: 1 | -1 = 1) {
  window.dispatchEvent(new CustomEvent(delta === 1 ? MEMORY_BUMP : MEMORY_UNBUMP));
}

function target(): HTMLElement | null {
  return [...document.querySelectorAll<HTMLElement>("[data-mem-target]")].find((b) => b.offsetParent !== null) ?? null;
}

export function flyToMemory(el: HTMLElement | null) {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const t = target();
  if (!el || !t || reduced || typeof el.animate !== "function") {
    bumpMemory();
    return;
  }
  const r = el.getBoundingClientRect();
  const tr = t.getBoundingClientRect();
  const g = el.cloneNode(true) as HTMLElement;
  g.removeAttribute("id");
  g.classList.add("ghost");
  Object.assign(g.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px`, margin: "0", transition: "none" });
  document.body.appendChild(g);
  const dx = tr.left + tr.width / 2 - (r.left + r.width / 2);
  const dy = tr.top + tr.height / 2 - (r.top + r.height / 2);
  const anim = g.animate(
    [
      { transform: "none", opacity: 1, borderRadius: "24px" },
      { transform: `translate(${dx * 0.25}px, ${dy * 0.25 - 40}px) scale(.6)`, opacity: 0.9, offset: 0.35 },
      { transform: `translate(${dx}px, ${dy}px) scale(.03)`, opacity: 0.2, borderRadius: "200px" },
    ],
    { duration: 750, easing: "cubic-bezier(.6,0,.25,1)" },
  );
  anim.onfinish = () => {
    g.remove();
    bumpMemory();
  };
}
