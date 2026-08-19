import { PigMascot } from "./PigMascot";

/** Inline "processing" chip where the pig hops back and forth across the dots. */
export function PigProcessing({ label = "processing" }: { label?: string }) {
  return (
    <span className="chip chip-cobalt pigp-chip">
      {label}
      <span className="pigp-stage">
        <span className="pigp-dot" />
        <span className="pigp-dot" />
        <span className="pigp-dot" />
        <span className="pigp-pig">
          <PigMascot size={14} bob={false} />
        </span>
      </span>
      <style jsx>{`
        .pigp-chip {
          gap: 8px;
        }
        .pigp-stage {
          position: relative;
          width: 28px;
          height: 14px;
          flex: none;
        }
        .pigp-dot {
          position: absolute;
          bottom: 0;
          width: 4px;
          height: 4px;
          border-radius: 50%;
          background: currentColor;
          opacity: 0.35;
          animation: pigp-pulse 1.8s ease-in-out infinite;
        }
        .pigp-dot:nth-child(1) {
          left: 0;
          animation-delay: 0s;
        }
        .pigp-dot:nth-child(2) {
          left: 12px;
          animation-delay: 0.6s;
        }
        .pigp-dot:nth-child(3) {
          left: 24px;
          animation-delay: 1.2s;
        }
        @keyframes pigp-pulse {
          0%,
          100% {
            opacity: 0.35;
            transform: scale(1);
          }
          50% {
            opacity: 1;
            transform: scale(1.3);
          }
        }
        .pigp-pig {
          position: absolute;
          bottom: 1px;
          left: -3px;
          width: 14px;
          height: 14px;
          animation: pigp-hop 1.8s ease-in-out infinite;
        }
        @keyframes pigp-hop {
          0% {
            transform: translate(0px, 0);
          }
          12.5% {
            transform: translate(6px, -8px);
          }
          25% {
            transform: translate(12px, 0);
          }
          37.5% {
            transform: translate(18px, -8px);
          }
          50% {
            transform: translate(24px, 0);
          }
          62.5% {
            transform: translate(18px, -8px);
          }
          75% {
            transform: translate(12px, 0);
          }
          87.5% {
            transform: translate(6px, -8px);
          }
          100% {
            transform: translate(0px, 0);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .pigp-dot,
          .pigp-pig {
            animation: none;
          }
        }
      `}</style>
    </span>
  );
}
