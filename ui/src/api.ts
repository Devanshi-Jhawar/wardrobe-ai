// Every call goes to the agent (the API gateway) under /api.
import type { AgentReply, Health, Item, Memory, Preferences, WornEntry } from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    throw new ApiError(0, "Can't reach the server. Is the agent running on port 8000?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const q = (params: Record<string, string | number | boolean>) =>
  "?" + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();

export const api = {
  health: () => request<Health>("/health"),

  ask: (user_id: string, query: string) =>
    request<AgentReply>("/agent", json("POST", { user_id, query })),

  wardrobe: (user_id: string) =>
    request<{ count: number; items: Item[] }>("/wardrobe" + q({ user_id, limit: 200 })),

  upload: (user_id: string, file: File) => {
    const form = new FormData();
    form.append("user_id", user_id);
    form.append("file", file);
    return request<Item>("/wardrobe/items", { method: "POST", body: form });
  },

  updateItem: (user_id: string, id: string, changes: Partial<Item>) =>
    request<Item>(`/wardrobe/items/${id}` + q({ user_id }), json("PATCH", changes)),

  deleteItem: (user_id: string, id: string) =>
    request<void>(`/wardrobe/items/${id}` + q({ user_id }), { method: "DELETE" }),

  enrichItem: (user_id: string, id: string) =>
    request<Item>(`/wardrobe/items/${id}/enrich` + q({ user_id }), { method: "POST" }),

  imageUrl: (user_id: string, id: string, thumb = true) =>
    `${BASE}/wardrobe/items/${id}/image` + q({ user_id, thumb }),

  memory: (user_id: string) => request<Memory>("/memory" + q({ user_id })),

  setPreferences: (user_id: string, prefs: Partial<Preferences>) =>
    request<Preferences>("/memory/preferences" + q({ user_id }), json("PUT", prefs)),

  history: (user_id: string) =>
    request<{ total: number; outfits: WornEntry[] }>("/memory/history" + q({ user_id, limit: 50 })),

  deleteWorn: (user_id: string, entry_id: string) =>
    request<void>(`/memory/worn/${entry_id}` + q({ user_id }), { method: "DELETE" }),

  wear: (user_id: string, item_ids: string[], occasion?: string | null, city?: string | null) =>
    request<unknown>("/wear", json("POST", { user_id, item_ids, occasion, city })),

  rate: (user_id: string, item_ids: string[], liked: boolean) =>
    request<unknown>("/rate", json("POST", { user_id, item_ids, liked })),
};
