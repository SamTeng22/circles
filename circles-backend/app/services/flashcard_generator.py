import google.generativeai as genai
from app.core.config import settings
# Reuse the same context-building helper the quiz generator uses so flashcards
# are grounded in the same selected notes format.
from app.services.quiz_generator import build_context
from app.services.json_utils import parse_llm_json

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")


async def generate_flashcards(
    notes: list[dict],
    num_cards: int,
) -> list[dict]:
    if not notes:
        return []

    context = build_context(notes)
    prompt = f"""You are a flashcard generator for students. Based on the study notes below, generate {num_cards} flashcards.

Each flashcard has a short prompt on the front and a concise, self-contained answer on the back. Favor one idea per card: key terms, definitions, cause/effect, and important facts. Keep fronts under ~15 words and backs under ~40 words.

Language rules:
- Each note below is written in one of: English, Tagalog, or Chinese.
- Write each flashcard (front, back, hint) in the SAME language as the note it is drawn from.
- Tag every flashcard with a "language" field using EXACTLY one of these codes: "en" (English), "tl" (Tagalog/Filipino), "zh" (Chinese). Do not use any other code or a language name.
- It is fine and expected for different flashcards in the same output to use different languages if the source notes differ in language.

Math notation rules:
- The study notes may contain mathematical notation written in LaTeX, delimited by $...$ (inline) or $$...$$ (block), e.g. $x^2 + 3x - 4 = 0$. Interpret this notation correctly when reasoning about the material.
- When your own output involves math (equations, fractions, exponents, derivatives, integrals, variables, Greek letters, etc.), write it using the same convention: $...$ inline, $$...$$ for a standalone equation, using real LaTeX commands (\\frac{{}}{{}}, \\sqrt{{}}, \\int, \\sum, \\partial, \\alpha, ...) rather than Unicode math symbols or plain-text approximations.
- If a note contains a fully worked math example (a specific equation with its solution), do NOT just repeat that exact problem back on the card. Treat it as a template: write a NEW problem of the same type and difficulty with different numbers, coefficients, or variables, and solve that new problem yourself for "back". Only reuse the note's own numbers for a pure recall card (e.g. "what method solves this form of equation"), not for a "solve for x"-style card.
- CRITICAL for valid JSON: every backslash in a LaTeX command must be written as a doubled backslash so the JSON parses correctly — the string content should look like $\\\\frac{{1}}{{2}}$ so that after JSON parsing it becomes $\\frac{{1}}{{2}}$. Double-check every LaTeX command in your output has doubled backslashes.

Return ONLY a valid JSON array with this exact format, no markdown, no extra text:
[
  {{
    "front": "...",
    "back": "...",
    "hint": "...",
    "language": "en|tl|zh"
  }}
]

The "hint" is optional context (leave as an empty string if not useful).

Example of a math flashcard (note the doubled backslashes in the LaTeX):
{{
  "front": "What is the derivative of $x^3$?",
  "back": "$\\\\frac{{d}}{{dx}} x^3 = 3x^2$",
  "hint": "Use the power rule.",
  "language": "en"
}}

Study notes:
{context}
"""
    response = model.generate_content(prompt)
    cards = parse_llm_json(response.text)
    for c in cards:
        if c.get("language") not in ("en", "tl", "zh"):
            c["language"] = "en"
    return cards
