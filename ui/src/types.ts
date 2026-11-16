export type Slot = "top" | "bottom" | "onepiece" | "footwear" | "outerwear" | "accessory" | null;

export interface Item {
  id: string;
  user_id: string;
  category: string | null;
  color: string[] | null;
  pattern: string | null;
  material: string | null;
  style: string | null;
  occasion: string[] | null;
  season: string[] | null;
  attributes: Record<string, unknown> | null;
  status: "pending" | "ready" | "failed" | string;
  is_favorite: boolean;
  wear_count: number;
  last_worn_at: string | null;
  created_at: string;
  slot?: Slot;
}

export interface OutfitItem {
  id: string | null;
  category: string | null;
  color: string[] | string | null;
  style?: string | null;
}

export interface Suggestion {
  kind: "missing" | "occasion" | "weather" | "complement" | "coverage" | string;
  slot: string | null;
  title: string;
  reason: string;
  suggestion: string;
  rule: string;
  query: string;
  search_link: string;
  day?: number;
}

export interface TripDay {
  day: number;
  date: string | null;
  label: string | null;
  max: number | null;
  min: number | null;
  rainy: boolean | null;
  occasion: string | null;
  activity: string | null;
  outfit: OutfitItem[];
  item_ids: string[];
  rationale: string | null;
}

export interface Answer {
  type:
    | "recommendation"
    | "trip_plan"
    | "gap"
    | "preference_saved"
    | "preference_not_saved";
  message: string;
  outfit?: OutfitItem[];
  item_ids?: string[];
  carry?: string[];
  rationale?: string | null;
  critic_notes?: string | null;
  attempts?: number;
  suggestions?: Suggestion[];
  days?: TripDay[];
  packing_list?: OutfitItem[];
  kind?: "like" | "dislike";
  remembered?: string[];
}

export interface AgentReply {
  answer: Answer;
  intent: string;
  debug: {
    occasion: string | null;
    city: string | null;
    dates: Record<string, unknown> | null;
    itinerary: { day: number; occasion: string | null; activity: string | null }[] | null;
    planner: "llm" | "rules" | null;
    attempts: number | null;
    critic_notes: string | null;
    wardrobe_count: number;
    search_text: string | null;
    search_matches: number;
  };
}

export interface Preferences {
  likes: string[];
  dislikes: string[];
  avoid_repeat_days: number;
}

export interface WornEntry {
  id: string;
  worn_on: string;
  item_ids: string[];
  occasion: string | null;
  city: string | null;
  note: string | null;
  created_at: string;
}

export interface Memory {
  user_id: string;
  preferences: Preferences;
  recently_worn_item_ids: string[];
  liked_item_ids: string[];
  disliked_item_ids: string[];
  recent_outfits: WornEntry[];
}

export interface Health {
  status: string;
  mode: string;
  llm: { enabled: boolean; provider: string | null; model: string | null };
  services: Record<string, boolean>;
}
