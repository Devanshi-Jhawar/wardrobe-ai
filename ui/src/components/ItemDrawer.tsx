import { useEffect, useState } from "react";
import { api } from "../api";
import { IconClose, IconRefresh, IconStar, IconTrash } from "../icons";
import type { Item } from "../types";
import { CATEGORIES, OCCASIONS, SEASONS, capitalize, formatDate } from "../util";
import { ItemImage } from "./Look";

type Draft = {
  category: string; color: string; pattern: string; material: string; style: string;
  occasion: string[]; season: string[]; is_favorite: boolean;
};

const toDraft = (it: Item): Draft => ({
  category: it.category ?? "", color: (it.color ?? []).join(", "), pattern: it.pattern ?? "",
  material: it.material ?? "", style: it.style ?? "", occasion: it.occasion ?? [],
  season: it.season ?? [], is_favorite: it.is_favorite,
});

function Toggles({ options, value, onChange }: { options: string[]; value: string[]; onChange: (v: string[]) => void }) {
  const all = Array.from(new Set([...options, ...value]));
  return (
    <div className="chips">
      {all.map((o) => (
        <button key={o} type="button" className="chip" aria-pressed={value.includes(o)}
          onClick={() => onChange(value.includes(o) ? value.filter((x) => x !== o) : [...value, o])}>
          {capitalize(o)}
        </button>
      ))}
    </div>
  );
}

export function ItemDrawer({ userId, item, onClose, onSaved, onDeleted }: {
  userId: string; item: Item; onClose: () => void;
  onSaved: (item: Item) => void; onDeleted: (id: string) => void;
}) {
  const [draft, setDraft] = useState<Draft>(toDraft(item));
  const [busy, setBusy] = useState<null | "save" | "delete" | "enrich">(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setDraft(toDraft(item)); setConfirmDelete(false); setError(null); }, [item]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));

  const save = async () => {
    setBusy("save"); setError(null);
    try {
      const saved = await api.updateItem(userId, item.id, {
        category: draft.category || null,
        color: draft.color.split(",").map((c) => c.trim().toLowerCase()).filter(Boolean),
        pattern: draft.pattern || null, material: draft.material || null, style: draft.style || null,
        occasion: draft.occasion, season: draft.season, is_favorite: draft.is_favorite,
      });
      onSaved(saved);
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  const remove = async () => {
    setBusy("delete"); setError(null);
    try { await api.deleteItem(userId, item.id); onDeleted(item.id); }
    catch (e) { setError((e as Error).message); setBusy(null); }
  };

  const reanalyse = async () => {
    setBusy("enrich"); setError(null);
    try { onSaved(await api.enrichItem(userId, item.id)); }
    catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  const conf = item.attributes?.confidence as number | undefined;

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Item details">
        <div className="drawer-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 4 }}>Item</div>
            <h2>{draft.category || "Untagged item"}</h2>
          </div>
          <div className="row">
            <button className={`btn icon ${draft.is_favorite ? "active" : ""}`} onClick={() => set("is_favorite", !draft.is_favorite)}
              aria-label={draft.is_favorite ? "Remove from favourites" : "Mark as favourite"} aria-pressed={draft.is_favorite}>
              <IconStar filled={draft.is_favorite} />
            </button>
            <button className="btn ghost icon" onClick={onClose} aria-label="Close"><IconClose /></button>
          </div>
        </div>

        <div className="drawer-body">
          <div className="drawer-img"><ItemImage userId={userId} id={item.id} thumb={false} alt={draft.category || "Item"} /></div>

          <div className="row" style={{ flexWrap: "wrap" }}>
            <span className={`tag ${item.status === "ready" ? "" : item.status === "failed" ? "danger" : "warn"}`}>{capitalize(item.status)}</span>
            {typeof conf === "number" && <span className="tag">Detected at {Math.round(conf * 100)}%</span>}
            {item.attributes?.low_confidence ? <span className="tag warn">Check the category</span> : null}
            <span className="small muted">Worn {item.wear_count} time{item.wear_count === 1 ? "" : "s"}
              {item.last_worn_at ? `, last on ${formatDate(item.last_worn_at)}` : ""}</span>
            <span className="spacer" />
            {item.status !== "ready" && (
              <button className="btn sm" onClick={reanalyse} disabled={!!busy}>
                {busy === "enrich" ? <span className="spinner" /> : <IconRefresh size={14} />} Re-analyse
              </button>
            )}
          </div>

          <div className="form-grid">
            <label className="field">
              <span>Category</span>
              <select className="select" value={draft.category} onChange={(e) => set("category", e.target.value)}>
                <option value="">Not set</option>
                {Array.from(new Set([...CATEGORIES, ...(draft.category ? [draft.category] : [])])).map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Colours</span>
              <input className="input" value={draft.color} onChange={(e) => set("color", e.target.value)} placeholder="navy, white" />
            </label>
            <label className="field">
              <span>Style</span>
              <input className="input" value={draft.style} onChange={(e) => set("style", e.target.value)} placeholder="casual, ethnic, formal" />
            </label>
            <label className="field">
              <span>Pattern</span>
              <input className="input" value={draft.pattern} onChange={(e) => set("pattern", e.target.value)} placeholder="solid, striped" />
            </label>
            <label className="field" style={{ gridColumn: "1 / -1" }}>
              <span>Material</span>
              <input className="input" value={draft.material} onChange={(e) => set("material", e.target.value)} placeholder="cotton, linen, silk" />
            </label>
          </div>

          <div className="field"><span>Occasions</span>
            <Toggles options={OCCASIONS} value={draft.occasion} onChange={(v) => set("occasion", v)} />
          </div>
          <div className="field"><span>Seasons</span>
            <Toggles options={SEASONS} value={draft.season} onChange={(v) => set("season", v)} />
          </div>

          {error && <div className="notice error">{error}</div>}
        </div>

        <div className="drawer-foot">
          {confirmDelete ? (
            <>
              <span className="small muted" style={{ alignSelf: "center" }}>Remove this item?</span>
              <span className="spacer" />
              <button className="btn ghost" onClick={() => setConfirmDelete(false)} disabled={!!busy}>Keep</button>
              <button className="btn danger" onClick={remove} disabled={!!busy}>
                {busy === "delete" ? <span className="spinner" /> : <IconTrash size={15} />} Remove
              </button>
            </>
          ) : (
            <>
              <button className="btn danger" onClick={() => setConfirmDelete(true)} disabled={!!busy}><IconTrash size={15} /> Remove</button>
              <span className="spacer" />
              <button className="btn ghost" onClick={onClose}>Cancel</button>
              <button className="btn primary" onClick={save} disabled={!!busy}>
                {busy === "save" ? <span className="spinner" /> : null} Save changes
              </button>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
