import { createFileRoute } from "@tanstack/react-router";
import { motion } from "motion/react";
import { ArrowUpRight, Sparkles, Wind, Droplets, Sun, Leaf } from "lucide-react";
import { AmbientBackground } from "@/components/aethera/AmbientBackground";
import { CommandDock } from "@/components/aethera/CommandDock";
import { AtmosphericOrb } from "@/components/aethera/AtmosphericOrb";
import { ComfortRing } from "@/components/aethera/ComfortRing";
import { WaveTimeline } from "@/components/aethera/WaveTimeline";
import { Reveal } from "@/components/aethera/Reveal";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  return (
    <main className="relative min-h-screen overflow-x-hidden">
      <AmbientBackground />
      <TopBar />

      <Hero />
      <IntelligenceStream />
      <ExposureLandscape />
      <ForecastChapter />
      <Companion />
      <Footer />

      <CommandDock />
    </main>
  );
}

/* ─────────────────────────── TOP BAR ─────────────────────────── */

function TopBar() {
  return (
    <header className="fixed left-0 right-0 top-0 z-40">
      <div className="mx-auto flex max-w-[1400px] items-center justify-between px-6 py-6 md:px-10">
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className="flex items-center gap-3"
        >
          <div className="relative h-7 w-7">
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-accent to-cyan blur-md opacity-70" />
            <div className="relative h-7 w-7 rounded-full border border-foreground/20 bg-gradient-to-br from-accent to-cyan" />
          </div>
          <span className="font-display text-lg tracking-tight">Aethera</span>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 1.2 }}
          className="hidden items-center gap-2 rounded-full border border-border/60 bg-background/40 px-4 py-2 text-[11px] uppercase tracking-[0.25em] text-muted-foreground backdrop-blur-xl md:flex"
        >
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          Live · Berlin · 14:32
        </motion.div>
      </div>
    </header>
  );
}

/* ─────────────────────────── HERO ─────────────────────────── */

function Hero() {
  return (
    <section className="relative flex min-h-[100svh] items-center px-6 pt-32 md:px-10">
      <div className="mx-auto grid w-full max-w-[1400px] grid-cols-1 items-center gap-16 lg:grid-cols-[1.05fr_1fr]">
        {/* left: recommendation copy */}
        <div className="relative z-10">
          <Reveal>
            <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.35em] text-muted-foreground">
              <span className="hairline w-10" />
              Today's Guidance
            </div>
          </Reveal>

          <Reveal delay={0.15}>
            <h1 className="mt-8 font-display text-[13vw] font-light leading-[0.95] tracking-[-0.03em] text-balance md:text-[6.2rem] lg:text-[7.2rem]">
              Breathe
              <br />
              <span className="italic text-foreground/70">easily.</span>
            </h1>
          </Reveal>

          <Reveal delay={0.35}>
            <p className="mt-10 max-w-[46ch] text-pretty text-lg leading-relaxed text-muted-foreground md:text-xl">
              The atmosphere is generous today. Pollen has drifted north, humidity
              settles into comfort, and UV remains soft. It is a rare, considered
              day — spend it outside.
            </p>
          </Reveal>

          <Reveal delay={0.55}>
            <div className="mt-12 flex flex-wrap items-center gap-8">
              <button className="group inline-flex items-center gap-3 rounded-full bg-foreground px-6 py-3.5 text-sm font-medium tracking-wide text-primary-foreground transition-all hover:gap-4 hover:bg-foreground/90">
                Read the full brief
                <ArrowUpRight className="h-4 w-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" strokeWidth={1.5} />
              </button>

              <div className="flex items-center gap-3 text-xs uppercase tracking-[0.28em] text-muted-foreground">
                <div className="flex h-6 items-center gap-1">
                  {[0.9, 0.7, 0.5, 0.35, 0.2].map((o, i) => (
                    <span
                      key={i}
                      className="block h-full w-[3px] rounded-sm bg-accent"
                      style={{ opacity: i < 4 ? 1 : 0.25, transform: `scaleY(${o})` }}
                    />
                  ))}
                </div>
                Confidence · 94%
              </div>
            </div>
          </Reveal>

          <Reveal delay={0.75}>
            <div className="mt-16 grid max-w-lg grid-cols-3 gap-6 border-t border-border/60 pt-8">
              <MicroStat icon={Wind} label="Wind" value="12" unit="km/h" />
              <MicroStat icon={Droplets} label="Humidity" value="48" unit="%" />
              <MicroStat icon={Sun} label="UV" value="3" unit="Low" />
            </div>
          </Reveal>
        </div>

        {/* right: orb */}
        <Reveal delay={0.2}>
          <div className="relative">
            <AtmosphericOrb value={34} />
          </div>
        </Reveal>
      </div>

      {/* subtle scroll cue */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.8, duration: 1.5 }}
        className="pointer-events-none absolute inset-x-0 bottom-8 flex justify-center"
      >
        <div className="flex flex-col items-center gap-3 text-[10px] uppercase tracking-[0.4em] text-muted-foreground/70">
          <span>Scroll</span>
          <span className="block h-8 w-px animate-float-y bg-gradient-to-b from-foreground/60 to-transparent" />
        </div>
      </motion.div>
    </section>
  );
}

function MicroStat({
  icon: Icon,
  label,
  value,
  unit,
}: {
  icon: typeof Wind;
  label: string;
  value: string;
  unit: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />
        <span className="text-[10px] uppercase tracking-[0.25em]">{label}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="font-display text-3xl font-light tracking-tight">{value}</span>
        <span className="text-xs text-muted-foreground">{unit}</span>
      </div>
    </div>
  );
}

/* ─────────────────────────── INTELLIGENCE STREAM ─────────────────────────── */

function IntelligenceStream() {
  const lines = [
    "The morning air carried unusually low particulate matter — 8 μg/m³ before sunrise.",
    "A soft northerly breeze cleared residual ozone from yesterday's warm afternoon.",
    "Pollen count sits well below your sensitivity threshold. No adjustment needed.",
    "Expect these conditions to hold through the golden hour. A long walk is well-placed.",
  ];

  return (
    <section className="relative px-6 py-40 md:px-10">
      <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-20 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <Reveal>
            <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.35em] text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5 text-accent" strokeWidth={1.5} />
              Aethera Intelligence
            </div>
          </Reveal>
          <Reveal delay={0.15}>
            <h2 className="mt-8 font-display text-6xl font-light leading-[1.02] tracking-tight text-balance md:text-7xl">
              A quiet <span className="italic text-foreground/60">narration</span> of the day.
            </h2>
          </Reveal>
          <Reveal delay={0.3}>
            <p className="mt-8 max-w-md text-muted-foreground">
              Numbers alone rarely tell a story. Aethera reads the atmosphere for you
              and translates it into a single, thoughtful voice.
            </p>
          </Reveal>
        </div>

        <div className="relative">
          <div className="glass rounded-3xl p-10">
            <div className="mb-8 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
                <span className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
                  Streaming · Model Æ-4
                </span>
              </div>
              <span className="font-mono text-[11px] text-muted-foreground">14:32:07</span>
            </div>

            <div className="space-y-5 font-display text-2xl font-light leading-relaxed text-foreground/90">
              {lines.map((l, i) => (
                <Reveal key={i} delay={0.1 + i * 0.15}>
                  <p>
                    <span className="text-muted-foreground">—</span> {l}
                  </p>
                </Reveal>
              ))}
              <Reveal delay={0.8}>
                <div className="mt-4 inline-flex items-center gap-2 text-base">
                  <span className="inline-block h-4 w-[3px] animate-pulse bg-accent" />
                  <span className="text-muted-foreground">Aethera is composing…</span>
                </div>
              </Reveal>
            </div>

            <div className="mt-10 flex flex-wrap gap-2">
              {["Why so clean?", "Best hours for outdoors", "Weekly outlook"].map((s) => (
                <button
                  key={s}
                  className="rounded-full border border-border/60 px-4 py-2 text-xs text-muted-foreground transition-all hover:border-accent/50 hover:bg-accent/5 hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* floating capsule */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 1, delay: 0.6 }}
            className="glass absolute -right-4 -top-6 hidden rounded-2xl px-5 py-4 md:block"
          >
            <div className="flex items-center gap-3">
              <div className="grid h-9 w-9 place-items-center rounded-full bg-accent/15">
                <Leaf className="h-4 w-4 text-accent" strokeWidth={1.5} />
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                  Allergen index
                </div>
                <div className="font-display text-xl">Low · 12</div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────── EXPOSURE LANDSCAPE ─────────────────────────── */

function ExposureLandscape() {
  return (
    <section className="relative px-6 py-40 md:px-10">
      <div className="mx-auto max-w-[1400px]">
        <Reveal>
          <div className="mb-20 flex flex-col items-start gap-6 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-[0.35em] text-muted-foreground">
                Comfort Rings
              </div>
              <h2 className="mt-4 font-display text-5xl font-light tracking-tight md:text-6xl">
                Your exposure, <span className="italic text-foreground/60">at a glance.</span>
              </h2>
            </div>
            <p className="max-w-sm text-muted-foreground">
              Six atmospheric dimensions, calibrated to your personal sensitivity
              profile. Nothing screams — everything informs.
            </p>
          </div>
        </Reveal>

        <div className="grid grid-cols-2 gap-x-6 gap-y-14 md:grid-cols-3 lg:grid-cols-6">
          <Reveal delay={0.05}><ComfortRing value={92} label="Air" sublabel="AQI" hue="162" /></Reveal>
          <Reveal delay={0.12}><ComfortRing value={78} label="Pollen" sublabel="Low" hue="78" /></Reveal>
          <Reveal delay={0.19}><ComfortRing value={64} label="UV" sublabel="Idx 3" hue="35" /></Reveal>
          <Reveal delay={0.26}><ComfortRing value={48} label="Humidity" sublabel="%" hue="210" /></Reveal>
          <Reveal delay={0.33}><ComfortRing value={85} label="Ozone" sublabel="Good" hue="190" /></Reveal>
          <Reveal delay={0.40}><ComfortRing value={71} label="Comfort" sublabel="Score" hue="145" /></Reveal>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────── FORECAST CHAPTER ─────────────────────────── */

function ForecastChapter() {
  const days = [
    { d: "Sat", t: "72", cond: "Clear", val: 28 },
    { d: "Sun", t: "70", cond: "Breeze", val: 22 },
    { d: "Mon", t: "68", cond: "Haze", val: 54 },
    { d: "Tue", t: "74", cond: "Warm", val: 62 },
    { d: "Wed", t: "76", cond: "Humid", val: 71 },
    { d: "Thu", t: "71", cond: "Rain", val: 38 },
    { d: "Fri", t: "69", cond: "Clear", val: 24 },
  ];
  return (
    <section className="relative px-6 py-40 md:px-10">
      <div className="mx-auto max-w-[1400px]">
        <div className="grid grid-cols-1 gap-20 lg:grid-cols-[0.85fr_1.15fr]">
          <Reveal>
            <div>
              <div className="text-[11px] uppercase tracking-[0.35em] text-muted-foreground">
                Adaptive Timeline
              </div>
              <h2 className="mt-4 font-display text-6xl font-light leading-[1.02] tracking-tight">
                The next <span className="italic text-foreground/60">seven mornings.</span>
              </h2>
              <p className="mt-8 max-w-md text-muted-foreground">
                A continuous wave, not a bar chart. Read the atmosphere as it rises
                and softens across the week.
              </p>

              <div className="mt-10 flex gap-6 text-xs text-muted-foreground">
                <Legend color="oklch(0.75 0.11 162)" label="Air Quality" />
                <Legend color="oklch(0.82 0.11 78)" label="Pollen" />
                <Legend color="oklch(0.78 0.09 210)" label="Humidity" />
              </div>
            </div>
          </Reveal>

          <Reveal delay={0.2}>
            <div className="glass rounded-3xl p-8 md:p-12">
              <WaveTimeline />
              <div className="mt-10 hairline" />
              <div className="mt-8 grid grid-cols-7 gap-3">
                {days.map((day, i) => (
                  <motion.div
                    key={day.d}
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.4 + i * 0.06, duration: 0.6 }}
                    className="group flex cursor-pointer flex-col items-center gap-2 rounded-2xl px-2 py-3 text-center transition-colors hover:bg-foreground/5"
                  >
                    <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                      {day.d}
                    </span>
                    <span className="font-display text-2xl font-light">{day.t}°</span>
                    <span className="text-[10px] text-muted-foreground">{day.cond}</span>
                    <span
                      className="mt-1 h-1 w-full rounded-full"
                      style={{
                        background: `linear-gradient(90deg, oklch(0.75 0.11 162 / 0.6) ${day.val}%, oklch(1 0 0 / 0.05) ${day.val}%)`,
                      }}
                    />
                  </motion.div>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      <span className="uppercase tracking-[0.22em]">{label}</span>
    </div>
  );
}

/* ─────────────────────────── COMPANION ─────────────────────────── */

function Companion() {
  return (
    <section className="relative px-6 py-40 md:px-10">
      <div className="mx-auto max-w-[1100px] text-center">
        <Reveal>
          <div className="text-[11px] uppercase tracking-[0.4em] text-muted-foreground">
            A companion, not a chatbot
          </div>
        </Reveal>
        <Reveal delay={0.15}>
          <h2 className="mt-8 font-display text-6xl font-light leading-[1.02] tracking-tight text-balance md:text-8xl">
            Ask the <span className="italic text-foreground/60">atmosphere</span> anything.
          </h2>
        </Reveal>

        <Reveal delay={0.35}>
          <div className="glass mx-auto mt-16 flex max-w-2xl items-center gap-4 rounded-full px-3 py-3 text-left">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-accent to-cyan">
              <Sparkles className="h-4 w-4 text-background" strokeWidth={2} />
            </div>
            <input
              className="min-w-0 flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
              placeholder="Is it safe to run at sunset?"
            />
            <button className="shrink-0 rounded-full bg-foreground px-5 py-2.5 text-xs uppercase tracking-[0.2em] text-primary-foreground transition hover:opacity-90">
              Ask
            </button>
          </div>
        </Reveal>

        <Reveal delay={0.5}>
          <div className="mt-8 flex flex-wrap justify-center gap-2 text-xs text-muted-foreground">
            {[
              "Should I open the windows?",
              "When is the cleanest air today?",
              "Plan a two-hour walk",
              "Weekly allergy outlook",
            ].map((s) => (
              <button
                key={s}
                className="rounded-full border border-border/60 px-4 py-2 transition-all hover:border-accent/50 hover:text-foreground"
              >
                {s}
              </button>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ─────────────────────────── FOOTER ─────────────────────────── */

function Footer() {
  return (
    <footer className="relative border-t border-border/60 px-6 py-16 md:px-10">
      <div className="mx-auto flex max-w-[1400px] flex-col items-start justify-between gap-8 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-3">
            <div className="h-6 w-6 rounded-full bg-gradient-to-br from-accent to-cyan" />
            <span className="font-display text-lg">Aethera</span>
          </div>
          <p className="mt-4 max-w-sm text-sm text-muted-foreground">
            Environmental intelligence, considered.
            <br />
            © 2026 Aethera Systems.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-x-12 gap-y-3 text-xs uppercase tracking-[0.25em] text-muted-foreground">
          <a className="hover:text-foreground" href="#">Manifesto</a>
          <a className="hover:text-foreground" href="#">Science</a>
          <a className="hover:text-foreground" href="#">Contact</a>
          <a className="hover:text-foreground" href="#">Privacy</a>
          <a className="hover:text-foreground" href="#">Press</a>
          <a className="hover:text-foreground" href="#">Careers</a>
        </div>
      </div>
    </footer>
  );
}
