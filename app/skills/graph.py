"""
LangGraph workflow for SSB Journey Voice Skills and State Management.
Orchestrates dynamic intent classification and skill prompt routing.
"""

from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import END, START, StateGraph

from app.skills.prompt_manager import prompt_manager


class SSBCandidateState(TypedDict, total=False):
    """
    Candidate state tracked across the voice session.
    """
    candidate_name: Optional[str]
    target_entry: Optional[str]
    ssb_board: Optional[str]
    attempt_type: Optional[str]
    current_skill: str
    intent: Optional[str]
    query: Optional[str]
    language: str
    active_prompt: Optional[str]
    history: List[Dict[str, Any]]
    transition_reason: Optional[str]


def skill_router_node(state: SSBCandidateState) -> Dict[str, Any]:
    """
    Evaluates detected intent or text query to select the next skill.
    """
    intent = (state.get("intent") or "").lower().strip()
    query = (state.get("query") or "").lower().strip()

    # Explicit intent has highest priority
    if intent in ["onboarding", "profile", "welcome"]:
        selected = "onboarding"
    elif intent in ["roadmap", "doubt", "doubts", "stages", "ppdt", "oir", "psych", "gto"]:
        selected = "roadmap"
    elif intent in ["checklist", "documents", "clothing", "dress", "kit"]:
        selected = "checklist"
    elif intent in ["mock_interview", "olq", "mock", "interview"]:
        selected = "mock_interview"
    elif intent in ["motivation", "demotivation", "anxiety", "quote"]:
        selected = "motivation"
    elif query:
        # Fallback keyword classification on candidate text query
        if any(w in query for w in ["checklist", "document", "marksheet", "clothing", "dress", "kit", "shoes", "call letter", "tie"]):
            selected = "checklist"
        elif any(w in query for w in ["mock", "interview", "question", "olq", "feedback", "practice", "ask me"]):
            selected = "mock_interview"
        elif any(w in query for w in ["demotivated", "nervous", "dar", "tension", "afraid", "confidence", "quote", "motivate"]):
            selected = "motivation"
        elif any(w in query for w in ["day", "stage", "screening", "ppdt", "oir", "tat", "wat", "srt", "sd", "gto", "conference"]):
            selected = "roadmap"
        else:
            selected = state.get("current_skill") or "roadmap"
    else:
        selected = state.get("current_skill") or "onboarding"

    return {"intent": selected}


def route_decision(state: SSBCandidateState) -> str:
    """Returns the name of the node to execute next."""
    return state.get("intent", "roadmap")


def onboarding_node(state: SSBCandidateState) -> Dict[str, Any]:
    lang = state.get("language", "hinglish")
    return {
        "current_skill": "onboarding",
        "active_prompt": prompt_manager.get_skill_prompt("onboarding", language=lang),
    }


def roadmap_node(state: SSBCandidateState) -> Dict[str, Any]:
    lang = state.get("language", "hinglish")
    return {
        "current_skill": "roadmap",
        "active_prompt": prompt_manager.get_skill_prompt("roadmap", language=lang),
    }


def checklist_node(state: SSBCandidateState) -> Dict[str, Any]:
    lang = state.get("language", "hinglish")
    return {
        "current_skill": "checklist",
        "active_prompt": prompt_manager.get_skill_prompt("checklist", language=lang),
    }


def mock_interview_node(state: SSBCandidateState) -> Dict[str, Any]:
    lang = state.get("language", "hinglish")
    return {
        "current_skill": "mock_interview",
        "active_prompt": prompt_manager.get_skill_prompt("mock_interview", language=lang),
    }


def motivation_node(state: SSBCandidateState) -> Dict[str, Any]:
    lang = state.get("language", "hinglish")
    return {
        "current_skill": "motivation",
        "active_prompt": prompt_manager.get_skill_prompt("motivation", language=lang),
    }


# ==========================================
# LangGraph Workflow Definition & Compilation
# ==========================================

def build_ssb_skill_graph():
    workflow = StateGraph(SSBCandidateState)

    workflow.add_node("router", skill_router_node)
    workflow.add_node("onboarding", onboarding_node)
    workflow.add_node("roadmap", roadmap_node)
    workflow.add_node("checklist", checklist_node)
    workflow.add_node("mock_interview", mock_interview_node)
    workflow.add_node("motivation", motivation_node)

    workflow.add_edge(START, "router")
    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "onboarding": "onboarding",
            "roadmap": "roadmap",
            "checklist": "checklist",
            "mock_interview": "mock_interview",
            "motivation": "motivation",
        },
    )

    workflow.add_edge("onboarding", END)
    workflow.add_edge("roadmap", END)
    workflow.add_edge("checklist", END)
    workflow.add_edge("mock_interview", END)
    workflow.add_edge("motivation", END)

    return workflow.compile()


ssb_skill_graph = build_ssb_skill_graph()


def create_initial_state(language: str = "hinglish") -> SSBCandidateState:
    """Creates a clean candidate state initialized in onboarding mode."""
    return SSBCandidateState(
        candidate_name=None,
        target_entry=None,
        ssb_board=None,
        attempt_type=None,
        current_skill="onboarding",
        intent="onboarding",
        query=None,
        language=language,
        active_prompt=prompt_manager.get_skill_prompt("onboarding", language=language),
        history=[],
        transition_reason="Session started",
    )


def transition_skill(
    current_state: SSBCandidateState,
    intent: Optional[str] = None,
    query: Optional[str] = None,
    details: Optional[Dict[str, Optional[str]]] = None,
    reason: Optional[str] = None,
) -> SSBCandidateState:
    """
    Executes a LangGraph state transition and updates candidate state.
    """
    updated_state = dict(current_state)
    if intent:
        updated_state["intent"] = intent
    elif query is not None:
        # Reset previous intent when a new query is provided so router evaluates query
        updated_state["intent"] = None

    if query is not None:
        updated_state["query"] = query
    if reason:
        updated_state["transition_reason"] = reason

    if details:
        for k, v in details.items():
            if v and str(v).lower() not in ["none", "null", "undefined"]:
                if k in ["name", "candidate_name"]:
                    updated_state["candidate_name"] = str(v).strip()
                elif k in ["target_entry", "entry", "course"]:
                    updated_state["target_entry"] = str(v).strip()
                elif k in ["ssb_board", "board", "center"]:
                    updated_state["ssb_board"] = str(v).strip()
                elif k in ["attempt_type", "attempt", "fresher_repeater"]:
                    updated_state["attempt_type"] = str(v).strip()

    result = ssb_skill_graph.invoke(updated_state)
    updated_state.update(result)
    return updated_state
