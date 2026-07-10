import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Compass, Sparkles, Waves, Wind, User } from "lucide-react";

const items = [
  { icon: Compass, label: "Today" },
  { icon: Waves, label: "Atmosphere" },
  { icon: Wind, label: "Forecast" },
  { icon: Sparkles, label: "Insights" },
  { icon: User, label: "Profile" },
];

export function CommandDock() {
  const [visible, setVisible] = useState(true);
  const [active, setActive] = useState(0);
  const [hovered, setHovered] = useState<number | null>(null);

  useEffect(() => {
    let lastY = window.scrollY;
    let ticking = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const y = window.scrollY;
        if (y > lastY && y > 120) setVisible(false);
        else setVisible(true);
        lastY = y;
        ticking = false;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <AnimatePresence>
      {visible && (
        <motion.nav
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 24 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2"
        >
          <div className="glass flex items-center gap-1 rounded-full px-2 py-2">
            {items.map((it, i) => {
              const Icon = it.icon;
              const isActive = active === i;
              return (
                <button
                  key={it.label}
                  onClick={() => setActive(i)}
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                  className="group relative flex h-11 items-center gap-2 rounded-full px-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {isActive && (
                    <motion.div
                      layoutId="dock-active"
                      className="absolute inset-0 rounded-full bg-foreground/10"
                      transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    />
                  )}
                  <Icon className="relative h-4 w-4" strokeWidth={1.6} />
                  <AnimatePresence>
                    {(isActive || hovered === i) && (
                      <motion.span
                        initial={{ opacity: 0, width: 0 }}
                        animate={{ opacity: 1, width: "auto" }}
                        exit={{ opacity: 0, width: 0 }}
                        transition={{ duration: 0.25 }}
                        className="relative overflow-hidden whitespace-nowrap text-[13px] tracking-wide"
                      >
                        {it.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </button>
              );
            })}
          </div>
        </motion.nav>
      )}
    </AnimatePresence>
  );
}
