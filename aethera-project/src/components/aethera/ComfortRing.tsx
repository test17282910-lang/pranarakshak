import { motion, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";

export function ComfortRing({
  value,
  label,
  sublabel,
  size = 160,
  hue = "162",
}: {
  value: number; // 0-100
  label: string;
  sublabel?: string;
  size?: number;
  hue?: string;
}) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-15%" });
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const dur = 1400;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(Math.round(eased * value));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, value]);

  const r = 45;
  const c = 2 * Math.PI * r;

  return (
    <div ref={ref} className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle
            cx="50" cy="50" r={r}
            fill="none"
            stroke="oklch(1 0 0 / 0.06)"
            strokeWidth="2"
          />
          <motion.circle
            cx="50" cy="50" r={r}
            fill="none"
            stroke={`oklch(0.78 0.10 ${hue})`}
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray={c}
            initial={{ strokeDashoffset: c }}
            animate={inView ? { strokeDashoffset: c - (c * value) / 100 } : {}}
            transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1] }}
            style={{ filter: `drop-shadow(0 0 8px oklch(0.78 0.10 ${hue} / 0.6))` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-4xl font-light">{display}</span>
          {sublabel && (
            <span className="mt-0.5 text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              {sublabel}
            </span>
          )}
        </div>
      </div>
      <span className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
        {label}
      </span>
    </div>
  );
}
