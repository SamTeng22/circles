import { PIG_FILL, PIG_STROKE } from "./pigArt";
import { ANIMALS, type AnimalName } from "./animalArt";

/** Fully-drawn, static mascot for any of the animals in `animalArt`. */
export function AnimalMascot({
  animal,
  size = 56,
  bob = true,
  className,
}: {
  animal: AnimalName;
  size?: number;
  bob?: boolean;
  className?: string;
}) {
  const spec = ANIMALS[animal];
  const byId = Object.fromEntries(spec.parts.map((p) => [p.id, p]));

  return (
    <div
      className={`pig-mascot${bob ? " pig-mascot-bobbing" : ""}${className ? ` ${className}` : ""}`}
      style={{ width: size, height: size }}
    >
      <svg viewBox={spec.viewBox} width={size} height={size} style={{ overflow: "visible" }}>
        <g>
          {spec.fillOrder.map((id) => {
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
          {spec.parts.map((p) => (
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
          {spec.lines.map((p) => (
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
          {spec.eyes.map((e) => (
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
