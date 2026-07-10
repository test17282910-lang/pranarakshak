import { motion, useInView } from "motion/react";
import { useMemo, useRef } from "react";

const hours = ["05", "08", "11", "14", "17", "20", "23"];

export function WaveTimeline() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-10%" });

  // deterministic wave data
  const points = useMemo(() => {
    const n = 48;
    const pts: { x: number; y: number }[] = [];
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * 100;
      const y =
        50 -
        (Math.sin(i * 0.35) * 12 +
          Math.sin(i * 0.15 + 1.4) * 8 +
          Math.cos(i * 0.9) * 3);
      pts.push({ x, y });
    }
    return pts;
  }, []);

  const path = useMemo(() => {
    return points
      .map((p, i) => {
        if (i === 0) return `M ${p.x} ${p.y}`;
        const prev = points[i - 1];
        const cx = (prev.x + p.x) / 2;
        return `Q ${cx} ${prev.y} ${p.x} ${p.y}`;
      })
      .join(" ");
    }, [points]);

  const area = `${path} L 100 100 L 0 100 Z`;

  return (
    <div ref={ref} className="relative w-full">
      <svg viewBox="0 0 100 60" preserveAspectRatio="none" className="h-64 w-full">
        <defs>
          <linearGradient id="wave-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="oklch(0.75 0.11 162)" stopOpacity="0.4" />
            <stop offset="100%" stopColor="oklch(0.75 0.11 162)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="wave-line" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="oklch(0.78 0.09 210)" />
            <stop offset="50%" stopColor="oklch(0.85 0.12 165)" />
            <stop offset="100%" stopColor="oklch(0.82 0.11 78)" />
          </linearGradient>
        </defs>

        {/* grid hairlines */}
        {[15, 30, 45].map((y) => (
          <line
            key={y}
            x1="0" x2="100" y1={y} y2={y}
            stroke="oklch(1 0 0 / 0.05)"
            strokeWidth="0.15"
          />
        ))}

        <motion.path
          d={area}
          fill="url(#wave-fill)"
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ duration: 1.2, delay: 0.4 }}
        />
        <motion.path
          d={path}
          fill="none"
          stroke="url(#wave-line)"
          strokeWidth="0.5"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={inView ? { pathLength: 1 } : {}}
          transition={{ duration: 2, ease: [0.16, 1, 0.3, 1] }}
        />

        {/* now marker */}
        <motion.circle
          cx="35"
          cy={points[Math.round((35 / 100) * (points.length - 1))].y}
          r="0.9"
          fill="oklch(0.85 0.12 165)"
          initial={{ scale: 0 }}
          animate={inView ? { scale: 1 } : {}}
          transition={{ delay: 1.8, type: "spring", stiffness: 300 }}
        >
          <animate attributeName="r" values="0.9;1.4;0.9" dur="2s" repeatCount="indefinite" />
        </motion.circle>
      </svg>

      <div className="mt-4 flex justify-between px-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {hours.map((h) => <span key={h}>{h}</span>)}
      </div>
    </div>
  );
}
