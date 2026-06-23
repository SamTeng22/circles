"use client";
import { useRouter } from "next/navigation";
import type { User } from "firebase/auth";
import { Circle } from "@/lib/api";
import { logout } from "@/lib/firebase";
import { BrandGlyphLight } from "@/components/BrandGlyph";
import { circleColor, initials } from "@/lib/circleStyle";

// Top-level nav. Only "Home" is wired today; the rest land on the dashboard
// until their pages exist (circle detail, quizzes, flashcards, live quiz).
const NAV = [
  { key: "home", label: "Home", icon: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z" },
  { key: "circles", label: "Circles", icon: "M9 9a5 5 0 1 0 .001 0M15 15a5 5 0 1 0 .001 0" },
  { key: "quizzes", label: "Quizzes", icon: "M9 9a3 3 0 1 1 4 2.8c-.8.4-1 1-1 2M12 17h.01" },
  { key: "flashcards", label: "Flashcards", icon: "M3 6h18v13H3zM3 10h18" },
  { key: "live", label: "Live quiz", icon: "M5 3l14 9-14 9z" },
] as const;

export function Sidebar({
  user,
  circles,
  activeCircleId,
}: {
  user: User | null;
  circles: Circle[];
  activeCircleId?: string;
}) {
  const router = useRouter();
  const displayName = user?.displayName || user?.email?.split("@")[0] || "You";

  return (
    <aside className="side">
      <div className="brand">
        <BrandGlyphLight />
        <span className="brand-name">
          Circ<b>l</b>es
        </span>
      </div>

      <nav className="nav">
        {NAV.map((item) => (
          <button
            key={item.key}
            className={`nav-item${item.key === "home" ? " active" : ""}`}
            onClick={() => router.push("/dashboard")}
          >
            <svg className="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d={item.icon} />
            </svg>
            {item.label}
          </button>
        ))}

        {circles.length > 0 && <div className="nav-label">Your circles</div>}
        {circles.map((c) => (
          <button
            key={c.id}
            className={`nav-item${c.id === activeCircleId ? " active" : ""}`}
            onClick={() => router.push(`/circles/${c.id}`)}
          >
            <span className="circ-dot" style={{ background: circleColor(c.id) }}>
              {initials(c.name)}
            </span>
            {c.name}
          </button>
        ))}
      </nav>

      <div className="side-spacer" />

      <div className="me">
        <div className="av">{displayName.charAt(0).toUpperCase()}</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {displayName}
          </div>
          <small>
            {circles.length} circle{circles.length === 1 ? "" : "s"}
          </small>
        </div>
        <button className="signout" onClick={() => logout()} title="Sign out" aria-label="Sign out">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
