from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agents.ensemble import analyze_transcript
from agents.executor import execute_decision
from agents.explainer import explain_decision


class OracleState(TypedDict, total=False):
    transcript: str
    prices: dict[str, float]
    decision: dict[str, Any]
    execution: str
    explanation: str


async def analyze_node(state: OracleState) -> OracleState:
    decision = await analyze_transcript(state["transcript"], state.get("prices", {}))
    return {**state, "decision": decision}


def execute_node(state: OracleState) -> OracleState:
    execution = execute_decision(state["decision"])
    return {**state, "execution": execution}


def explain_node(state: OracleState) -> OracleState:
    explanation = explain_decision(state["decision"])
    return {**state, "explanation": explanation}


def build_workflow():
    graph = StateGraph(OracleState)
    graph.add_node("analyze", analyze_node)
    graph.add_node("execute", execute_node)
    graph.add_node("explain", explain_node)
    graph.set_entry_point("analyze")
    graph.add_edge("analyze", "execute")
    graph.add_edge("execute", "explain")
    graph.add_edge("explain", END)
    return graph.compile()
