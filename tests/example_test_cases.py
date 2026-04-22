"""
C1 阶段测试用例示例
测试 Agent 统一前处理逻辑
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.agent.medical_agent import MedicalAgent
import asyncio
from unittest.mock import patch


async def test_normal_case():
    """测试用例1：普通医疗问答"""
    print("\n=== 测试用例1：普通医疗问答 ===")

    agent = MedicalAgent()

    # 模拟调用
    result = await agent.prepare(
        question="头痛怎么办",
        document_id="doc123",
        session_id="session001"
    )

    # 预期结果
    assert result.status == "ready"
    assert result.query_type == "medical"
    assert len(result.sources) > 0
    assert result.rewritten_query != result.question  # query rewrite 已执行

    print(f"状态: {result.status}")
    print(f"问题类型: {result.query_type}")
    print(f"原始问题: {result.question}")
    print(f"改写后问题: {result.rewritten_query}")
    print(f"来源数量: {len(result.sources)}")


async def test_multi_turn_case():
    """测试用例2：多轮对话（带历史）"""
    print("\n=== 测试用例2：多轮对话 ===")

    agent = MedicalAgent()

    # 模拟已存在历史对话
    with patch('backend.services.agent.medical_agent.memory_manager') as mock_memory:
        mock_memory.get_session_history.return_value = [
            {"user_question": "我昨天开始发烧", "assistant_answer": "建议休息观察"}
        ]
        mock_memory.get_turn_count.return_value = 1

        # 基于上下文的提问
        result = await agent.prepare(
            question="这个严重吗",
            session_id="session001"
        )

        # 预期结果
        assert result.status == "ready"
        assert "这个" in result.contextual_query  # contextual query 补全
        assert result.history_turns == 1

        print(f"状态: {result.status}")
        print(f"上下文补全后: {result.contextual_query}")
        print(f"历史轮数: {result.history_turns}")


async def test_followup_case():
    """测试用例3：需要追问的情况"""
    print("\n=== 测试用例3：需要追问 ===")

    agent = MedicalAgent()

    # 模糊提问
    result = await agent.prepare(
        question="怎么办",
        session_id="session001"
    )

    # 预期结果
    assert result.status == "followup"
    assert result.followup_question is not None

    print(f"状态: {result.status}")
    print(f"追问问题: {result.followup_question}")


async def main():
    """运行测试用例"""
    await test_normal_case()
    await test_multi_turn_case()
    await test_followup_case()


if __name__ == "__main__":
    asyncio.run(main())