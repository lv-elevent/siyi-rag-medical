import os
import fitz  # PyMuPDF

# docx 可选依赖
try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


def parse_document(file_path: str) -> str:
    """
    统一文档解析入口（支持 PDF / TXT / MD / DOCX）
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _parse_pdf(file_path)

    elif ext in [".txt", ".md"]:
        return _parse_text(file_path)

    elif ext == ".docx":
        return _parse_docx(file_path)

    else:
        raise ValueError(f"不支持的文件类型: {ext}")


# =========================
# PDF
# =========================
def _parse_pdf(file_path: str) -> str:
    try:
        doc = fitz.open(file_path)
        text_parts = []

        for page in doc:
            page_text = page.get_text("text")
            if page_text:
                text_parts.append(page_text)

        doc.close()

        return _clean_text("\n".join(text_parts))

    except Exception as exc:
        raise RuntimeError(f"PDF 解析失败: {str(exc)}") from exc


# =========================
# TXT / MD
# =========================
def _parse_text(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return _clean_text(f.read())
    except Exception as exc:
        raise RuntimeError(f"文本解析失败: {str(exc)}") from exc


# =========================
# DOCX
# =========================
def _parse_docx(file_path: str) -> str:
    if not HAS_DOCX:
        raise RuntimeError("未安装 python-docx，请执行 pip install python-docx")

    try:
        doc = Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return _clean_text(text)
    except Exception as exc:
        raise RuntimeError(f"DOCX 解析失败: {str(exc)}") from exc


# =========================
# 清洗
# =========================
def _clean_text(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return "\n".join(lines)