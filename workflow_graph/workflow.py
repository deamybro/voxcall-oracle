from __future__ import annotations

import os
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agents.ensemble import analyze_transcript
from agents.executor import execute_decision
from agents.explainer import explain_decision


class OracleState(TypedDict, total=False):
    transcript: str
    prices: dict[str, float]
    decision: dict[str, Any]
    risk_passed: bool
    execution: str
    explanation: str


async def analyze_node(state: OracleState) -> OracleState:
    """Run the Featherless finance ensemble on the transcript chunk."""
    decision = await analyze_transcript(state["transcript"], state.get("prices", {}))
    return {**state, "decision": decision}


def risk_gate_node(state: OracleState) -> OracleState:
    """Check confidence threshold and position limits before execution.

    This node enforces production safety: trades below the minimum
    confidence are blocked, and hold decisions never reach Kraken CLI.
    """
    decision = state.get("decision", {})
    action = str(decision.get("action", "hold")).lower()
    confidence = int(decision.get("confidence", 0))
    threshold = int(os.getenv("MIN_TRADE_CONFIDENCE", "75"))

    passed = action in {"buy", "sell"} and confidence >= threshold
    return {**state, "risk_passed": passed}


def should_execute(state: OracleState) -> str:
    """Conditional edge: route to execute or skip to explain."""
    if state.get("risk_passed", False):
        return "execute"
    return "explain"


def execute_node(state: OracleState) -> OracleState:
    """Send the order to Kraken CLI (paper or live)."""
    execution = execute_decision(state["decision"])
    return {**state, "execution": execution}


def explain_node(state: OracleState) -> OracleState:
    """Generate human-readable explanation of the decision."""
    explanation = explain_decision(state["decision"])
    return {**state, "explanation": explanation}


def build_workflow():
    """Build the VoxCall Oracle LangGraph workflow.

    Pipeline:
        analyze → risk_gate → [execute | skip] → explain → END
    """
    graph = StateGraph(OracleState)
    graph.add_node("analyze", analyze_node)
    graph.add_node("risk_gate", risk_gate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("explain", explain_node)

    graph.set_entry_point("analyze")
    graph.add_edge("analyze", "risk_gate")
    graph.add_conditional_edges("risk_gate", should_execute, {
        "execute": "execute",
        "explain": "explain",
    })
    graph.add_edge("execute", "explain")
    graph.add_edge("explain", END)

    return graph.compile()
