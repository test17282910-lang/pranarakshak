import { motion } from "motion/react";

/** Living centerpiece — a breathing atmospheric core with orbiting rings. */
export function AtmosphericOrb({ value = 34 }: { value?: number }) {
  const rings = [
    { size: 520, dur: 60, opacity: 0.10, dash: "1 12" },
    { size: 420, dur: 45, reverse: true, opacity: 0.14, dash: "2 8" },
    { size: 340, dur: 30, opacity: 0.18, dash: "1 6" },
  ];

  return (
    <div className="relative mx-auto flex aspect-square w-full max-w-[560px] items-center justify-center">
      {/* concentric rotating rings */}
      {rings.map((r, i) => (
        <motion.svg
          key={i}
          viewBox="0 0 100 100"
          className="absolute"
          style={{ width: r.size, height: r.size, opacity: r.opacity }}
          animate={{ rotate: r.reverse ? -360 : 360 }}
          transition={{ duration: r.dur, ease: "linear", repeat: Infinity }}
        >
          <circle
            cx="50" cy="50" r="48"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.15"
            strokeDasharray={r.dash}
            className="text-foreground"
          />
        </motion.svg>
      ))}

      {/* tick marks */}
      <svg viewBox="0 0 100 100" className="absolute h-[600px] w-[600px] opacity-40">
        {Array.from({ length: 72 }).map((_, i) => {
          const angle = (i / 72) * Math.PI * 2;
          const long = i % 6 === 0;
          const inner = long ? 44 : 45.5;
          const outer = 47;
          const x1 = 50 + Math.cos(angle) * inner;
          const y1 = 50 + Math.sin(angle) * inner;
          const x2 = 50 + Math.cos(angle) * outer;
          const y2 = 50 + Math.sin(angle) * outer;
          return (
            <line
              key={i}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="currentColor"
              strokeWidth={long ? 0.25 : 0.1}
              className="text-foreground"
            />
          );
        })}
      </svg>

      {/* core orb */}
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative"
      >
        <div
          className="animate-orb h-[280px] w-[280px] rounded-full"
          style={{
            background: "var(--gradient-orb)",
            boxShadow:
              "inset -20px -30px 60px oklch(0 0 0 / 0.5), inset 20px 30px 60px oklch(1 0 0 / 0.15), 0 0 120px oklch(0.75 0.11 162 / 0.35)",
          }}
        />
        {/* highlight */}
        <div
          className="pointer-events-none absolute left-8 top-6 h-24 w-24 rounded-full blur-2xl"
          style={{ background: "oklch(1 0 0 / 0.35)" }}
        />
        {/* AQI numeral */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-[11px] uppercase tracking-[0.3em] text-foreground/60">
            Air Quality
          </span>
          <motion.span
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.9 }}
            className="font-display text-[110px] font-light leading-none tracking-tight text-foreground"
          >
            {value}
          </motion.span>
          <span className="mt-1 text-xs uppercase tracking-[0.3em] text-accent">
            Excellent
          </span>
        </div>
      </motion.div>
    </div>
  );
}
