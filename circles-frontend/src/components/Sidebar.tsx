"use client";
import { usePathname, useRouter } from "next/navigation";
import type { User } from "firebase/auth";
import { Circle } from "@/lib/api";
import { logout } from "@/lib/firebase";
import { BrandGlyphLight } from "@/components/BrandGlyph";
import { PigBounce } from "@/components/PigBounce";
import { circleColor, initials } from "@/lib/circleStyle";

export type SidebarCircleTab = "quizzes" | "flashcards" | "live";

// Circle-scoped nav — only meaningful once a circle is selected, so these
// are hidden until then and route into that circle's matching tab.
const CIRCLE_NAV = [
  { key: "quizzes", label: "Quizzes", icon: "M9 9a3 3 0 1 1 4 2.8c-.8.4-1 1-1 2M12 17h.01", tab: "quizzes" },
  { key: "flashcards", label: "Flashcards", icon: "M3 6h18v13H3zM3 10h18", tab: "flashcards" },
  { key: "live", label: "Live quiz", icon: "M5 3l14 9-14 9z", tab: "quizzes" },
] as const;

export function Sidebar({
  user,
  circles,
  activeCircleId,
  activeTab,
}: {
  user: User | null;
  circles: Circle[];
  activeCircleId?: string;
  activeTab?: SidebarCircleTab;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const displayName = user?.displayName || user?.email?.split("@")[0] || "You";
  const homeActive = pathname === "/dashboard";

  return (
    <aside className="side">
      <div className="brand">
        <BrandGlyphLight />
        <span className="brand-name">
          Circ<b>l</b>es
        </span>
      </div>

      <nav className="nav">
        <button className={`nav-item${homeActive ? " active" : ""}`} onClick={() => router.push("/dashboard")}>
          <svg className="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z" />
          </svg>
          Home
        </button>

        {activeCircleId &&
          CIRCLE_NAV.map((item) => (
            <button
              key={item.key}
              className={`nav-item${activeTab === item.key ? " active" : ""}`}
              onClick={() => router.push(`/circles/${activeCircleId}?tab=${item.tab}`)}
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

      <div className="side-spacer">
        <PigBounce pigSize={36} />
      </div>

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
