// Decorative "consensus lens" cluster used on circle cards — purely visual.
const BLOBS = [
  { c: "#FF5A47", x: 38, y: 34, r: 120 },
  { c: "#3F3AE6", x: 62, y: 36, r: 122 },
  { c: "#0CB78D", x: 50, y: 60, r: 118 },
  { c: "#F5A524", x: 36, y: 58, r: 108 },
  { c: "#7C5CFF", x: 64, y: 58, r: 108 },
];

export function MiniViz({ scale = 0.42 }: { scale?: number }) {
  return (
    <div className="miniviz">
      {BLOBS.map((b, i) => {
        const r = b.r * scale;
        return (
          <div
            key={i}
            className="blob"
            style={{ width: r, height: r, background: b.c, left: `${b.x}%`, top: `${b.y}%` }}
          />
        );
      })}
    </div>
  );
}
