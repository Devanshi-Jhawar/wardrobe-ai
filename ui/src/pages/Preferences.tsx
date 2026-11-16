import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { ItemImage } from "../components/Look";
import { IconClose, IconPlus } from "../icons";
import type { Memory, WornEntry } from "../types";
import { capitalize, formatDate } from "../util";

function WordList({ title, hint, words, onChange, busy }: {
  title: string; hint: string; words: string[]; onChange: (w: string[]) => void; busy: boolean;
}) {
  const [text, setText] = useState("");
  const add = () => {
    const w = text.trim().toLowerCase();
    if (w && !words.includes(w)) onChange([...words, w]);
    setText("");
  };
  return (
    <div className="card panel">
      <h3>{title}</h3>
      {words.length ? (
        <div className="chips">
          {words.map((w) => (
            <span key={w} className="chip static">
              {w}
              <button className="x" onClick={() => onChange(words.filter((x) => x !== w))} aria-label={`Remove ${w}`} disabled={busy}>
                <IconClose size={12} />
              </button>
            </span>
          ))}
        </div>
      ) : (
        <p className="small muted" style={{ margin: 0 }}>{hint}</p>
      )}
      <form className="add-row" onSubmit={(e) => { e.preventDefault(); add(); }}>
        <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Colour, garment or style" aria-label={`Add to ${title}`} />
        <button className="btn icon" type="submit" disabled={!text.trim() || busy} aria-label="Add"><IconPlus size={16} /></button>
      </form>
    </div>
  );
}

export function Preferences({ userId }: { userId: string }) {
  const [memory, setMemory] = useState<Memory | null>(null);
  const [history, setHistory] = useState<WornEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [days, setDays] = useState("3");
  const [saved, setSaved] = useState(false);
  const [city, setCity] = useState("");

  useEffect(() => {
    if (!saved) return;
    const t = setTimeout(() => setSaved(false), 2500);
    return () => clearTimeout(t);
  }, [saved]);

  const load = useCallback(() => {
    setError(null);
    Promise.all([api.memory(userId), api.history(userId)])
      .then(([m, h]) => { setMemory(m); setHistory(h.outfits); setDays(String(m.preferences.avoid_repeat_days)); setCity(m.preferences.home_city ?? ""); })
      .catch((e: Error) => setError(e.message));
  }, [userId]);
  useEffect(() => { setMemory(null); load(); }, [load]);

  const save = async (patch: { likes?: string[]; dislikes?: string[]; avoid_repeat_days?: number; home_city?: string }) => {
    if (!memory) return;
    setBusy(true); setError(null); setSaved(false);
    try {
      // A word can't be both liked and disliked: the newest list wins.
      if (patch.likes) patch.dislikes = memory.preferences.dislikes.filter((d) => !patch.likes!.includes(d));
      if (patch.dislikes) patch.likes = (patch.likes ?? memory.preferences.likes).filter((l) => !patch.dislikes!.includes(l));
      const prefs = await api.setPreferences(userId, patch);
      setMemory({ ...memory, preferences: prefs });
      setDays(String(prefs.avoid_repeat_days));
      setCity(prefs.home_city ?? "");
      setSaved(true);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const undo = async (id: string) => {
    try { await api.deleteWorn(userId, id); setHistory((h) => h.filter((x) => x.id !== id)); }
    catch (e) { setError((e as Error).message); }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Memory</div>
          <h1>Preferences</h1>
          <p className="lede">
            What I remember about your taste. You can also tell me in conversation, for example
            "I don't like frocks" or "I love pastels".
          </p>
        </div>
      </div>

      {error && <div className="notice error" style={{ marginBottom: 16 }}>{error}</div>}
      {saved && <div className="notice" role="status" style={{ marginBottom: 16 }}>Saved</div>}

      {!memory ? (
        !error && <div className="row muted"><span className="spinner" /> Loading</div>
      ) : (
        <div className="stack" style={{ gap: 16 }}>
          <div className="cols">
            <WordList title="Likes" hint="Nothing yet. Liked things are picked first when they fit."
              words={memory.preferences.likes} busy={busy} onChange={(likes) => save({ likes })} />
            <WordList title="Avoid" hint="Nothing yet. Anything here is never suggested."
              words={memory.preferences.dislikes} busy={busy} onChange={(dislikes) => save({ dislikes })} />
          </div>

          <div className="card panel">
            <h3>Home city</h3>
            <form className="row" style={{ flexWrap: "wrap" }}
              onSubmit={(e) => { e.preventDefault(); save({ home_city: city.trim() }); }}>
              <input className="input" style={{ width: 240 }} value={city} onChange={(e) => setCity(e.target.value)}
                placeholder="e.g. Mumbai" aria-label="Home city" maxLength={120} />
              <button className="btn sm" type="submit" disabled={busy}>Save</button>
              {memory.preferences.home_city && (
                <button className="btn ghost sm" type="button" disabled={busy}
                  onClick={() => save({ home_city: "" })}>Clear</button>
              )}
            </form>
            <p className="small muted" style={{ margin: "12px 0 0" }}>
              Used for the weather when your question doesn't name a place. Without it, outfits ignore the weather.
            </p>
          </div>

          <div className="card panel">
            <h3>Repeats</h3>
            <form className="row" style={{ flexWrap: "wrap" }}
              onSubmit={(e) => { e.preventDefault(); const n = Number(days); if (days !== "" && Number.isInteger(n) && n >= 0 && n <= 60) save({ avoid_repeat_days: n }); else setError("Enter a whole number of days from 0 to 60."); }}>
              <span className="muted">Don't suggest something I've worn within</span>
              <input className="input" style={{ width: 72 }} type="number" min={0} max={60} value={days} onChange={(e) => setDays(e.target.value)} aria-label="Days" />
              <span className="muted">days</span>
              <button className="btn sm" type="submit" disabled={busy}>{busy ? <span className="spinner" /> : null} Save</button>
            </form>
            <p className="small muted" style={{ margin: "12px 0 0" }}>
              {memory.liked_item_ids.length} piece{memory.liked_item_ids.length === 1 ? "" : "s"} rated up,{" "}
              {memory.disliked_item_ids.length} rated down from outfit feedback.
            </p>
          </div>

          <div className="card panel">
            <h3>Wear history</h3>
            {history.length === 0 ? (
              <p className="small muted" style={{ margin: 0 }}>
                Nothing logged yet. Choose "I'm wearing this" on a suggested outfit to record it.
              </p>
            ) : (
              <div className="history">
                {history.map((h) => (
                  <div key={h.id} className="history-row">
                    <div>
                      <div style={{ fontWeight: 500 }}>{formatDate(h.worn_on)}</div>
                      <div className="small muted">{[capitalize(h.occasion), h.city].filter(Boolean).join(", ") || "Everyday"}</div>
                    </div>
                    <div className="thumbs">
                      {h.item_ids.slice(0, 8).map((id) => (
                        <ItemImage key={id} userId={userId} id={id} alt="" />
                      ))}
                    </div>
                    <button className="btn ghost sm" onClick={() => undo(h.id)}>Remove</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
