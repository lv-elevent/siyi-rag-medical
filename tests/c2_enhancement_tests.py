"""
C2 阶段测试用例
测试多轮理解与检索前查询质量增强
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

from backend.services.agent.medical_agent import MedicalAgent, AgentPrepareResult


class TestC2Enhancement:
    """C2 增强测试"""

    def setup_method(self):
        """每个测试前初始化"""
        self.agent = MedicalAgent()

    @pytest.mark.asyncio
    async def test_1_normal_question(self):
        """测试用例1：普通问答"""
        print("\n=== 测试用例1：普通问答 ===")

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
            mock_rewrite.return_value = "头痛的症状和治疗方式"
            mock_retrieval.return_value = (
                [{"text": "头痛常见原因和治疗方法", "metadata": {"filename": "医疗指南.txt", "chunk_index": 0}}],
                "头痛的症状和治疗方式"  # 使用 rewritten_query 作为 retrieval_query
            )
            mock_format.return_value = ""
            mock_generate.return_value = "头痛可能是由多种原因引起的..."
            mock_safety.return_value = ("头痛可能是由多种原因引起的...", True, [])

            # 调用 prepare
            result = await self.agent.prepare("头痛怎么办")

            # 验证结果
            assert result.status == "ready"
            assert result.query_type == "medical"
            assert result.retrieval_query == "头痛的症状和治疗方式"
            assert len(result.sources) == 1
            assert result.followup_reason is None

            print(f"✅ status: {result.status}")
            print(f"✅ retrieval_query: {result.retrieval_query}")
            print(f"✅ sources: {len(result.sources)}个")

    @pytest.mark.asyncio
    async def test_2_vague_question_without_context(self):
        """测试用例2：无上下文的模糊追问"""
        print("\n=== 测试用例2：无上下文的模糊追问 ===")

        with patch('backend.services.agent.medical_agent.classify_medical_question') as mock_classify, \
             patch('backend.services.agent.medical_agent._is_valid_rag_query') as mock_gate, \
             patch('backend.services.agent.medical_agent._analyze_followup_need') as mock_followup, \
             patch('backend.services.agent.medical_agent._build_contextual_query') as mock_contextual, \
             patch('backend.services.agent.medical_agent.rewrite_medical_question') as mock_rewrite:

            # Mock 返回值
            mock_classify.return_value = "medical"
            mock_gate.return_value = True
            mock_followup.return_value = {
                "needs_followup": True,
                "followup_question": "请说明您具体指的是什么疾病、症状或情况。",
                "reason": "vague_no_context"
            }

            # 调用 prepare
            result = await self.agent.prepare("怎么办")

            # 验证结果
            assert result.status == "followup"
            assert result.followup_question == "请说明您具体指的是什么疾病、症状或情况。"
            assert result.followup_reason == "vague_no_context"
            assert result.retrieval_query == ""  # followup 状态下 retrieval_query 为空

            print(f"✅ status: {result.status}")
            print(f"✅ followup_question: {result.followup_question}")
            print(f"✅ followup_reason: {result.followup_reason}")

    @pytest.mark.asyncio
    async def test_3_followup_with_context(self):
        """测试用例3：有上下文的 followup 问题"""
        print("\n=== 测试用例3：有上下文的 followup 问题 ===")

        # 模拟历史对话
        with patch('backend.services.agent.medical_agent.memory_manager') as mock_memory:
            mock_memory.get_session_history.return_value = [
                {"user_question": "我昨天开始发烧", "assistant_answer": "建议休息观察"},
                {"user_question": "体温38.5度", "assistant_answer": "建议物理降温"}
            ]

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
                mock_contextual.return_value = "我昨天开始发烧。补充问题：这个严重吗"
                mock_rewrite.return_value = "发烧的严重程度判断"
                mock_retrieval.return_value = (
                    [{"text": "体温38.5度的严重程度", "metadata": {"filename": "发热诊疗.txt", "chunk_index": 0}}],
                    "发烧的严重程度判断"
                )
                mock_format.return_value = "用户：我昨天开始发烧\n助手：建议休息观察\n用户：体温38.5度\n助手：建议物理降温"
                mock_generate.return_value = "体温38.5度属于中度发热..."
                mock_safety.return_value = ("体温38.5度属于中度发热...", True, [])

                # 调用 prepare
                result = await self.agent.prepare("这个严重吗", session_id="session001")

                # 验证结果
                assert result.status == "ready"
                assert result.contextual_query == "我昨天开始发烧。补充问题：这个严重吗"
                assert result.history_turns == 2
                assert "我昨天开始发烧" in result.full_context

                print(f"✅ status: {result.status}")
                print(f"✅ contextual_query: {result.contextual_query}")
                print(f"✅ history_turns: {result.history_turns}")

    @pytest.mark.asyncio
    async def test_4_rewrite_failure_fallback_success(self):
        """测试用例4：rewrite 失败但 fallback 成功的场景"""
        print("\n=== 测试用例4：rewrite 失败但 fallback 成功 ===")

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

            # rewrite 返回无效结果
            mock_rewrite.return_value = "invalid query"  # rewrite 后没有匹配结果

            # fallback 返回成功结果
            mock_retrieval.return_value = (
                [{"text": "头痛常见原因和治疗方法", "metadata": {"filename": "医疗指南.txt", "chunk_index": 0}}],
                "头痛怎么办"  # 使用 contextual_query 作为 retrieval_query
            )
            mock_format.return_value = ""
            mock_generate.return_value = "头痛可能是由多种原因引起的..."
            mock_safety.return_value = ("头痛可能是由多种原因引起的...", True, [])

            # 调用 prepare
            result = await self.agent.prepare("头痛怎么办")

            # 验证结果
            assert result.status == "ready"
            assert result.retrieval_query == "头痛怎么办"  # fallback 成功，使用 contextual_query
            assert result.sources[0]["filename"] == "医疗指南.txt"

            print(f"✅ status: {result.status}")
            print(f"✅ rewritten_query: {result.rewritten_query}")
            print(f"✅ retrieval_query: {result.retrieval_query} (fallback 成功)")


class TestEnhancedFollowupAnalysis:
    """增强的 followup 分析测试"""

    def test_vague_question_with_context(self):
        """测试有历史上下文时的模糊问题"""
        agent = MedicalAgent()
        history = [
            {"user_question": "我昨天开始发烧", "assistant_answer": "建议休息观察"}
        ]

        result = agent._analyze_followup_need(
            question="严重吗",
            history=history,
            query_type="medical"
        )

        assert result["needs_followup"] == False
        assert result["reason"] == "none"

    def test_pronoun_with_valid_history(self):
        """测试有有效历史时的指代词"""
        agent = MedicalAgent()
        history = [
            {"user_question": "我最近咳嗽得很厉害", "assistant_answer": "可能是感冒"}
        ]

        result = agent._analyze_followup_need(
            question="会传染吗",
            history=history,
            query_type="medical"
        )

        assert result["needs_followup"] == False
        assert result["reason"] == "none"

    def test_short_vague_question(self):
        """测试简短模糊问题"""
        agent = MedicalAgent()
        result = agent._analyze_followup_need(
            question="怎么办",
            history=[],
            query_type="medical"
        )

        assert result["needs_followup"] == True
        assert result["reason"] == "vague_no_context"
        assert "请说明您具体指的是什么" in result["followup_question"]


class TestContextualQueryBuilding:
    """Contextual query 构建测试"""

    def test_no_history(self):
        """测试无历史情况"""
        agent = MedicalAgent()
        result = agent._build_contextual_query(
            question="头痛怎么办",
            history=[]
        )
        assert result == "头痛怎么办"

    def test_long_valid_history(self):
        """测试有效历史长文本"""
        agent = MedicalAgent()
        history = [
            {"user_question": "我昨天开始发烧，体温38.5度，伴有头痛和喉咙痛", "assistant_answer": "可能是流感"},
            {"user_question": "我吃了退烧药，还是有点头痛", "assistant_answer": "继续观察"}
        ]

        result = agent._build_contextual_query(
            question="这个严重吗",
            history=history
        )

        assert "我昨天开始发烧" in result
        assert "这个严重吗" in result

    def test_short_history_skipped(self):
        """测试跳过过短历史"""
        agent = MedicalAgent()
        history = [
            {"user_question": "严重吗", "assistant_answer": "不好说"},
            {"user_question": "头痛怎么办", "assistant_answer": "先观察"}
        ]

        result = agent._build_contextual_query(
            question="这个严重吗",
            history=history
        )

        # 应该使用最长的有效用户问题
        assert result == "头痛怎么办。补充问题：这个严重吗"


if __name__ == "__main__":
    # 运行测试
    import pytest
    pytest.main([__file__, "-v"])