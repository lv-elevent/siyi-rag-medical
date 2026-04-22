from typing import List, Dict

# 分块参数配置
CHUNK_SIZE = 600
OVERLAP = 80


def split_text_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP
) -> List[Dict[str, str | int]]:
    """将文本按段落和句子切分为带重叠的 chunk 列表。"""
    if not text or not text.strip():
        return []

    # 分块参数安全检查
    overlap = max(1, min(overlap, chunk_size // 3))

    # 1. 先按段落和句子切分
    paragraphs = text.split('\n\n')
    blocks = []
    current = ""

    for para in paragraphs:
        lines = para.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if len(line) < 30:
                current += " " + line
            else:
                if current:
                    blocks.append(current)
                    current = line
                else:
                    current = line
    if current:
        blocks.append(current)

    # 2. 合并块到指定大小
    chunks = []
    index = 0
    start = 0
    total_blocks = len(blocks)
    safety_counter = 0
    MAX_CYCLES = total_blocks * 2

    while start < total_blocks and safety_counter < MAX_CYCLES:
        safety_counter += 1

        # 计算当前 chunk 的结束位置
        end = start
        current_size = 0

        while end < total_blocks:
            size = current_size + len(blocks[end])
            if size <= chunk_size:
                current_size = size
                end += 1
            else:
                break

        # 生成 chunk
        chunk_text = " ".join(blocks[start:end])
        if chunk_text.strip():
            chunks.append({"index": index, "text": chunk_text.strip()})
            index += 1

        # 更新 start：确保至少前进，保持 overlap
        if end >= total_blocks:
            break

        # 计算 start 的新位置（保持 overlap）
        new_start = end - overlap
        if new_start <= start:
            new_start = end

        new_start = max(0, min(new_start, end))
        start = new_start

    return chunks