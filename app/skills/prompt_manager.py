import os
from functools import lru_cache
from typing import Optional

SKILLS_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


class SSBPromptManager:
    """
    Manages modular SSB prompt loading, caching, and intent-based dynamic assembly for SSB Journey.
    Files stored in app/skills/prompts/:
      - base_mentor.txt: Voice persona, officer-like tone, strict SSB specialization, tool rules
      - onboarding.txt: SSB Journey portal overview, 5-day framework, zero user interrogation
      - roadmap_doubts.txt: 5-Day SSB roadmap (Screening, Psych, GTO, Interview, Conference)
      - checklist.txt: 68-item pre-reporting checklist & reporting requirements
      - mock_interview_olq.txt: 15 Officer Like Qualities (OLQ) breakdown & IO interview parameters
      - motivation.txt: 20 Curated defense quotes & handling demotivation/anxiety
    """

    @staticmethod
    def load_prompt_file(filename: str) -> str:
        filepath = os.path.join(SKILLS_PROMPTS_DIR, filename)
        if not os.path.exists(filepath):
            return ""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()

    @classmethod
    def get_base_mentor(cls) -> str:
        return cls.load_prompt_file("base_mentor.txt")

    @classmethod
    def get_onboarding_rules(cls) -> str:
        return cls.load_prompt_file("onboarding.txt")

    @classmethod
    def get_roadmap_doubts_rules(cls) -> str:
        return cls.load_prompt_file("roadmap_doubts.txt")

    @classmethod
    def get_checklist_rules(cls) -> str:
        return cls.load_prompt_file("checklist.txt")

    @classmethod
    def get_mock_interview_rules(cls) -> str:
        return cls.load_prompt_file("mock_interview_olq.txt")

    @classmethod
    def get_motivation_rules(cls) -> str:
        return cls.load_prompt_file("motivation.txt")

    @classmethod
    def get_unified_mentor_prompt(cls, language: str = "hinglish") -> str:
        """
        Assembles an all-in-one SSB Journey Voice Mentor system prompt.
        Combines base persona + all specialized skill rules.
        """
        parts = [
            cls.get_base_mentor(),
            cls.get_onboarding_rules(),
            cls.get_roadmap_doubts_rules(),
            cls.get_checklist_rules(),
            cls.get_mock_interview_rules(),
            cls.get_motivation_rules(),
        ]
        lang_note = cls._get_language_instruction(language)
        if lang_note:
            parts.append(lang_note)
        return "\n\n".join(filter(None, parts))

    @classmethod
    def get_skill_prompt(cls, skill_name: str, language: str = "hinglish") -> str:
        """
        Returns a focused prompt for a specific skill combined with the base mentor persona.
        Skills: 'onboarding', 'roadmap', 'checklist', 'mock_interview', 'motivation'
        """
        skill_name = skill_name.lower().strip()
        skill_rules = ""

        if skill_name in ["onboarding", "greeting", "profile"]:
            skill_rules = cls.get_onboarding_rules()
        elif skill_name in ["roadmap", "doubts", "stages", "ppdt", "gto", "psych"]:
            skill_rules = cls.get_roadmap_doubts_rules()
        elif skill_name in ["checklist", "documents", "reporting", "items"]:
            skill_rules = cls.get_checklist_rules()
        elif skill_name in ["mock_interview", "olq", "interview", "mock"]:
            skill_rules = cls.get_mock_interview_rules()
        elif skill_name in ["motivation", "quotes", "inspiration", "confidence"]:
            skill_rules = cls.get_motivation_rules()
        else:
            skill_rules = cls.get_roadmap_doubts_rules()

        parts = [
            cls.get_base_mentor(),
            f"--- ACTIVE SKILL FOCUS: {skill_name.upper()} ---\n{skill_rules}",
        ]
        lang_note = cls._get_language_instruction(language)
        if lang_note:
            parts.append(lang_note)

        return "\n\n".join(filter(None, parts))

    @staticmethod
    def _get_language_instruction(language: str) -> str:
        lang = language.lower()
        if lang in ["hi", "hindi"]:
            return "LANGUAGE INSTRUCTION: Please converse primarily in clean, respectful Hindi with an energetic, inspiring cadence."
        elif lang in ["hinglish", "hi-en", "mix"]:
            return "LANGUAGE INSTRUCTION: Speak in natural conversational Hinglish (Hindi + English blend) as spoken by Indian armed forces officers and candidates."
        elif lang in ["en", "english"]:
            return "LANGUAGE INSTRUCTION: Please converse in clear, confident English with natural warmth and positive enthusiasm."
        return ""


prompt_manager = SSBPromptManager()
