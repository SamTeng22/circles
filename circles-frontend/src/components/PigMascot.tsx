import {
  PIG_EYES,
  PIG_FILL,
  PIG_FILL_ORDER,
  PIG_LINES,
  PIG_PARTS,
  PIG_STROKE,
  PIG_VIEWBOX,
} from "./pigArt";

const byId = Object.fromEntries(PIG_PARTS.map((p) => [p.id, p]));

/** Fully-drawn, static pig mascot — the finished frame of the loader's drawing. */
export function PigMascot({
  size = 56,
  bob = true,
  className,
}: {
  size?: number;
  bob?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`pig-mascot${bob ? " pig-mascot-bobbing" : ""}${className ? ` ${className}` : ""}`}
      style={{ width: size, height: size }}
    >
      <svg viewBox={PIG_VIEWBOX} width={size} height={size} style={{ overflow: "visible" }}>
        <g>
          {PIG_FILL_ORDER.map((id) => {
            const p = byId[id];
            return (
              <path
                key={p.id}
                d={p.d}
                fill={PIG_FILL[p.col]}
                fillOpacity={p.fo ?? 0.3}
                style={p.solid ? undefined : { mixBlendMode: "multiply" }}
              />
            );
          })}
          {PIG_PARTS.map((p) => (
            <path
              key={p.id}
              d={p.d}
              fill="none"
              stroke={PIG_STROKE[p.col]}
              strokeWidth={p.thin ? 2.6 : p.big ? 4.5 : 4}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}
          {PIG_LINES.map((p) => (
            <path
              key={p.id}
              d={p.d}
              fill="none"
              stroke={PIG_STROKE[p.col]}
              strokeWidth={p.thin ? 2.6 : 4}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}
          {PIG_EYES.map((e) => (
            <circle key={e.id} cx={e.cx} cy={e.cy} r={e.r} fill={PIG_FILL.ink} />
          ))}
        </g>
      </svg>
      <style jsx>{`
        .pig-mascot {
          display: inline-flex;
        }
        .pig-mascot-bobbing {
          animation: pig-mascot-bob 2.6s ease-in-out infinite;
        }
        @keyframes pig-mascot-bob {
          0%,
          100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-3px);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .pig-mascot-bobbing {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
}
