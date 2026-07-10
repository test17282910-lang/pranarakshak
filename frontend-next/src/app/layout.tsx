import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AQI Health Alert — Breathe Intelligently",
  description: "Personalised AQI predictions and health alerts tailored to your respiratory condition. Real-time CPCB India station data.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  // Generate deterministic particles to keep Server Component static
  const particles = Array.from({ length: 25 }, (_, i) => {
    const seed = (i * 9301 + 49297) % 233280;
    const left = (seed / 233280) * 100;
    const delay = ((seed * 13) % 100) / 10;
    const dur = 18 + ((seed * 7) % 20);
    const size = 1.5 + ((seed * 3) % 3);
    return { left, delay, dur, size };
  });

  return (
    <html lang="en">
      <body>
        {/* Ambient atmospheric background with drifting orbs and rising particles */}
        <div className="ambient-bg" aria-hidden>
          <div className="orb-1" />
          <div className="orb-2" />
          <div className="orb-3" />
          
          {/* Animated rising particles */}
          <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
            {particles.map((p, i) => (
              <span
                key={i}
                style={{
                  position: "absolute",
                  bottom: "-5vh",
                  left: `${p.left}%`,
                  width: p.size,
                  height: p.size,
                  borderRadius: "50%",
                  background: "rgba(255, 255, 255, 0.25)",
                  animation: `particle ${p.dur}s linear ${p.delay}s infinite`,
                  filter: "blur(0.5px)",
                }}
              />
            ))}
          </div>

          <div className="vignette-top" />
          <div className="vignette-bottom" />
        </div>
        {children}
      </body>
    </html>
  );
}
