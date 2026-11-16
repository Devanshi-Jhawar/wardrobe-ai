// Small shared helpers.

export const CATEGORIES = [
  "Anarkali", "Bag", "Blazer", "Dress", "Dupatta", "Hoodie", "Jacket", "Jeans", "Jewellery",
  "Kameez", "Kurti", "Lehenga", "Maxi", "Saree", "Shalwar", "Sharara", "Sherwani", "Shirt",
  "Shoes", "Skirt", "Slippers", "Sunglasses", "T-Shirt",
];
export const OCCASIONS = ["casual", "office", "party", "wedding", "festival", "date", "gym", "trip"];
export const SEASONS = ["summer", "spring", "autumn", "winter"];

export const SLOT_LABELS: Record<string, string> = {
  top: "Tops", bottom: "Bottoms", onepiece: "One-pieces", footwear: "Footwear",
  outerwear: "Layers", accessory: "Accessories",
};

// Approximate display colours for the names the vision service uses.
const COLOR_HEX: Record<string, string> = {
  black: "#111", white: "#f4f2ee", grey: "#8a8a8a", gray: "#8a8a8a", silver: "#c0c0c0",
  red: "#b3261e", maroon: "#6d1a1f", pink: "#e79bb0", orange: "#de7a2f", peach: "#f2b48f",
  yellow: "#e8c640", mustard: "#c99a1c", gold: "#c9a96e", beige: "#d8c7a7", cream: "#efe6cf",
  tan: "#c49a6c", brown: "#6e4a2f", khaki: "#b3a16f", olive: "#6b6b32", green: "#3e7a4a",
  teal: "#227a7a", mint: "#a8dcc0", blue: "#2f5fb3", navy: "#1d2a4d", "sky blue": "#8cc4e8",
  purple: "#6a3d8f", lavender: "#b9a6dc", magenta: "#b0307a",
};

export function colorHex(name: string): string {
  return COLOR_HEX[name.toLowerCase()] ?? "#555";
}

export function asList(v: string[] | string | null | undefined): string[] {
  if (!v) return [];
  return Array.isArray(v) ? v : [v];
}

export function describe(item: { category: string | null; color: string[] | string | null }): string {
  const c = asList(item.color)[0];
  return [c, item.category].filter(Boolean).join(" ") || "Item";
}

export function formatDate(iso: string | null | undefined, opts?: Intl.DateTimeFormatOptions): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, opts ?? { weekday: "short", day: "numeric", month: "short" });
}

export function capitalize(s: string | null | undefined): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

// Per-browser conveniences; never required for the app to work.
export const store = {
  get<T>(key: string, fallback: T): T {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : (JSON.parse(raw) as T);
    } catch {
      return fallback;
    }
  },
  set(key: string, value: unknown) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage unavailable */
    }
  },
};
