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

_QUESTION_TYPE_LABELS = {
    "multiple_choice": "multiple choice",
    "true_false": "true/false",
    "fill_in_blank": "fill-in-the-blank",
    "matching": "matching",
}

_BLANK_MARKER = "_____"

_TYPE_SHAPE_BLOCKS = {
    "multiple_choice": """Multiple choice questions use "question_type": "multiple_choice":
{
  "question_type": "multiple_choice",
  "question": "...",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "correct_answer": "A. ...",
  "bloom_level": "remembering|understanding|applying",
  "language": "en|tl|zh",
  "explanation": "..."
}""",
    "true_false": """True/false questions use "question_type": "true_false". "question" is a single statement that is either true or false; "correct_answer" is exactly the string "True" or "False":
{
  "question_type": "true_false",
  "question": "...",
  "options": ["True", "False"],
  "correct_answer": "True",
  "bloom_level": "remembering|understanding|applying",
  "language": "en|tl|zh",
  "explanation": "..."
}""",
    "fill_in_blank": f"""Fill-in-the-blank questions use "question_type": "fill_in_blank". Write "question" as a sentence with the key term or phrase removed and replaced by a blank written as EXACTLY five underscores ({_BLANK_MARKER}). List every acceptable phrasing of the answer in "accepted_answers" (include the most natural phrasing first):
{{
  "question_type": "fill_in_blank",
  "question": "The process by which plants convert sunlight into energy is called {_BLANK_MARKER}.",
  "accepted_answers": ["photosynthesis"],
  "correct_answer": "photosynthesis",
  "bloom_level": "remembering|understanding|applying",
  "language": "en|tl|zh",
  "explanation": "..."
}}""",
    "matching": """Matching questions use "question_type": "matching". Provide 3-5 "pairs", each a short term/concept ("left") and its matching definition/description ("right"). Every "left" value and every "right" value must be unique within the question (no repeats), and roughly similar in length so the correct pairing isn't given away:
{
  "question_type": "matching",
  "question": "Match each term to its definition.",
  "pairs": [
    {"left": "...", "right": "..."},
    {"left": "...", "right": "..."},
    {"left": "...", "right": "..."}
  ],
  "bloom_level": "remembering|understanding|applying",
  "language": "en|tl|zh",
  "explanation": "..."
}""",
}

_MC_EXTRA_EXAMPLES = """
Example of a Tagalog-sourced multiple choice question:
{
  "question_type": "multiple_choice",
  "question": "Ano ang kahulugan ng photosynthesis?",
  "options": ["A. Paggawa ng pagkain gamit ang liwanag ng araw", "B. Paghinga ng hangin", "C. Paglaki ng ugat", "D. Paglipat ng tubig"],
  "correct_answer": "A. Paggawa ng pagkain gamit ang liwanag ng araw",
  "bloom_level": "remembering",
  "language": "tl",
  "explanation": "Ang photosynthesis ay ang proseso kung saan gumagawa ng pagkain ang halaman gamit ang liwanag ng araw."
}

Example of a Chinese-sourced multiple choice question:
{
  "question_type": "multiple_choice",
  "question": "光合作用的主要产物是什么?",
  "options": ["A. 葡萄糖和氧气", "B. 二氧化碳", "C. 水", "D. 氮气"],
  "correct_answer": "A. 葡萄糖和氧气",
  "bloom_level": "remembering",
  "language": "zh",
  "explanation": "光合作用利用阳光将二氧化碳和水转化为葡萄糖和氧气。"
}

Example of a math multiple choice question (note the doubled backslashes in the LaTeX):
{
  "question_type": "multiple_choice",
  "question": "Solve $x^2 - 5x + 6 = 0$ for x.",
  "options": ["A. $x = 2, 3$", "B. $x = -2, -3$", "C. $x = 1, 6$", "D. $x = 0, 5$"],
  "correct_answer": "A. $x = 2, 3$",
  "bloom_level": "applying",
  "language": "en",
  "explanation": "Factoring gives $(x - 2)(x - 3) = 0$, so by the quadratic formula $x = \\\\frac{5 \\\\pm \\\\sqrt{25 - 24}}{2} = 2 \\\\text{ or } 3$."
}"""

_OTHER_TYPE_EXAMPLES = {
    "true_false": """
Example of a true/false question:
{
  "question_type": "true_false",
  "question": "Mitochondria are the site of protein synthesis in a cell.",
  "options": ["True", "False"],
  "correct_answer": "False",
  "bloom_level": "understanding",
  "language": "en",
  "explanation": "Protein synthesis happens at ribosomes; mitochondria produce energy (ATP)."
}""",
    "fill_in_blank": f"""
Example of a fill-in-the-blank question:
{{
  "question_type": "fill_in_blank",
  "question": "The powerhouse of the cell is the {_BLANK_MARKER}.",
  "accepted_answers": ["mitochondria", "mitochondrion"],
  "correct_answer": "mitochondria",
  "bloom_level": "remembering",
  "language": "en",
  "explanation": "Mitochondria generate most of the cell's ATP through cellular respiration."
}}""",
    "matching": """
Example of a matching question:
{
  "question_type": "matching",
  "question": "Match each organelle to its function.",
  "pairs": [
    {"left": "Mitochondria", "right": "Produces energy (ATP)"},
    {"left": "Nucleus", "right": "Stores genetic material"},
    {"left": "Ribosome", "right": "Synthesizes proteins"}
  ],
  "bloom_level": "understanding",
  "language": "en",
  "explanation": "Each organelle has a distinct role in the cell."
}""",
}


async def generate_quiz_questions(
    notes: list[dict],
    question_type_counts: dict[str, int],
    difficulty: str = "medium",
) -> list[dict]:
    if not notes:
        return []

    requested_types = [
        (qtype, count)
        for qtype, count in question_type_counts.items()
        if qtype in _TYPE_SHAPE_BLOCKS and count > 0
    ]
    if not requested_types:
        return []

    total = sum(count for _, count in requested_types)
    context = build_context(notes)
    difficulty_instructions = _DIFFICULTY_INSTRUCTIONS.get(difficulty, _DIFFICULTY_INSTRUCTIONS["medium"])

    mix_lines = "\n".join(
        f"- {count} {_QUESTION_TYPE_LABELS[qtype]} question(s)" for qtype, count in requested_types
    )
    shape_blocks = "\n\n".join(_TYPE_SHAPE_BLOCKS[qtype] for qtype, _ in requested_types)
    example_blocks = "".join(
        _MC_EXTRA_EXAMPLES if qtype == "multiple_choice" else _OTHER_TYPE_EXAMPLES[qtype]
        for qtype, _ in requested_types
    )

    prompt = f"""You are a quiz generator. Based on the study notes below, generate exactly {total} questions with this mix, and no other question type:
{mix_lines}

Bloom's taxonomy levels available for the "bloom_level" field:
- Remembering: recall facts
- Understanding: explain concepts
- Applying: use knowledge in a new situation

{difficulty_instructions}

Language rules:
- Each note below is written in one of: English, Tagalog, or Chinese.
- Write each question (question text, options/pairs/accepted answers, correct_answer, explanation) in the SAME language as the note it is drawn from. If a question draws on multiple notes in different languages, use the language of the note it primarily draws from.
- Tag every question with a "language" field using EXACTLY one of these codes: "en" (English), "tl" (Tagalog/Filipino), "zh" (Chinese). Do not use any other code or a language name.
- It is fine and expected for different questions in the same output to use different languages if the source notes differ in language.

Math notation rules:
- The study notes may contain mathematical notation written in LaTeX, delimited by $...$ (inline) or $$...$$ (block), e.g. $x^2 + 3x - 4 = 0$. Interpret this notation correctly when reasoning about the material.
- When your own output involves math (equations, fractions, exponents, derivatives, integrals, variables, Greek letters, etc.), write it using the same convention: $...$ inline, $$...$$ for a standalone equation, using real LaTeX commands (\\frac{{}}{{}}, \\sqrt{{}}, \\int, \\sum, \\partial, \\alpha, ...) rather than Unicode math symbols or plain-text approximations. Prefer inline $...$ in option/answer text; reserve $$...$$ mostly for "explanation" if a derivation needs its own line.
- If a note contains a fully worked math example (a specific equation with its solution), do NOT just repeat that exact problem back as a question. Treat it as a template: write a NEW problem of the same type and difficulty with different numbers, coefficients, or variables, and solve that new problem yourself. Only reuse the note's own numbers for a pure recall question (e.g. "what method solves this form of equation"), not for a "solve for x"-style question.
- CRITICAL for valid JSON: every backslash in a LaTeX command must be written as a doubled backslash so the JSON parses correctly — the string content should look like $\\\\frac{{1}}{{2}}$ so that after JSON parsing it becomes $\\frac{{1}}{{2}}$. Double-check every LaTeX command in your output has doubled backslashes.

Return ONLY a valid JSON array with {total} objects total, no markdown, no extra text. Each object's shape depends on its "question_type", exactly as follows:

{shape_blocks}
{example_blocks}

Study notes:
{context}
"""
    response = model.generate_content(prompt)
    questions = parse_llm_json(response.text)
    for q in questions:
        if q.get("language") not in ("en", "tl", "zh"):
            q["language"] = "en"
        _normalize_question_type(q)
    return questions


def _normalize_question_type(q: dict) -> None:
    qtype = q.get("question_type")
    if qtype not in _TYPE_SHAPE_BLOCKS:
        qtype = "multiple_choice"
    q["question_type"] = qtype

    if qtype == "true_false":
        q["options"] = ["True", "False"]
        answer = q.get("correct_answer")
        if isinstance(answer, bool):
            answer = "True" if answer else "False"
        answer = str(answer).strip().lower()
        q["correct_answer"] = "True" if answer in ("true", "t", "yes") else "False"
    elif qtype == "fill_in_blank":
        if _BLANK_MARKER not in (q.get("question") or ""):
            q["question"] = f"{q.get('question', '')} {_BLANK_MARKER}".strip()
        accepted = q.get("accepted_answers")
        if not accepted:
            fallback = q.get("correct_answer")
            q["accepted_answers"] = [fallback] if fallback else []
        if not q.get("correct_answer") and q.get("accepted_answers"):
            q["correct_answer"] = q["accepted_answers"][0]
