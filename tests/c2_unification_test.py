"""
C2 阶段统一性测试
验证 query_rewriter 输出结构和 medical_agent 的兼容性
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.query_rewriter import rewrite_medical_question
from backend.services.agent.medical_agent import MedicalAgent


def test_query_rewriter_output():
    """测试 query_rewriter 的输出结构"""
    print("\n=== 测试 query_rewriter 输出结构 ===")

    test_cases = [
        ("头疼怎么办", "medical"),
        ("我发烧了", "medical"),
        ("今天天气怎么样", "other"),
        ("什么是高血压", "knowledge"),
        ("", "medical"),
        ("a", "medical"),
        ("心脏病发作了需要马上就医", "medical"),
    ]

    for query, query_type in test_cases:
        result = rewrite_medical_question(query, query_type)

        # 验证输出结构
        assert "original_query" in result
        assert "rewritten_query" in result
        assert "query_type" in result
        assert "rewrite_strategy" in result

        print(f"\n输入: {query} ({query_type})")
        print(f"输出结构: {result}")

        # 验证兼容性
        if query_type == "medical":
            rewritten_query = result["rewritten_query"]
            print(f"改写结果: {query} -> {rewritten_query}")
            print(f"策略: {result['rewrite_strategy']}")


def test_medical_agent_compatibility():
    """测试 medical_agent 的兼容性"""
    print("\n=== 测试 medical_agent 兼容性 ===")

    agent = MedicalAgent()

    # Mock 模拟正常场景
    with patch('backend.services.agent.medical_agent.classify_medical_question') as mock_classify, \
         patch('backend.services.agent.medical_agent._is_valid_rag_query') as mock_gate, \
         patch('backend.services.agent.medical_agent._analyze_followup_need') as mock_followup, \
         patch('backend.services.agent.medical_agent._build_contextual_query') as mock_contextual, \
         patch('backend.services.agent.medical_agent.rewrite_medical_question') as mock_rewrite, \
         patch('backend.services.agent.medical_agent._retrieval_with_fallback') as mock_retrieval, \
         patch('backend.services.agent.medical_agent._format_history') as mock_format, \
         patch('backend.services.agent.medical_agent.generate_answer_with_llm') as mock_generate, \
         patch('backend.services.agent.medical_agent.safety_filter') as mock_safety:

        # Mock 返回值
        mock_classify.return_value = "medical"
        mock_gate.return_value = True
        mock_followup.return_value = {"needs_followup": False, "followup_question": None, "reason": "none"}
        mock_contextual.return_value = "头痛怎么办"

        # 模拟新的输出结构
        mock_rewrite.return_value = {
            "original_query": "头痛怎么办",
            "rewritten_query": "头痛怎么治疗",
            "query_type": "medical",
            "rewrite_strategy": "normal"
        }

        mock_retrieval.return_value = (
            [{"text": "头痛治疗方法", "metadata": {"filename": "医疗指南.txt", "chunk_index": 0}}],
            "头痛怎么治疗"
        )
        mock_format.return_value = ""
        mock_generate.return_value = "头痛的治疗方法包括..."
        mock_safety.return_value = ("头痛的治疗方法包括...", True, [])

        # 调用 prepare
        result = agent.prepare("头痛怎么办")

        print(f"\nprepare 结果:")
        print(f"status: {result.status}")
        print(f"query_type: {result.query_type}")
        print(f"rewritten_query: {result.rewritten_query}")
        print(f"retrieval_query: {result.retrieval_query}")

        # 验证 query_type 透传
        assert result.query_type == "medical"
        assert result.rewritten_query == "头痛怎么治疗"


def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n=== 测试向后兼容性 ===")

    # 测试旧字段命名是否仍然有效
    result = rewrite_medical_question("头疼怎么办", "medical")

    # 检查是否有旧字段（如果有的话）
    old_fields = ['type', 'query_category', 'rewrite_query', 'enhanced_query', 'expanded_query']
    has_old_fields = any(field in result for field in old_fields)

    print(f"是否包含旧字段: {has_old_fields}")

    # 确保 rewritten_query 字段存在
    assert "rewritten_query" in result
    assert result["query_type"] == "medical"


def test_boundary_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")

    boundary_cases = [
        ("", "medical"),  # 空字符串
        ("a", "medical"),  # 过短
        ("头痛", "medical"),  # 已清晰的查询
        ("紧急 心脏病发作了", "medical"),  # 紧急查询
        ("怎么办", "medical"),  # 模糊查询
    ]

    for query, query_type in boundary_cases:
        result = rewrite_medical_question(query, query_type)

        print(f"\n边界测试: {query}")
        print(f"策略: {result['rewrite_strategy']}")
        print(f"rewritten_query: {result['rewritten_query']}")

        # 验证边界处理
        if query in ["", "a"]:
            # 空或过短应该标记为 invalid
            assert result['rewrite_strategy'] == 'invalid' or result['rewrite_strategy'] == 'none'

        if query == "头痛":
            # 已清晰的查询应该保持不变或轻度改写
            assert result['rewrite_strategy'] in ['none', 'normal']


if __name__ == "__main__":
    import patch
    from unittest.mock import patch

    test_query_rewriter_output()
    test_medical_agent_compatibility()
    test_backward_compatibility()
    test_boundary_cases()

    print("\n✅ 所有测试通过！")