import { useState } from "react";
import { api } from "../api";
import { IconImage } from "../icons";
import type { OutfitItem } from "../types";
import { asList, describe } from "../util";

export function ItemImage({ userId, id, thumb = true, alt }: {
  userId: string; id: string | null; thumb?: boolean; alt: string;
}) {
  const [broken, setBroken] = useState(false);
  if (!id || broken) return <IconImage size={26} />;
  return <img src={api.imageUrl(userId, id, thumb)} alt={alt} loading="lazy" onError={() => setBroken(true)} />;
}

export function Look({ userId, item, compact = false }: { userId: string; item: OutfitItem; compact?: boolean }) {
  const label = describe(item);
  return (
    <div className="look" title={label}>
      <div className="look-img"><ItemImage userId={userId} id={item.id} alt={label} /></div>
      <div className="look-cap">
        <b>{item.category ?? "Item"}</b>
        {!compact && <span>{asList(item.color).slice(0, 2).join(", ") || item.style || " "}</span>}
      </div>
    </div>
  );
}
