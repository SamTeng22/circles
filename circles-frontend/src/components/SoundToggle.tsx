"use client";
import { useSoundPref } from "@/lib/sound";

export function SoundToggle({ className }: { className?: string }) {
  const [enabled, toggle] = useSoundPref();
  return (
    <button
      type="button"
      className={`btn btn-ghost btn-sm ${className ?? ""}`}
      onClick={toggle}
      title={enabled ? "Mute sound effects" : "Unmute sound effects"}
      aria-label={enabled ? "Mute sound effects" : "Unmute sound effects"}
    >
      {enabled ? "🔊" : "🔇"}
    </button>
  );
}
