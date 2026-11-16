import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { ItemDrawer } from "../components/ItemDrawer";
import { ItemImage } from "../components/Look";
import { UploadDialog } from "../components/UploadDialog";
import { IconStar, IconUpload } from "../icons";
import type { Item } from "../types";
import { SLOT_LABELS, asList, colorHex } from "../util";

const ORDER = ["top", "bottom", "onepiece", "footwear", "outerwear", "accessory"];

export function Wardrobe({ userId }: { userId: string }) {
  const [items, setItems] = useState<Item[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [selected, setSelected] = useState<Item | null>(null);
  const [uploading, setUploading] = useState(false);

  const load = useCallback(() => {
    setError(null);
    api.wardrobe(userId).then((r) => setItems(r.items)).catch((e: Error) => { setError(e.message); setItems([]); });
  }, [userId]);
  useEffect(() => { setItems(null); load(); }, [load]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const it of items ?? []) {
      const k = it.slot ?? "untagged";
      c[k] = (c[k] ?? 0) + 1;
    }
    return c;
  }, [items]);

  const shown = (items ?? []).filter((it) => {
    if (filter === "all") return true;
    if (filter === "favorites") return it.is_favorite;
    if (filter === "untagged") return !it.slot;
    return it.slot === filter;
  });

  // The upload reply has no slot, so reload to keep the grouping right.
  const onUploaded = useCallback(() => load(), [load]);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Your closet</div>
          <h1>Wardrobe</h1>
          <p className="lede">
            {items ? `${items.length} piece${items.length === 1 ? "" : "s"}.` : "Loading."} Photos are tagged
            automatically; open any piece to correct its details.
          </p>
        </div>
        <button className="btn primary" onClick={() => setUploading(true)}><IconUpload size={16} /> Add clothes</button>
      </div>

      {items && items.length > 0 && (
        <div className="toolbar">
          <div className="chips">
            <button className="chip" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All {items.length}</button>
            {ORDER.filter((s) => counts[s]).map((s) => (
              <button key={s} className="chip" aria-pressed={filter === s} onClick={() => setFilter(s)}>
                {SLOT_LABELS[s]} {counts[s]}
              </button>
            ))}
            {items.some((i) => i.is_favorite) && (
              <button className="chip" aria-pressed={filter === "favorites"} onClick={() => setFilter("favorites")}>Favourites</button>
            )}
            {counts.untagged ? (
              <button className="chip" aria-pressed={filter === "untagged"} onClick={() => setFilter("untagged")}>Needs details {counts.untagged}</button>
            ) : null}
          </div>
        </div>
      )}

      {error && <div className="notice error" style={{ marginBottom: 16 }}>{error}</div>}

      {items === null ? (
        <div className="row muted"><span className="spinner" /> Loading your wardrobe</div>
      ) : items.length === 0 ? (
        <div className="empty">
          <h2>Your wardrobe is empty</h2>
          <p className="muted">Add photos of your clothes and they'll be recognised and tagged for you.</p>
          <button className="btn primary" style={{ marginTop: 12 }} onClick={() => setUploading(true)}><IconUpload size={16} /> Add clothes</button>
        </div>
      ) : (
        <div className="grid">
          {shown.map((it) => (
            <button key={it.id} className="tile" onClick={() => setSelected(it)}>
              <div className="look-img">
                <ItemImage userId={userId} id={it.id} alt={it.category ?? "Item"} />
                <div className="tile-badges">
                  {it.status !== "ready" ? <span className={`tag ${it.status === "failed" ? "danger" : "warn"}`}>{it.status === "failed" ? "Tagging failed" : "Pending"}</span> : <span />}
                  {it.is_favorite && <span className="fav"><IconStar size={16} filled /></span>}
                </div>
              </div>
              <div className="tile-body">
                <div className="tile-title">{it.category ?? "Untagged"}</div>
                <div className="tile-sub">
                  {asList(it.color).slice(0, 3).map((c) => <span key={c} className="swatch" style={{ background: colorHex(c) }} title={c} />)}
                  <span>{asList(it.color).slice(0, 2).join(", ") || it.style || ""}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <ItemDrawer
          userId={userId}
          item={selected}
          onClose={() => setSelected(null)}
          onSaved={(saved) => { setSelected(null); setItems((xs) => (xs ?? []).map((x) => (x.id === saved.id ? { ...saved, slot: x.slot } : x))); load(); }}
          onDeleted={(id) => { setSelected(null); setItems((xs) => (xs ?? []).filter((x) => x.id !== id)); }}
        />
      )}
      {uploading && <UploadDialog userId={userId} onClose={() => setUploading(false)} onUploaded={onUploaded} />}
    </div>
  );
}
