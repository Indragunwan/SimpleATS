"""Extract plain text from uploaded files (PDF/DOCX/TXT)."""
import io


def extract_text_from_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts).strip()
    except Exception as e:
        return f"[Gagal parsing PDF: {e}]"


def extract_text_from_docx(content: bytes) -> str:
    try:
        from docx import Document

        doc = Document(io.BytesIO(content))
        parts = [p.text for p in doc.paragraphs if p.text]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text:
                        parts.append(cell.text)
        return "\n".join(parts).strip()
    except Exception as e:
        return f"[Gagal parsing DOCX: {e}]"


def extract_text(filename: str, content: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(content)
    if name.endswith(".docx") or name.endswith(".doc"):
        return extract_text_from_docx(content)
    try:
        return content.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""
