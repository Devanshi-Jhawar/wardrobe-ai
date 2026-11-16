import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { IconCheck, IconClose, IconUpload } from "../icons";
import type { Item } from "../types";
import { asList } from "../util";

type Row = { file: File; preview: string; state: "waiting" | "uploading" | "done" | "error"; item?: Item; error?: string };

export function UploadDialog({ userId, onClose, onUploaded }: {
  userId: string; onClose: () => void; onUploaded: (item: Item) => void;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const running = useRef(false);

  useEffect(() => () => rows.forEach((r) => URL.revokeObjectURL(r.preview)), []); // eslint-disable-line

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Upload one file at a time (vision runs on each).
  useEffect(() => {
    if (running.current) return;
    const next = rows.findIndex((r) => r.state === "waiting");
    if (next < 0) return;
    running.current = true;
    const patch = (p: Partial<Row>) => setRows((rs) => rs.map((r, i) => (i === next ? { ...r, ...p } : r)));
    patch({ state: "uploading" });
    api.upload(userId, rows[next].file)
      .then((item) => { patch({ state: "done", item }); onUploaded(item); })
      .catch((e: Error) => patch({ state: "error", error: e.message }))
      .finally(() => { running.current = false; setRows((rs) => [...rs]); });
  }, [rows, userId, onUploaded]);

  const add = (files: FileList | null) => {
    if (!files) return;
    const imgs = Array.from(files).filter((f) => f.type.startsWith("image/"));
    setRows((rs) => [...rs, ...imgs.map((file) => ({ file, preview: URL.createObjectURL(file), state: "waiting" as const }))]);
  };

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="dialog" role="dialog" aria-modal="true" aria-label="Add clothes">
        <div className="drawer-head">
          <h2>Add clothes</h2>
          <button className="btn ghost icon" onClick={onClose} aria-label="Close"><IconClose /></button>
        </div>
        <div
          className={`dropzone ${over ? "over" : ""}`}
          onClick={() => input.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); add(e.dataTransfer.files); }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        >
          <IconUpload size={26} />
          <div style={{ fontWeight: 500, color: "var(--text)" }}>Drop photos here, or click to choose</div>
          <div className="small muted" style={{ marginTop: 4 }}>
            One garment per photo works best. Each one is tagged automatically.
          </div>
          <input ref={input} type="file" accept="image/*" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        </div>
        {rows.length > 0 && (
          <div className="uploads">
            {rows.map((r, i) => (
              <div className="upload-row" key={i}>
                <img src={r.preview} alt="" />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.item?.category ?? r.file.name}
                  </div>
                  <div className="small muted">
                    {r.state === "waiting" && "Waiting"}
                    {r.state === "uploading" && "Analysing the photo"}
                    {r.state === "done" && (r.item?.status === "ready"
                      ? asList(r.item.color).join(", ") || "Tagged"
                      : r.item?.status === "failed" ? "Saved, but tagging failed. You can re-analyse or tag it by hand."
                      : "Saved. Add its details from the wardrobe.")}
                    {r.state === "error" && <span style={{ color: "var(--danger)" }}>{r.error}</span>}
                  </div>
                </div>
                {r.state === "uploading" ? <span className="spinner" /> : r.state === "done" ? (
                  <span style={{ color: r.item?.status === "ready" ? "var(--ok)" : "var(--warn)" }}><IconCheck /></span>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
