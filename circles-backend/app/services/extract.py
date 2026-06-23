import io
import pypdfium2 as pdfium
import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

# If a PDF's text layer yields less than this, treat it as scanned and OCR via Gemini.
MIN_TEXT_LEN = 100
# Cap how many pages we render+OCR, to stay under inline-data/token limits.
MAX_OCR_PAGES = 20
OCR_DPI = 150


def extract_text(data: bytes, content_type: str, filename: str = "") -> str:
    """Turn an uploaded file's bytes into plain text for chunking/embedding."""
    ct = (content_type or "").lower()
    name = (filename or "").lower()

    if ct == "application/pdf" or name.endswith(".pdf"):
        text = _pdf_text_layer(data)
        if len(text.strip()) >= MIN_TEXT_LEN:
            return text
        # No real text layer (scanned/photographed) -> render pages and OCR them.
        return _gemini_ocr(_pdf_pages_as_images(data))

    if ct.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return _gemini_ocr([data], mime=ct or "image/png")

    if ct.startswith("text/") or name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="ignore")

    # Unknown type: best-effort decode rather than hard-fail.
    return data.decode("utf-8", errors="ignore")


def _pdf_text_layer(data: bytes) -> str:
    pdf = pdfium.PdfDocument(data)
    try:
        return "\n".join(page.get_textpage().get_text_range() for page in pdf)
    finally:
        pdf.close()


def _pdf_pages_as_images(data: bytes) -> list[bytes]:
    pdf = pdfium.PdfDocument(data)
    images: list[bytes] = []
    try:
        for i, page in enumerate(pdf):
            if i >= MAX_OCR_PAGES:
                break
            pil = page.render(scale=OCR_DPI / 72).to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            images.append(buf.getvalue())
        return images
    finally:
        pdf.close()


def _gemini_ocr(images: list[bytes], mime: str = "image/png") -> str:
    if not images:
        return ""
    model = genai.GenerativeModel("gemini-2.5-flash")
    parts: list = [
        "Extract all readable text from these document pages. "
        "Output only the extracted text, preserving reading order. Do not add commentary."
    ]
    for img in images:
        parts.append({"mime_type": mime, "data": img})
    resp = model.generate_content(parts)
    return resp.text or ""
