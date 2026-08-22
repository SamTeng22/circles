import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# A backslash that isn't part of a valid JSON escape. Gemini reliably
# produces LaTeX like "\frac{1}{2}" in generated question/answer text, which
# is invalid inside a JSON string (it must be "\\frac{1}{2}").
#
# This can't be a simple "not one of \" \\ \/ \b \f \n \r \t \u" blacklist:
# several common LaTeX command names start with a letter that IS a valid
# single-character JSON escape (\frac, \beta, \theta, \tan, \nu, ...), and
# json.loads happily parses e.g. "\frac" as a formfeed followed by the
# literal text "rac" *without raising* - silently corrupting the LaTeX
# instead of failing loudly. So a lone \b/\f/\n/\r/\t only counts as a
# genuine (good) escape when it is NOT immediately followed by more letters;
# followed by letters, it's treated as the start of an unescaped LaTeX
# command and gets doubled. A leading (?<!\\) skips the second backslash of
# an already-correct "\\frac" pair so well-formed input is left alone.
_BAD_BACKSLASH_RE = re.compile(
    r'(?<!\\)\\(?!["\\/]|[bfnrt](?![a-zA-Z])|u[0-9a-fA-F]{4})'
)


def strip_code_fence(text: str) -> str:
    """Gemini often wraps JSON in a ```json ... ``` fence; unwrap it."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def repair_json_backslashes(text: str) -> str:
    return _BAD_BACKSLASH_RE.sub(r"\\\\", text)


def parse_llm_json(text: str) -> Any:
    """Parse an LLM response as JSON, tolerating a code fence and unescaped
    LaTeX backslashes in string values.

    Repair is applied whenever it would actually change the text (i.e. a
    suspect backslash was found), not just as a fallback after a parse
    failure - some bad backslashes (see _BAD_BACKSLASH_RE) parse "successfully"
    into the wrong string rather than raising.
    """
    cleaned = strip_code_fence(text)
    repaired = repair_json_backslashes(cleaned)
    if repaired == cleaned:
        return json.loads(cleaned)

    try:
        result = json.loads(repaired)
    except json.JSONDecodeError:
        return json.loads(cleaned)
    logger.warning("LLM JSON required backslash repair before it would parse correctly")
    return result
