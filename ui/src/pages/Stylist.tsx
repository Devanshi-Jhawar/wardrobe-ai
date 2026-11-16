import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { AnswerView } from "../components/AnswerView";
import { IconSend } from "../icons";
import type { AgentReply } from "../types";
import { store } from "../util";

type Turn =
  | { role: "user"; text: string }
  | { role: "agent"; reply: AgentReply }
  | { role: "error"; text: string };

const PROMPTS = [
  { title: "Office tomorrow", text: "What should I wear to office tomorrow?" },
  { title: "A four-day trip", text: "4 day trip to Goa: day 1 beach, day 2 wedding, day 3 sightseeing, day 4 flight home" },
  { title: "Wear something specific", text: "I want to wear my red saree this weekend for a festival" },
  { title: "What am I missing", text: "What should I buy to round out my wardrobe?" },
];

export function Stylist({ userId }: { userId: string }) {
  const key = `wardrobe-ai.thread.${userId}`;
  const [turns, setTurns] = useState<Turn[]>(() => store.get<Turn[]>(key, []));
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setTurns(store.get<Turn[]>(key, [])); }, [key]);
  useEffect(() => { store.set(key, turns.slice(-30)); }, [key, turns]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, busy]);

  const send = async (q: string) => {
    const query = q.trim();
    if (!query || busy) return;
    setText("");
    setTurns((t) => [...t, { role: "user", text: query }]);
    setBusy(true);
    try {
      const reply = await api.ask(userId, query);
      setTurns((t) => [...t, { role: "agent", reply }]);
    } catch (e) {
      setTurns((t) => [...t, { role: "error", text: (e as Error).message }]);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  };

  const grow = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  return (
    <div className="stylist">
      <div className="thread">
        <div className="thread-inner">
          {turns.length === 0 && (
            <div className="welcome">
              <div className="eyebrow">Your stylist</div>
              <h1>What are we dressing for?</h1>
              <p className="lede">
                Describe the occasion, the city and the day, or a whole trip. I'll check the forecast,
                your wardrobe and what you like, then put the outfit together.
              </p>
              <div className="prompts">
                {PROMPTS.map((p) => (
                  <button key={p.title} className="prompt" onClick={() => send(p.text)}>
                    <b>{p.title}</b><span>{p.text}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((t, i) =>
            t.role === "user" ? (
              <div key={i} className="msg-user">{t.text}</div>
            ) : t.role === "agent" ? (
              <AnswerView key={i} userId={userId} reply={t.reply} />
            ) : (
              <div key={i} className="notice error">{t.text}</div>
            ),
          )}

          {busy && (
            <div className="thinking"><span className="spinner" /> Checking your wardrobe and the forecast</div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="composer-bar">
        <div className="composer-inner">
          <form className="composer-box" onSubmit={(e) => { e.preventDefault(); send(text); }}>
            <textarea
              ref={inputRef}
              rows={1}
              value={text}
              placeholder="Office tomorrow in Pune, or: I don't like frocks"
              onChange={(e) => { setText(e.target.value); grow(e.target); }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); }
              }}
              aria-label="Ask your stylist"
            />
            <button className="btn primary icon" type="submit" disabled={!text.trim() || busy} aria-label="Send">
              <IconSend />
            </button>
          </form>
          <div className="composer-hint">
            {turns.length > 0 ? (
              <button className="btn ghost sm" onClick={() => setTurns([])}>Clear conversation</button>
            ) : (
              "Tell me what you like or dislike at any time and I'll remember it."
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
