"""The agent's brain, wired as a LangGraph flowchart.

Nodes are the step functions in nodes/*. Edges decide what runs next. The two
*conditional* edges are where the intelligence lives:

  planner ─► (preference?) ─► remember ─► answer
            └►(otherwise)──► gather ─► (gap question?) ─► gap ─► answer
                                      └►(recommend/trip)► composer ─► critic
                                                                       │
                              ┌──── critic passed ──► gap ─► answer ───┘
                              └──── critic failed ──► composer   (replan loop,
                                                                  capped in critic)

Build once at import, reuse for every request.
"""
from langgraph.graph import StateGraph, START, END

from .state import OutfitState
from .nodes.planner import planner
from .nodes.gather import gather
from .nodes.composer import composer
from .nodes.critic import critic
from .nodes.gap import gap
from .nodes.answer import answer
from .nodes.remember import remember


# --- routers for the conditional edges ---

def _after_planner(state: OutfitState) -> str:
    return "remember" if state.get("intent") == "save_preference" else "gather"


def _after_gather(state: OutfitState) -> str:
    # A pure "what to buy" question skips outfit-building and goes to gap.
    return "gap" if state.get("intent") == "gap" else "composer"


def _after_critic(state: OutfitState) -> str:
    # Passed -> move on to gap suggestions; failed -> replan with the composer.
    return "gap" if state.get("critic_passed") else "composer"


def build_graph():
    g = StateGraph(OutfitState)

    g.add_node("planner", planner)
    g.add_node("gather", gather)
    g.add_node("composer", composer)
    g.add_node("critic", critic)
    g.add_node("gap", gap)
    g.add_node("answer", answer)
    g.add_node("remember", remember)

    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", _after_planner,
                            {"remember": "remember", "gather": "gather"})
    g.add_edge("remember", "answer")
    g.add_conditional_edges("gather", _after_gather,
                            {"gap": "gap", "composer": "composer"})
    g.add_edge("composer", "critic")
    g.add_conditional_edges("critic", _after_critic,
                            {"gap": "gap", "composer": "composer"})
    g.add_edge("gap", "answer")
    g.add_edge("answer", END)

    return g.compile()


# A single compiled graph the API reuses.
AGENT = build_graph()


def run_agent(query: str, user_id: str = "demo") -> dict:
    """Run one request end-to-end and return the final State."""
    return AGENT.invoke({"query": query, "user_id": user_id, "attempts": 0})
