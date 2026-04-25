import logging
import os
import re
import importlib
from collections import Counter

import fitz  # PyMuPDF

# docx 可选依赖（使用延迟导入，避免静态检查报 missing import）
HAS_DOCX = importlib.util.find_spec("docx") is not None

logger = logging.getLogger(__name__)


HEADING_PREFIX_RE = re.compile(
    r"^\s*(第[一二三四五六七八九十百千万0-9]+[章节部分]|[0-9]+[.\)]|[一二三四五六七八九十]+[、.]|[-*•])"
)
SENTENCE_END_RE = re.compile(r"[。！？；.!?;:：]$")
GARBLED_CHAR_RE = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9\s.,;:!?，。；：！？()\[\]{}\-_/+%#*&@']")



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
        page_lines: list[list[str]] = []
        page_headers: list[str] = []
        page_footers: list[str] = []

        for page in doc:
            page_text = page.get_text("text")
            if not page_text:
                continue

            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            if not lines:
                continue

            page_lines.append(lines)
            page_headers.append(lines[0])
            page_footers.append(lines[-1])

        doc.close()

        headers_to_remove = _detect_repeated_page_markers(page_headers)
        footers_to_remove = _detect_repeated_page_markers(page_footers)
        header_footer_detected = bool(headers_to_remove or footers_to_remove)

        flattened_lines: list[str] = []
        removed_markers = 0
        for lines in page_lines:
            for idx, line in enumerate(lines):
                is_header = idx == 0 and line in headers_to_remove
                is_footer = idx == len(lines) - 1 and line in footers_to_remove
                if is_header or is_footer:
                    removed_markers += 1
                    continue
                flattened_lines.append(line)
            flattened_lines.append("")

        raw_text = "\n".join(flattened_lines)
        return _clean_text(
            raw_text,
            header_footer_detected=header_footer_detected,
            removed_markers=removed_markers,
        )

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
        docx_module = importlib.import_module("docx")
        doc = docx_module.Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return _clean_text(text)
    except Exception as exc:
        raise RuntimeError(f"DOCX 解析失败: {str(exc)}") from exc


# =========================
# 清洗
# =========================
def _detect_repeated_page_markers(markers: list[str]) -> set[str]:
    if len(markers) < 3:
        return set()

    normalized = [
        _normalize_inline_spaces(item)
        for item in markers
        if item and _looks_like_marker_candidate(item)
    ]
    if not normalized:
        return set()

    counts = Counter(normalized)
    threshold = max(3, int(len(markers) * 0.6))
    return {text for text, count in counts.items() if count >= threshold}


def _looks_like_marker_candidate(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 80:
        return False
    if re.fullmatch(r"[\d\s/\\\-_.]+", stripped):
        return True
    return len(stripped) >= 4


def _normalize_inline_spaces(text: str) -> str:
    # 空白与常见隐形字符归一
    text = (text or "")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 常见项目符号统一，减少模型“乱码感”
    text = re.sub(r"[•·●▪]", "- ", text)

    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _is_heading_or_item_line(text: str) -> bool:
    return bool(HEADING_PREFIX_RE.match((text or "").strip()))


def _should_merge_lines(prev_line: str, current_line: str) -> bool:
    if not prev_line or not current_line:
        return False
    if _is_heading_or_item_line(current_line):
        return False
    if SENTENCE_END_RE.search(prev_line):
        return False
    if len(prev_line) >= 120:
        return False
    return True


def _is_short_noise_paragraph(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    if _is_heading_or_item_line(stripped):
        return False
    if len(stripped) <= 2 and not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", stripped):
        return True
    if len(stripped) <= 4 and re.fullmatch(r"[^\u4e00-\u9fffA-Za-z0-9]+", stripped):
        return True
    return False


def _is_garbled_paragraph(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True

    # replacement char 直接判定为脏段
    if "�" in stripped:
        return True

    # 异常字符比例判定（保守）
    abnormal = len(GARBLED_CHAR_RE.findall(stripped))
    abnormal_ratio = abnormal / max(len(stripped), 1)

    # 短文本放宽，长文本收紧
    if len(stripped) >= 20 and abnormal_ratio > 0.25:
        return True
    if len(stripped) >= 60 and abnormal_ratio > 0.18:
        return True

    return False


def _clean_text(
    raw_text: str,
    header_footer_detected: bool = False,
    removed_markers: int = 0,
) -> str:
    before_len = len(raw_text or "")
    normalized_lines: list[str] = []
    for raw_line in (raw_text or "").splitlines():
        line = _normalize_inline_spaces(raw_line)
        # 行级兜底：去替代字符
        line = line.replace("�", "")
        normalized_lines.append(line)

    paragraphs: list[str] = []
    current_lines: list[str] = []
    removed_paragraphs = 0

    def flush_current() -> None:
        nonlocal removed_paragraphs
        if not current_lines:
            return
        paragraph = "\n".join(current_lines).strip()
        current_lines.clear()
        if _is_short_noise_paragraph(paragraph) or _is_garbled_paragraph(paragraph):
            removed_paragraphs += 1
            return
        paragraphs.append(paragraph)

    for line in normalized_lines:
        if not line:
            flush_current()
            continue

        if not current_lines:
            current_lines.append(line)
            continue

        prev = current_lines[-1]
        if _should_merge_lines(prev, line):
            current_lines[-1] = f"{prev} {line}".strip()
        else:
            current_lines.append(line)

    flush_current()

    cleaned_text = "\n\n".join(paragraphs).strip()
    # 末尾再做一次轻量规整
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)

    logger.info(
        "[document_parser.clean] before_len=%s after_len=%s removed_paragraphs=%s repeated_header_footer=%s removed_markers=%s",
        before_len,
        len(cleaned_text),
        removed_paragraphs,
        header_footer_detected,
        removed_markers,
    )
    return cleaned_text