"""
LangGraph Graph Definition
Wires all nodes together with conditional edges and a HITL breakpoint.

Graph flow:
  scanner → architect → developer → [HITL breakpoint] → submitter
                            ↑                                |
                            └────── feedback loop ───────────┘
"""

import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.agent.state import AgentState
from src.agent.nodes.scanner import scanner_node
from src.agent.nodes.architect import architect_node
from src.agent.nodes.developer import developer_node
from src.agent.nodes.submitter import submitter_node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routing functions (conditional edges)
# ---------------------------------------------------------------------------

def route_after_scanner(state: AgentState) -> Literal["architect", "end"]:
    if state.error_message or state.selected_issue is None:
        logger.error(f"Scanner failed: {state.error_message}")
        return "end"
    return "architect"


def route_after_architect(state: AgentState) -> Literal["developer", "end"]:
    if state.error_message or state.implementation_plan is None:
        logger.error(f"Architect failed: {state.error_message}")
        return "end"
    return "developer"


def route_after_hitl(state: AgentState) -> Literal["submitter", "developer", "end"]:
    """
    This edge fires AFTER the human has injected their decision into state
    (via graph.update_state). The breakpoint itself is handled by LangGraph.
    """
    decision = state.human_decision
    if decision is None:
        return "end"

    if decision.action == "approve":
        return "submitter"

    elif decision.action == "feedback":
        if state.iteration_count >= state.max_iterations:
            logger.warning("Max feedback iterations reached. Ending run.")
            return "end"
        return "developer"

    else:  # reject
        return "end"


def route_after_developer(state: AgentState) -> Literal["hitl", "end"]:
    if state.error_message or state.diff_result is None:
        logger.error(f"Developer failed: {state.error_message}")
        return "end"
    return "hitl"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Construct and compile the LangGraph state machine."""

    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("scanner", scanner_node)
    builder.add_node("architect", architect_node)
    builder.add_node("developer", developer_node)
    builder.add_node("hitl", lambda state: state)   # pass-through; breakpoint here
    builder.add_node("submitter", submitter_node)

    # Entry point
    builder.set_entry_point("scanner")

    # Edges
    builder.add_conditional_edges("scanner", route_after_scanner,
                                  {"architect": "architect", "end": END})
    builder.add_conditional_edges("architect", route_after_architect,
                                  {"developer": "developer", "end": END})
    builder.add_conditional_edges("developer", route_after_developer,
                                  {"hitl": "hitl", "end": END})

    # The HITL breakpoint: graph pauses BEFORE this edge fires.
    # main.py manually calls graph.update_state() with the human's decision,
    # then resumes execution.
    builder.add_conditional_edges("hitl", route_after_hitl,
                                  {"submitter": "submitter",
                                   "developer": "developer",
                                   "end": END})

    builder.add_edge("submitter", END)

    # MemorySaver enables state persistence (supports interrupt/resume)
    checkpointer = MemorySaver()
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl"],   # ← HITL breakpoint
    )


# Singleton graph instance
graph = build_graph()
