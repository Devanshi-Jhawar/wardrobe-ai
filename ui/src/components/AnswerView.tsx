import { useState } from "react";
import { api } from "../api";
import { IconArrowOut, IconCheck, IconChevron, IconThumbDown, IconThumbUp } from "../icons";
import type { AgentReply, Suggestion, TripDay } from "../types";
import { capitalize, formatDate } from "../util";
import { Look } from "./Look";

const KIND_LABEL: Record<string, string> = {
  missing: "Missing", occasion: "For the occasion", weather: "For the weather",
  complement: "Completes the look", coverage: "Wardrobe gap",
};

function Suggestions({ items, title }: { items: Suggestion[]; title: string }) {
  if (!items.length) return null;
  return (
    <section>
      <h3>{title}</h3>
      <div className="suggestions">
        {items.map((s, i) => (
          <div className="suggestion" key={i}>
            <div>
              <div className="suggestion-title">
                {s.title}
                <span className="tag accent">{KIND_LABEL[s.kind] ?? capitalize(s.kind)}</span>
                {s.day ? <span className="tag">Day {s.day}</span> : null}
              </div>
              <div className="suggestion-reason">{capitalize(s.reason)}.</div>
              <div className="suggestion-rule">{s.rule}</div>
            </div>
            <a className="btn sm" href={s.search_link} target="_blank" rel="noreferrer">
              Shop <IconArrowOut size={14} />
            </a>
          </div>
        ))}
      </div>
    </section>
  );
}

/** "I'm wearing this" / like / dislike for one outfit. */
function OutfitActions({ userId, ids, occasion, city }: {
  userId: string; ids: string[]; occasion: string | null; city: string | null;
}) {
  const [done, setDone] = useState<null | "worn" | "liked" | "disliked">(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!ids.length) return null;

  const run = async (kind: "worn" | "liked" | "disliked") => {
    setBusy(true);
    setError(null);
    try {
      if (kind === "worn") await api.wear(userId, ids, occasion, city);
      else await api.rate(userId, ids, kind === "liked");
      setDone(kind);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="actions">
        <button className={`btn sm ${done === "worn" ? "active" : ""}`} disabled={busy || done === "worn"} onClick={() => run("worn")}>
          <IconCheck size={15} /> {done === "worn" ? "Logged as worn" : "I'm wearing this"}
        </button>
        <button className={`btn sm ${done === "liked" ? "active" : ""}`} disabled={busy} onClick={() => run("liked")} aria-label="Like this outfit">
          <IconThumbUp size={15} /> Like
        </button>
        <button className={`btn sm ${done === "disliked" ? "active" : ""}`} disabled={busy} onClick={() => run("disliked")} aria-label="Dislike this outfit">
          <IconThumbDown size={15} /> Not for me
        </button>
      </div>
      {done === "disliked" && <span className="small muted">Noted. These pieces won't be suggested again.</span>}
      {done === "worn" && <span className="small muted">Saved to your history, so these won't repeat for a few days.</span>}
      {error && <span className="small" style={{ color: "var(--danger)" }}>{error}</span>}
    </div>
  );
}

function Day({ userId, d }: { userId: string; d: TripDay }) {
  return (
    <div className="card day">
      <div className="day-head">
        <span className="day-num">Day {d.day}</span>
        <span className="day-date">{formatDate(d.date)}</span>
      </div>
      <div className="day-weather">
        {d.max != null && <span className="tag">{Math.round(d.max)}&deg;{d.min != null ? ` / ${Math.round(d.min)}°` : ""}</span>}
        {d.label && <span className="tag">{d.label}</span>}
        {d.rainy && <span className="tag warn">Rain</span>}
        {d.occasion && <span className="tag accent">{d.occasion}</span>}
      </div>
      {d.activity && d.activity !== d.occasion && <div className="day-activity">{d.activity}</div>}
      {d.outfit.length ? (
        <div className="day-items">
          {d.outfit.map((it, i) => <Look key={(it.id ?? "") + i} userId={userId} item={it} compact />)}
        </div>
      ) : (
        <span className="small muted">Nothing suitable in your wardrobe for this day.</span>
      )}
    </div>
  );
}

function HowIRead({ reply }: { reply: AgentReply }) {
  const d = reply.debug;
  const dates = d.dates && Object.keys(d.dates).length
    ? Object.entries(d.dates).map(([k, v]) => `${k}: ${v}`).join(", ") : "not specified";
  return (
    <details className="how">
      <summary><IconChevron size={13} /> How I read this</summary>
      <dl>
        <dt>Understood by</dt><dd>{d.planner === "llm" ? "LLM planner" : "Rules planner"}</dd>
        <dt>Intent</dt><dd>{reply.intent}</dd>
        <dt>Occasion</dt><dd>{d.occasion ?? "none"}</dd>
        <dt>City</dt><dd>{d.city ?? "default location"}</dd>
        <dt>Dates</dt><dd>{dates}</dd>
        {d.itinerary?.length ? (
          <><dt>Itinerary</dt><dd>{d.itinerary.map((x) => `Day ${x.day}: ${x.occasion ?? x.activity ?? "open"}`).join("; ")}</dd></>
        ) : null}
        {d.search_text ? <><dt>Looking for</dt><dd>{d.search_text}</dd></> : null}
        {d.critic_notes ? <><dt>Critic</dt><dd>{d.critic_notes}{d.attempts ? ` (${d.attempts} pass${d.attempts > 1 ? "es" : ""})` : ""}</dd></> : null}
        <dt>Wardrobe</dt><dd>{d.wardrobe_count} items considered</dd>
      </dl>
    </details>
  );
}

export function AnswerView({ userId, reply }: { userId: string; reply: AgentReply }) {
  const a = reply.answer;
  const firstLine = a.message.split("\n")[0];

  if (a.type === "preference_saved" || a.type === "preference_not_saved") {
    return (
      <div className="msg-agent">
        <div className="lead">{firstLine}</div>
        {a.type === "preference_saved" && a.remembered?.length ? (
          <div className="chips">
            {a.remembered.map((r) => (
              <span key={r} className="chip static" aria-pressed="true">
                {a.kind === "like" ? "Likes" : "Avoids"}: {r}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  if (a.type === "gap") {
    return (
      <div className="msg-agent">
        <div className="lead">{a.suggestions?.length ? "Here is what would round out your wardrobe." : firstLine}</div>
        <Suggestions items={a.suggestions ?? []} title="Worth adding" />
        <HowIRead reply={reply} />
      </div>
    );
  }

  if (a.type === "trip_plan") {
    const days = a.days ?? [];
    const where = reply.debug.city ? ` in ${reply.debug.city}` : "";
    return (
      <div className="msg-agent">
        <div className="lead">Your {days.length}-day plan{where}.</div>
        <div className="days">{days.map((d) => <Day key={d.day} userId={userId} d={d} />)}</div>
        {a.packing_list?.length ? (
          <section>
            <h3>Packing list &middot; {a.packing_list.length} pieces</h3>
            <div className="outfit-grid">
              {a.packing_list.map((it, i) => <Look key={(it.id ?? "") + i} userId={userId} item={it} />)}
            </div>
          </section>
        ) : null}
        {a.carry?.length ? <div className="facts"><span><b>Also carry</b>{a.carry.join(", ")}</span></div> : null}
        <OutfitActions userId={userId} ids={(a.packing_list ?? []).map((i) => i.id).filter(Boolean) as string[]}
          occasion={null} city={reply.debug.city} />
        <Suggestions items={a.suggestions ?? []} title="To complete the trip" />
        <HowIRead reply={reply} />
      </div>
    );
  }

  // recommendation
  const outfit = a.outfit ?? [];
  return (
    <div className="msg-agent">
      <div className="lead">
        {outfit.length ? "Here is what I would wear." : "I couldn't put a full outfit together from your wardrobe yet."}
      </div>
      {a.rationale && a.rationale !== "general recommendation" && (
        <div className="msg-meta">
          {a.rationale.split("; ").map((r) => <span key={r} className="tag">{r}</span>)}
        </div>
      )}
      {outfit.length > 0 && (
        <div className="outfit-grid">
          {outfit.map((it, i) => <Look key={(it.id ?? "") + i} userId={userId} item={it} />)}
        </div>
      )}
      {a.carry?.length ? <div className="facts"><span><b>Also carry</b>{a.carry.join(", ")}</span></div> : null}
      <OutfitActions userId={userId} ids={a.item_ids ?? []} occasion={reply.debug.occasion} city={reply.debug.city} />
      <Suggestions items={a.suggestions ?? []} title="To complete the look" />
      <HowIRead reply={reply} />
    </div>
  );
}
