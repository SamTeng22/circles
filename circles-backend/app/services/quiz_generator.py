import google.generativeai as genai
from app.core.config import settings
from app.services.json_utils import parse_llm_json

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

def build_context(notes: list[dict]) -> str:
    return "\n\n".join(f"### {n['filename']}\n{n['content']}" for n in notes)


_DIFFICULTY_INSTRUCTIONS = {
    "easy": (
        "Difficulty: EASY. Favor \"remembering\" questions, with a few \"understanding\" - direct recall "
        "of facts/definitions and straightforward explanations, minimal \"applying\". If a question "
        "involves math, keep it single-step with small, clean numbers (e.g. small whole numbers)."
    ),
    "medium": (
        "Difficulty: MEDIUM. Use a mix of \"remembering\", \"understanding\", and \"applying\" questions. "
        "If a question involves math, it can require a couple of steps and moderately-sized numbers."
    ),
    "hard": (
        "Difficulty: HARD. Favor \"understanding\" and \"applying\" questions that require real "
        "reasoning, not just recall - minimal \"remembering\". If a question involves math, it should "
        "require multiple steps (e.g. simplifying before solving, combining two concepts) and use "
        "numbers that don't reduce trivially (fractions, negatives, larger coefficients)."
    ),
}


async def generate_quiz_questions(
    notes: list[dict],
    num_questions: int,
    difficulty: str = "medium",
) -> list[dict]:
    if not notes:
        return []

    context = build_context(notes)
    difficulty_instructions = _DIFFICULTY_INSTRUCTIONS.get(difficulty, _DIFFICULTY_INSTRUCTIONS["medium"])
    prompt = f"""You are a quiz generator. Based on the study notes below, generate {num_questions} multiple choice questions.

Bloom's taxonomy levels available for the "bloom_level" field:
- Remembering: recall facts
- Understanding: explain concepts
- Applying: use knowledge in a new situation

{difficulty_instructions}

Language rules:
- Each note below is written in one of: English, Tagalog, or Chinese.
- Write each question (question text, options, correct_answer, explanation) in the SAME language as the note it is drawn from. If a question draws on multiple notes in different languages, use the language of the note it primarily draws from.
- Tag every question with a "language" field using EXACTLY one of these codes: "en" (English), "tl" (Tagalog/Filipino), "zh" (Chinese). Do not use any other code or a language name.
- It is fine and expected for different questions in the same output to use different languages if the source notes differ in language.

Math notation rules:
- The study notes may contain mathematical notation written in LaTeX, delimited by $...$ (inline) or $$...$$ (block), e.g. $x^2 + 3x - 4 = 0$. Interpret this notation correctly when reasoning about the material.
- When your own output involves math (equations, fractions, exponents, derivatives, integrals, variables, Greek letters, etc.), write it using the same convention: $...$ inline, $$...$$ for a standalone equation, using real LaTeX commands (\\frac{{}}{{}}, \\sqrt{{}}, \\int, \\sum, \\partial, \\alpha, ...) rather than Unicode math symbols or plain-text approximations. Prefer inline $...$ in "options" and "correct_answer"; reserve $$...$$ mostly for "explanation" if a derivation needs its own line.
- If a note contains a fully worked math example (a specific equation with its solution), do NOT just repeat that exact problem back as a question. Treat it as a template: write a NEW problem of the same type and difficulty with different numbers, coefficients, or variables, and solve that new problem yourself for "correct_answer"/"explanation". Only reuse the note's own numbers for a pure recall question (e.g. "what method solves this form of equation"), not for a "solve for x"-style question.
- CRITICAL for valid JSON: every backslash in a LaTeX command must be written as a doubled backslash so the JSON parses correctly — the string content should look like $\\\\frac{{1}}{{2}}$ so that after JSON parsing it becomes $\\frac{{1}}{{2}}$. Double-check every LaTeX command in your output has doubled backslashes.

Return ONLY a valid JSON array with this exact format, no markdown, no extra text:
[
  {{
    "question": "...",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "correct_answer": "A. ...",
    "bloom_level": "remembering|understanding|applying",
    "language": "en|tl|zh",
    "explanation": "..."
  }}
]

Example of a Tagalog-sourced question:
{{
  "question": "Ano ang kahulugan ng photosynthesis?",
  "options": ["A. Paggawa ng pagkain gamit ang liwanag ng araw", "B. Paghinga ng hangin", "C. Paglaki ng ugat", "D. Paglipat ng tubig"],
  "correct_answer": "A. Paggawa ng pagkain gamit ang liwanag ng araw",
  "bloom_level": "remembering",
  "language": "tl",
  "explanation": "Ang photosynthesis ay ang proseso kung saan gumagawa ng pagkain ang halaman gamit ang liwanag ng araw."
}}

Example of a Chinese-sourced question:
{{
  "question": "光合作用的主要产物是什么?",
  "options": ["A. 葡萄糖和氧气", "B. 二氧化碳", "C. 水", "D. 氮气"],
  "correct_answer": "A. 葡萄糖和氧气",
  "bloom_level": "remembering",
  "language": "zh",
  "explanation": "光合作用利用阳光将二氧化碳和水转化为葡萄糖和氧气。"
}}

Example of a math question (note the doubled backslashes in the LaTeX):
{{
  "question": "Solve $x^2 - 5x + 6 = 0$ for x.",
  "options": ["A. $x = 2, 3$", "B. $x = -2, -3$", "C. $x = 1, 6$", "D. $x = 0, 5$"],
  "correct_answer": "A. $x = 2, 3$",
  "bloom_level": "applying",
  "language": "en",
  "explanation": "Factoring gives $(x - 2)(x - 3) = 0$, so by the quadratic formula $x = \\\\frac{{5 \\\\pm \\\\sqrt{{25 - 24}}}}{{2}} = 2 \\\\text{{ or }} 3$."
}}

Study notes:
{context}
"""
    response = model.generate_content(prompt)
    questions = parse_llm_json(response.text)
    for q in questions:
        if q.get("language") not in ("en", "tl", "zh"):
            q["language"] = "en"
    return questions
