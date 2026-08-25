"use client";
import { useEffect, useRef } from "react";
import { PigMascot } from "./PigMascot";

/** The sidebar pig, let loose — bounces around its container like a DVD logo. */
export function PigBounce({
  pigSize = 36,
  speed = 55,
  className,
}: {
  pigSize?: number;
  speed?: number;
  className?: string;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const figRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const box = boxRef.current;
    const fig = figRef.current;
    if (!box || !fig) return;

    const center = () => {
      const w = box.clientWidth;
      const h = box.clientHeight;
      fig.style.transform = `translate(${Math.max((w - pigSize) / 2, 0)}px, ${Math.max((h - pigSize) / 2, 0)}px)`;
    };

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      center();
      return;
    }

    let width = box.clientWidth;
    let height = box.clientHeight;
    if (width < pigSize + 8 || height < pigSize + 8) {
      center();
      return;
    }

    let x = Math.random() * (width - pigSize);
    let y = Math.random() * (height - pigSize);
    let vx = (Math.random() < 0.5 ? -1 : 1) * speed;
    let vy = (Math.random() < 0.5 ? -1 : 1) * speed;
    let facing = vx >= 0 ? 1 : -1;
    let last = performance.now();
    let raf = 0;

    const onResize = () => {
      width = box.clientWidth;
      height = box.clientHeight;
      x = Math.min(x, Math.max(width - pigSize, 0));
      y = Math.min(y, Math.max(height - pigSize, 0));
    };
    window.addEventListener("resize", onResize);

    function tick(now: number) {
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;

      x += vx * dt;
      y += vy * dt;

      const maxX = Math.max(width - pigSize, 0);
      const maxY = Math.max(height - pigSize, 0);

      if (x <= 0) {
        x = 0;
        vx = Math.abs(vx);
        facing = 1;
      } else if (x >= maxX) {
        x = maxX;
        vx = -Math.abs(vx);
        facing = -1;
      }

      if (y <= 0) {
        y = 0;
        vy = Math.abs(vy);
      } else if (y >= maxY) {
        y = maxY;
        vy = -Math.abs(vy);
      }

      fig.style.transform = `translate(${x}px, ${y}px) scaleX(${facing})`;
      raf = requestAnimationFrame(tick);
    }

    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, [pigSize, speed]);

  return (
    <div ref={boxRef} className={`pig-bounce-box${className ? ` ${className}` : ""}`}>
      <div ref={figRef} className="pig-bounce-fig">
        <PigMascot size={pigSize} />
      </div>
      <style jsx>{`
        .pig-bounce-box {
          position: relative;
          overflow: hidden;
          width: 100%;
          height: 100%;
        }
        .pig-bounce-fig {
          position: absolute;
          top: 0;
          left: 0;
          will-change: transform;
        }
      `}</style>
    </div>
  );
}
