import { useEffect, useRef } from "react";

/**
 * Living atmospheric background:
 * - slow drifting gradient orbs
 * - floating particles
 * - parallax response to cursor
 */
export function AmbientBackground() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    let raf = 0;
    let tx = 0, ty = 0, cx = 0, cy = 0;
    const onMove = (e: MouseEvent) => {
      tx = (e.clientX / window.innerWidth - 0.5) * 20;
      ty = (e.clientY / window.innerHeight - 0.5) * 20;
    };
    const loop = () => {
      cx += (tx - cx) * 0.04;
      cy += (ty - cy) * 0.04;
      el.style.setProperty("--px", `${cx}px`);
      el.style.setProperty("--py", `${cy}px`);
      raf = requestAnimationFrame(loop);
    };
    window.addEventListener("mousemove", onMove);
    raf = requestAnimationFrame(loop);
    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  // deterministic particles
  const particles = Array.from({ length: 28 }, (_, i) => {
    const seed = (i * 9301 + 49297) % 233280;
    const left = (seed / 233280) * 100;
    const delay = ((seed * 13) % 100) / 10;
    const dur = 18 + ((seed * 7) % 20);
    const size = 1 + ((seed * 3) % 3);
    return { left, delay, dur, size };
  });

  return (
    <div ref={rootRef} aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* base gradient */}
      <div className="absolute inset-0 aether-bg" />
      {/* drifting orbs */}
      <div
        className="absolute -top-40 left-1/4 h-[70vh] w-[70vh] rounded-full opacity-70 blur-3xl animate-drift"
        style={{
          background:
            "radial-gradient(circle, oklch(0.75 0.11 162 / 0.35), transparent 65%)",
          transform: "translate(var(--px, 0), var(--py, 0))",
        }}
      />
      <div
        className="absolute bottom-[-30vh] right-[-10vh] h-[80vh] w-[80vh] rounded-full opacity-60 blur-3xl animate-drift-slow"
        style={{
          background:
            "radial-gradient(circle, oklch(0.78 0.09 210 / 0.30), transparent 65%)",
          transform: "translate(calc(var(--px, 0) * -1), calc(var(--py, 0) * -1))",
        }}
      />
      <div
        className="absolute top-1/3 right-1/3 h-[40vh] w-[40vh] rounded-full opacity-40 blur-3xl animate-drift"
        style={{
          background:
            "radial-gradient(circle, oklch(0.82 0.11 78 / 0.18), transparent 65%)",
        }}
      />

      {/* grain */}
      <div
        className="absolute inset-0 opacity-[0.035] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.9'/></svg>\")",
        }}
      />

      {/* particles */}
      <div className="absolute inset-0">
        {particles.map((p, i) => (
          <span
            key={i}
            className="absolute bottom-[-10vh] rounded-full bg-foreground/40"
            style={{
              left: `${p.left}%`,
              width: p.size,
              height: p.size,
              animation: `particle ${p.dur}s linear ${p.delay}s infinite`,
              filter: "blur(0.5px)",
            }}
          />
        ))}
      </div>

      {/* top vignette */}
      <div className="absolute inset-x-0 top-0 h-[30vh] bg-gradient-to-b from-background/60 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-[30vh] bg-gradient-to-t from-background to-transparent" />
    </div>
  );
}
