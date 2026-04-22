# -*- coding: utf-8 -*-
"""测试服务和调用"""
import os
import sys
from dotenv import load_dotenv
from backend.core.embedding_client import embed_text
from backend.core.llm_client import generate_answer_with_llm
from backend.services.retrieval_service import semantic_search

# 设置输出编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

print("=== 测试 1: Embeddings 生成 ===")
try:
    test_text = "这是一个测试文本，用于验证 embeddings 生成是否正常。"
    embedding = embed_text(test_text)
    print(f"✓ Embeddings 生成成功，维度: {len(embedding)}")
except Exception as e:
    print(f"✗ Embeddings 生成失败: {e}")

print("\n=== 测试 2: LLM 调用 ===")
try:
    test_question = "请问你的名字是什么？"
    test_context = "你的名字是 Claude，是一个 AI 助手。"
    answer = generate_answer_with_llm(test_question, test_context)
    print(f"✓ LLM 调用成功")
    print(f"  问题: {test_question}")
    print(f"  答案: {answer}")
except Exception as e:
    print(f"✗ LLM 调用失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试 3: 向量检索 ===")
try:
    test_question = "用户的名字是什么？"
    results = semantic_search(test_question, top_k=3)
    print(f"✓ 向量检索成功")
    print(f"  问题: {test_question}")
    print(f"  命中 chunk 数量: {len(results)}")
    if results:
        for i, item in enumerate(results[:2], 1):
            print(f"  Chunk {i}: {item['text'][:50]}...")
except Exception as e:
    print(f"✗ 向量检索失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 所有测试完成 ===")
