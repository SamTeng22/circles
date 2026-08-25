"use client";
import { useEffect, useRef } from "react";
import { PIG_EYES, PIG_FILL, PIG_FILL_ORDER, PIG_LINES, PIG_PARTS, PIG_STROKE, PIG_VIEWBOX, type PigPart } from "./pigArt";

const NS = "http://www.w3.org/2000/svg";

type PartRef = {
  fill?: SVGPathElement;
  stroke?: SVGPathElement;
  eyeG?: SVGGElement;
  dot?: SVGCircleElement;
  cfg?: { cx: number; cy: number; r: number };
};

/** The pig-drawing animation used as the site's loading state. */
export function PigLoader({
  label = "Loading",
  fullscreen = true,
  size = 200,
}: {
  label?: string;
  fullscreen?: boolean;
  size?: number;
}) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const pig = root.querySelector<SVGGElement>(".pig-fig")!;
    const fillsG = root.querySelector<SVGGElement>(".pig-fills")!;
    const linesG = root.querySelector<SVGGElement>(".pig-lines")!;
    const eyesG = root.querySelector<SVGGElement>(".pig-eyes")!;
    const nib = root.querySelector<SVGGElement>(".pig-nib")!;
    const nibDot = root.querySelector<SVGCircleElement>(".pig-nib-dot")!;

    function mk<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string>): SVGElementTagNameMap[K] {
      const el = document.createElementNS(NS, tag) as SVGElementTagNameMap[K];
      for (const k in attrs) el.setAttribute(k, attrs[k]);
      return el;
    }

    const ref: Record<string, PartRef> = {};

    function build() {
      fillsG.innerHTML = "";
      linesG.innerHTML = "";
      eyesG.innerHTML = "";

      PIG_PARTS.forEach((p) => {
        ref[p.id] = {
          fill: mk("path", {
            d: p.d,
            fill: PIG_FILL[p.col],
            class: "pig-fill" + (p.solid ? "" : " pig-riso"),
            style: `--fo:${p.fo ?? 0.3}`,
          }),
        };
      });
      PIG_FILL_ORDER.forEach((id) => fillsG.appendChild(ref[id].fill!));

      PIG_PARTS.forEach((p) => {
        const s = mk("path", {
          d: p.d,
          stroke: PIG_STROKE[p.col],
          class: "pig-stroke" + (p.big ? " pig-stroke-big" : "") + (p.thin ? " pig-stroke-thin" : ""),
          pathLength: "1",
        });
        linesG.appendChild(s);
        ref[p.id].stroke = s;
      });

      PIG_LINES.forEach((p) => {
        const s = mk("path", {
          d: p.d,
          stroke: PIG_STROKE[p.col],
          class: "pig-stroke" + (p.thin ? " pig-stroke-thin" : ""),
          pathLength: "1",
        });
        linesG.appendChild(s);
        ref[p.id] = { stroke: s };
      });

      PIG_EYES.forEach((e) => {
        const g = mk("g", { class: "pig-eye" });
        const c = mk("circle", {
          cx: String(e.cx),
          cy: String(e.cy),
          r: String(e.r),
          fill: PIG_FILL.ink,
          class: "pig-dot",
        });
        g.appendChild(c);
        eyesG.appendChild(g);
        ref[e.id] = { eyeG: g, dot: c, cfg: e };
      });
    }
    build();

    let timers: ReturnType<typeof setTimeout>[] = [];
    const at = (t: number, fn: () => void) => timers.push(setTimeout(fn, t));

    function resetVisualState() {
      timers.forEach(clearTimeout);
      timers = [];
      pig.classList.remove("pig-out", "pig-wiggle");
      nib.classList.remove("pig-nib-go");
      nib.style.opacity = "0";
      Object.values(ref).forEach((o) => {
        o.stroke?.classList.remove("pig-stroke-drawing");
        o.fill?.classList.remove("pig-fill-filled");
        o.dot?.classList.remove("pig-dot-in");
        o.eyeG?.classList.remove("pig-eye-blink");
      });
      void pig.getBoundingClientRect();
    }

    function drawShape(p: PigPart) {
      const o = ref[p.id];
      const dur = p.dur ?? 0.5;
      nibDot.setAttribute("fill", PIG_FILL[p.col]);
      nib.style.setProperty("offset-path", `path('${p.d}')`);
      nib.style.setProperty("--dur", `${dur}s`);
      nib.classList.remove("pig-nib-go");
      void nib.getBoundingClientRect();
      nib.classList.add("pig-nib-go");
      o.stroke!.style.setProperty("--dur", `${dur}s`);
      o.stroke!.classList.add("pig-stroke-drawing");
      at(dur * 1000, () => {
        o.fill?.classList.add("pig-fill-filled");
        nib.classList.remove("pig-nib-go");
        nib.style.opacity = "0";
      });
    }

    function dabEye(id: string) {
      const o = ref[id];
      const e = o.cfg!;
      nibDot.setAttribute("fill", PIG_FILL.ink);
      nib.style.setProperty("offset-path", `path('M ${e.cx} ${e.cy} l .1 0')`);
      nib.style.setProperty("--dur", ".2s");
      nib.classList.remove("pig-nib-go");
      void nib.getBoundingClientRect();
      nib.classList.add("pig-nib-go");
      o.dot!.classList.add("pig-dot-in");
      at(200, () => {
        nib.classList.remove("pig-nib-go");
        nib.style.opacity = "0";
      });
    }

    function run() {
      resetVisualState();

      if (reduce) {
        Object.values(ref).forEach((o) => {
          o.fill?.classList.add("pig-fill-filled");
          if (o.stroke) o.stroke.style.strokeDashoffset = "0";
          o.dot?.classList.add("pig-dot-in");
        });
        return;
      }

      const BEAT = 560;
      const START = 360;
      PIG_PARTS.forEach((p, i) => at(START + i * BEAT, () => drawShape(p)));

      const END = START + PIG_PARTS.length * BEAT;
      at(END + 120, () => dabEye("eye-l"));
      at(END + 360, () => dabEye("eye-r"));
      at(END + 640, () => drawShape(PIG_LINES[0]));
      at(END + 1080, () => drawShape(PIG_LINES[1]));

      at(END + 1600, () => {
        ref["eye-l"].eyeG!.classList.add("pig-eye-blink");
        ref["eye-r"].eyeG!.classList.add("pig-eye-blink");
      });
      at(END + 1940, () => {
        ref["eye-l"].eyeG!.classList.remove("pig-eye-blink");
        ref["eye-r"].eyeG!.classList.remove("pig-eye-blink");
      });
      at(END + 1840, () => pig.classList.add("pig-wiggle"));
      at(END + 2360, () => pig.classList.remove("pig-wiggle"));

      at(END + 2640, () => pig.classList.add("pig-out"));
      at(END + 3080, run);
    }

    run();

    return () => {
      timers.forEach(clearTimeout);
    };
  }, []);

  return (
    <div
      className="pig-loader-wrap"
      ref={rootRef}
      style={fullscreen ? { height: "100vh" } : undefined}
      role={label ? "status" : undefined}
      aria-live={label ? "polite" : undefined}
      aria-hidden={label ? undefined : true}
    >
      <div className="pig-loader-stage" style={{ width: size, height: size }}>
        <div className="pig-loader-bob">
          <svg className="pig-loader-scene" viewBox={PIG_VIEWBOX}>
            <g className="pig-fig">
              <g className="pig-fills"></g>
              <g className="pig-lines"></g>
              <g className="pig-eyes"></g>
            </g>
            <g className="pig-nib">
              <circle r="6.5" fill="#fff" />
              <circle className="pig-nib-dot" r="4.5" fill="#FF5A47" />
            </g>
          </svg>
        </div>
      </div>
      {label && <span className="pig-loader-status">{label}…</span>}

      <style jsx global>{`
        .pig-loader-wrap {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 12px;
        }
        .pig-loader-stage {
          width: 200px;
          height: 200px;
          flex: none;
        }
        .pig-loader-bob {
          width: 100%;
          height: 100%;
          animation: pig-bob 2.6s ease-in-out infinite;
        }
        @keyframes pig-bob {
          0%,
          100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-7px);
          }
        }
        .pig-loader-scene {
          width: 100%;
          height: 100%;
          overflow: visible;
        }

        .pig-fig {
          transform-box: fill-box;
          transform-origin: center;
          transition: opacity 0.4s ease, transform 0.4s ease;
        }
        .pig-fig.pig-out {
          opacity: 0;
          transform: scale(0.86);
        }
        .pig-fig.pig-wiggle {
          animation: pig-wiggle 0.5s ease;
        }
        @keyframes pig-wiggle {
          0%,
          100% {
            transform: rotate(0);
          }
          25% {
            transform: rotate(-3.5deg);
          }
          75% {
            transform: rotate(3.5deg);
          }
        }

        .pig-fill {
          fill-opacity: 0;
          transition: fill-opacity 0.34s ease;
        }
        .pig-fill.pig-fill-filled {
          fill-opacity: var(--fo, 0.3);
        }
        .pig-fill.pig-riso {
          mix-blend-mode: multiply;
        }

        .pig-stroke {
          fill: none;
          stroke-width: 4;
          stroke-linecap: round;
          stroke-linejoin: round;
          stroke-dasharray: 1;
          stroke-dashoffset: 1;
        }
        .pig-stroke.pig-stroke-big {
          stroke-width: 4.5;
        }
        .pig-stroke.pig-stroke-thin {
          stroke-width: 2.6;
        }
        .pig-stroke.pig-stroke-drawing {
          animation: pig-draw var(--dur, 0.5s) linear forwards;
        }
        @keyframes pig-draw {
          to {
            stroke-dashoffset: 0;
          }
        }

        .pig-eye {
          transform-box: fill-box;
          transform-origin: center;
        }
        .pig-eye.pig-eye-blink {
          animation: pig-blink 0.32s ease;
        }
        @keyframes pig-blink {
          0%,
          100% {
            transform: scaleY(1);
          }
          45%,
          55% {
            transform: scaleY(0.08);
          }
        }
        .pig-dot {
          transform-box: fill-box;
          transform-origin: center;
          opacity: 0;
          transform: scale(0);
        }
        .pig-dot.pig-dot-in {
          animation: pig-dab 0.28s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
        }
        @keyframes pig-dab {
          0% {
            opacity: 0;
            transform: scale(0);
          }
          60% {
            opacity: 1;
            transform: scale(1.25);
          }
          100% {
            opacity: 1;
            transform: scale(1);
          }
        }

        .pig-nib {
          opacity: 0;
        }
        .pig-nib.pig-nib-go {
          opacity: 1;
          animation: pig-nibmove var(--dur, 0.5s) linear forwards;
        }
        @keyframes pig-nibmove {
          from {
            offset-distance: 0%;
          }
          to {
            offset-distance: 100%;
          }
        }

        .pig-loader-status {
          font-family: var(--font-mono), ui-monospace, monospace;
          font-size: 13.5px;
          color: var(--ink-2);
          font-weight: 500;
        }

        @media (prefers-reduced-motion: reduce) {
          .pig-loader-bob {
            animation: none;
          }
          .pig-stroke {
            stroke-dashoffset: 0;
          }
          .pig-fill {
            fill-opacity: var(--fo, 0.3);
          }
          .pig-dot {
            opacity: 1;
            transform: none;
          }
        }
      `}</style>
    </div>
  );
}
