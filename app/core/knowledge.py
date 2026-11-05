"""
SSB Journey Domain Knowledge & Voice Persona System Prompt.
Charismatic, lively, human, and captivating tone for defense aspirants.
Specialized exclusively for Services Selection Board (SSB) selection details.
"""

from app.skills.prompt_manager import prompt_manager

GREETING_TRIGGER = (
    'Speak immediately in a lively, charismatic, inspiring, and natural conversational tone! '
    'Say: "Jai Hind future officers! Welcome to Mission SSB! '
    'Main hoon aapka dedicated AI mentor, exclusively specialized for Services Selection Board (SSB). '
    'Hamare is portal par aapko milta hai complete five-day SSB roadmap — Day 1 Screening aur PPDT se lekar Psychology tests, GTO tasks, Personal Interview aur Board Conference tak. '
    'Saath hi reporting day ki 68 essential items ki complete Pre-Reporting Checklist aur 15 Officer Like Qualities ki detailed breakdown taaki aapki preparation 100% solid ho. '
    'Apni preparation start karne ke liye upar diye gaye Login ya Start Free button par click kijiye aur apna free account banakar aaj hi apni recommendation practice shuru kijiye. '
    'To chaliye shuru karte hain aapki recommendation ki Mission SSB Journey!" '
    'Speak with genuine soldierly warmth, high energy, and a natural confident cadence. '
    'Do not rush, but do not drag. Sound engaging, authoritative, and full of life from the very first second!'
)

# Unified mentor prompt combining base persona and all SSB Journey skills
SYSTEM_PROMPT = prompt_manager.get_unified_mentor_prompt(language="hinglish")
