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

Return ONLY a valid JSON array with this exact format, no markdown, no extra text:
[
  {{
    "question": "...",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "correct_answer": "A. ...",
    "bloom_level": "remembering|understanding|applying",
    "explanation": "..."
  }}
]

Study notes:
{context}
"""
    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
