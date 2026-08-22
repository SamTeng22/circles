"use client";
import { useEffect, useState } from "react";

const SOUND_FILES = {
  correct: "/sounds/correct.wav",
  wrong: "/sounds/wrong.wav",
  flip: "/sounds/flip.wav",
  complete: "/sounds/complete.wav",
} as const;

export type SoundName = keyof typeof SOUND_FILES;

const STORAGE_KEY = "soundEnabled";
const cache: Partial<Record<SoundName, HTMLAudioElement>> = {};

function isSoundEnabled(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(STORAGE_KEY) !== "false";
}

function setSoundEnabled(enabled: boolean) {
  localStorage.setItem(STORAGE_KEY, String(enabled));
}

export function playSound(name: SoundName) {
  if (typeof window === "undefined" || !isSoundEnabled()) return;
  let audio = cache[name];
  if (!audio) {
    audio = new Audio(SOUND_FILES[name]);
    cache[name] = audio;
  } else {
    audio.currentTime = 0;
  }
  // Autoplay can be blocked before any user gesture; that's fine, ignore it.
  audio.play().catch(() => {});
}

export function useSoundPref(): [boolean, () => void] {
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    setEnabled(isSoundEnabled());
  }, []);

  function toggle() {
    setEnabled((prev) => {
      const next = !prev;
      setSoundEnabled(next);
      return next;
    });
  }

  return [enabled, toggle];
}
