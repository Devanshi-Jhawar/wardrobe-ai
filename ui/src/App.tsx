import { useEffect, useState } from "react";
import { api } from "./api";
import { IconGrid, IconHanger, IconSliders, IconSpark } from "./icons";
import { Preferences } from "./pages/Preferences";
import { Stylist } from "./pages/Stylist";
import { Wardrobe } from "./pages/Wardrobe";
import type { Health } from "./types";
import { store } from "./util";

type Page = "stylist" | "wardrobe" | "preferences";
const PAGES: { id: Page; label: string; icon: JSX.Element }[] = [
  { id: "stylist", label: "Stylist", icon: <IconSpark /> },
  { id: "wardrobe", label: "Wardrobe", icon: <IconGrid /> },
  { id: "preferences", label: "Preferences", icon: <IconSliders /> },
];
const SERVICE_NAMES: Record<string, string> = {
  wardrobe: "Wardrobe", vision: "Vision", embedding: "Embedding", weather: "Weather", memory: "Memory",
};

const pageFromHash = (): Page => {
  const h = window.location.hash.replace("#/", "") as Page;
  return PAGES.some((p) => p.id === h) ? h : "stylist";
};

function Nav({ page }: { page: Page }) {
  return (
    <nav className="nav" aria-label="Main">
      {PAGES.map((p) => (
        <button key={p.id} aria-current={page === p.id ? "page" : undefined}
          onClick={() => { window.location.hash = `#/${p.id}`; }}>
          {p.icon}<span>{p.label}</span>
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [userId, setUserId] = useState<string>(() => store.get("wardrobe-ai.user", "u1"));
  const [userDraft, setUserDraft] = useState(userId);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const check = () => api.health().then((h) => { setHealth(h); setHealthError(false); }).catch(() => setHealthError(true));
    check();
    const t = window.setInterval(check, 30000);
    return () => window.clearInterval(t);
  }, []);

  const commitUser = () => {
    const u = userDraft.trim() || "u1";
    setUserDraft(u);
    if (u !== userId) { setUserId(u); store.set("wardrobe-ai.user", u); }
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><IconHanger size={18} /></div>
          <div>
            <div className="brand-name">Wardrobe</div>
            <div className="brand-sub">Personal stylist</div>
          </div>
        </div>

        <div>
          <div className="nav-label">Menu</div>
          <Nav page={page} />
        </div>

        <div className="sidebar-foot">
          <div className="profile">
            <label htmlFor="profile">Profile</label>
            <input id="profile" value={userDraft} onChange={(e) => setUserDraft(e.target.value)} onBlur={commitUser}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} spellCheck={false} />
          </div>
          <div className="status" aria-label="Service status">
            {healthError ? (
              <div className="status-row"><span><span className="dot off" />Agent offline</span></div>
            ) : health ? (
              <>
                <div className="status-row">
                  <span><span className={`dot ${health.llm.enabled ? "on" : ""}`} />Planner</span>
                  <span>{health.llm.enabled ? (health.llm.provider === "xai" ? "Grok" : "Groq") : "Rules"}</span>
                </div>
                {Object.entries(health.services).map(([k, up]) => (
                  <div className="status-row" key={k}>
                    <span><span className={`dot ${up ? "on" : "off"}`} />{SERVICE_NAMES[k] ?? k}</span>
                    <span>{up ? "Online" : "Offline"}</span>
                  </div>
                ))}
              </>
            ) : (
              <div className="status-row"><span><span className="dot" />Connecting</span></div>
            )}
          </div>
        </div>
      </aside>

      <header className="topbar">
        <div className="brand-mark"><IconHanger size={16} /></div>
        <div className="brand-name" style={{ fontSize: 20 }}>Wardrobe</div>
        <Nav page={page} />
      </header>

      <main className="main" key={userId}>
        {page === "stylist" && <Stylist userId={userId} />}
        {page === "wardrobe" && <Wardrobe userId={userId} />}
        {page === "preferences" && <Preferences userId={userId} />}
      </main>
    </div>
  );
}
