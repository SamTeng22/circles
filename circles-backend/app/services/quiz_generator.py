import json
import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

def build_context(notes: list[dict]) -> str:
    return "\n\n".join(f"### {n['filename']}\n{n['content']}" for n in notes)

async def generate_quiz_questions(
    notes: list[dict],
    num_questions: int,
) -> list[dict]:
    if not notes:
        return []

    context = build_context(notes)
    prompt = f"""You are a quiz generator. Based on the study notes below, generate {num_questions} multiple choice questions.

Use a mix of Bloom's taxonomy levels:
- Remembering: recall facts
- Understanding: explain concepts
- Applying: use knowledge in a new situation

Language rules:
- Each note below is written in one of: English, Tagalog, or Chinese.
- Write each question (question text, options, correct_answer, explanation) in the SAME language as the note it is drawn from. If a question draws on multiple notes in different languages, use the language of the note it primarily draws from.
- Tag every question with a "language" field using EXACTLY one of these codes: "en" (English), "tl" (Tagalog/Filipino), "zh" (Chinese). Do not use any other code or a language name.
- It is fine and expected for different questions in the same output to use different languages if the source notes differ in language.

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

Study notes:
{context}
"""
    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    questions = json.loads(text)
    for q in questions:
        if q.get("language") not in ("en", "tl", "zh"):
            q["language"] = "en"
    return questions
