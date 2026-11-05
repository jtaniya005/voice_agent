import os
import sys

# Ensure backend root is on Python module path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.skills import (
    prompt_manager,
    create_initial_state,
    transition_skill,
)


def test_prompt_manager_loading():
    """Verify all skill prompt files are loaded and non-empty."""
    base = prompt_manager.get_base_mentor()
    assert len(base) > 100
    assert "SSB Journey" in base

    onboarding = prompt_manager.get_onboarding_rules()
    assert len(onboarding) > 100
    assert "SSB Journey" in onboarding

    roadmap = prompt_manager.get_roadmap_doubts_rules()
    assert len(roadmap) > 100
    assert "PPDT" in roadmap

    checklist = prompt_manager.get_checklist_rules()
    assert len(checklist) > 100
    assert "68 Items" in checklist or "Mandatory Documents" in checklist

    mock = prompt_manager.get_mock_interview_rules()
    assert len(mock) > 100
    assert "15 Officer Like Qualities" in mock

    motivation = prompt_manager.get_motivation_rules()
    assert len(motivation) > 100
    assert "20 CURATED" in motivation

    unified = prompt_manager.get_unified_mentor_prompt(language="hinglish")
    assert len(unified) > 1000
    assert "SSB Journey" in unified
    print("[PASS] PromptManager successfully loaded all modular skill prompts.")


def test_langgraph_workflow_transitions():
    """Verify LangGraph StateGraph handles intent transitions and candidate details tracking."""
    # 1. Initial State
    state = create_initial_state(language="hinglish")
    assert state["current_skill"] == "onboarding"
    assert state["candidate_name"] is None

    # 2. Extract Candidate Details
    state = transition_skill(
        state,
        details={"name": "Vikram Batra", "target_entry": "CDS", "ssb_board": "1 AFSB Dehradun"},
    )
    assert state["candidate_name"] == "Vikram Batra"
    assert state["target_entry"] == "CDS"
    assert state["ssb_board"] == "1 AFSB Dehradun"

    # 3. Transition to Checklist via explicit intent
    state = transition_skill(state, intent="checklist", reason="Candidate asked about dress code")
    assert state["current_skill"] == "checklist"
    assert "CHECKLIST" in state["active_prompt"]

    # 4. Transition to Motivation via query keyword
    state = transition_skill(state, query="Sir mujhe bahut tension aur dar lag raha hai screening ka")
    assert state["current_skill"] == "motivation"
    assert "MOTIVATION" in state["active_prompt"]

    # 5. Transition to Mock Interview via query keyword
    state = transition_skill(state, query="Can you take a mock interview and ask me an OLQ question?")
    assert state["current_skill"] == "mock_interview"
    assert "MOCK_INTERVIEW" in state["active_prompt"]

    # 6. Transition to Roadmap via query keyword
    state = transition_skill(state, query="What happens on Day 1 screening and PPDT?")
    assert state["current_skill"] == "roadmap"
    assert "ROADMAP" in state["active_prompt"]

    print("[PASS] LangGraph StateGraph transitions & candidate tracking verified.")


if __name__ == "__main__":
    test_prompt_manager_loading()
    test_langgraph_workflow_transitions()
    print("\nAll modular prompts and LangGraph skill workflow tests PASSED successfully!")
