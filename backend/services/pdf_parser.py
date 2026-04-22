import fitz


def extract_text_from_pdf(file_path: str) -> str:
    """从 PDF 中提取纯文本，并去掉空行。"""
    try:
        doc = fitz.open(file_path)
        text_parts: list[str] = []

        for page in doc:
            page_text = page.get_text("text")
            if page_text:
                text_parts.append(page_text)

        doc.close()

        raw_text = "\n".join(text_parts)
        cleaned_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        return "\n".join(cleaned_lines)

    except Exception as exc:
        raise RuntimeError(f"PDF 解析失败: {str(exc)}") from exc