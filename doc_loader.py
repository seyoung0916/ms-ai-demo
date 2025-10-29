# ms-ai-demo/doc_loader.py
from typing import BinaryIO
from pypdf import PdfReader
from docx import Document


def load_text_from_file(file: BinaryIO, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(file)
        pages = []
        for p in reader.pages:
            pages.append(p.extract_text() or "")
        return "\n".join(pages).strip()
    elif name.endswith(".docx"):
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs]).strip()
    elif name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")
    else:
        raise ValueError("지원하지 않는 파일 형식입니다. (pdf, docx, txt만)")
