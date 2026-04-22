"""
测试 Agent 前处理逻辑
验证 prepare 方法的各种场景
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from backend.services.agent.medical_agent import MedicalAgent, AgentPrepareResult


class TestMedicalAgentPrepare:
    """MedicalAgent prepare 方法测试"""

    def setup_method(self):
        """每个测试前初始化"""
        self.agent = MedicalAgent()

    @pytest.mark.asyncio
    async def test_empty_question(self):
        """测试问题为空的情况"""
        result = self.agent.prepare("")

        assert result.status == "error"
        assert result.error_message == "问题不能为空"
        assert result.question == ""

    @pytest.mark.asyncio
    async def test_normal_question(self):
        """测试普通问题场景"""
        with patch('backend.services.agent.medical_agent.classify_medical_question') as mock_classify, \
             patch('backend.services.agent.medical_agent._is_valid_rag_query') as mock_gate, \
             patch('backend.services.agent.medical_agent._check_followup_needed') as mock_followup, \
             patch('backend.services.agent.medical_agent._build_contextual_query') as mock_contextual, \
             patch('backend.services.agent.medical_agent.rewrite_medical_question') as mock_rewrite, \
             patch('backend.services.agent.medical_agent.semantic_search') as mock_search, \
             patch('backend.services.agent.medical_agent._format_history') as mock_format:

            # Mock 返回值
            mock_classify.return_value = "medical"
            mock_gate.return_value = True
            mock_followup.return_value = (False, None)
            mock_contextual.return_value = "改写的问题"
            mock_rewrite.return_value = "重写后的查询"
            mock_search.return_value = [
                {"text": "文档内容1", "metadata": {"filename": "test1.txt", "chunk_index": 0}},
                {"text": "文档内容2", "metadata": {"filename": "test2.txt", "chunk_index": 1}}
            ]
            mock_format.return_value = "格式化的历史"

            # 调用 prepare
            result = self.agent.prepare("头痛怎么办")

            # 验证结果
            assert result.status == "ready"
            assert result.question == "头痛怎么办"
            assert result.query_type == "medical"
            assert result.contextual_query == "改写的问题"
            assert result.rewritten_query == "重写后的查询"
            assert len(result.sources) == 2
            assert result.history_turns == 0

    @pytest.mark.asyncio
    async def test_followup_question(self):
        """测试需要追问的情况"""
        with patch('backend.services.agent.medical_agent.classify_medical_question') as mock_classify, \
             patch('backend.services.agent.medical_agent._is_valid_rag_query') as mock_gate, \
             patch('backend.services.agent.medical_agent._check_followup_needed') as mock_followup:

            mock_classify.return_value = "medical"
            mock_gate.return_value = True
            mock_followup.return_value = (True, "请说明您具体指的是什么疾病、症状或情况。")

            result = self.agent.prepare("怎么办")

            assert result.status == "followup"
            assert result.followup_question == "请说明您具体指的是什么疾病、症状或情况。"
            assert result.question == "怎么办"

    @pytest.mark.asyncio
    async def test_empty_knowledge_base(self):
        """测试知识库无相关内容的情况"""
        with patch('backend.services.agent.medical_agent.classify_medical_question') as mock_classify, \
             patch('backend.services.agent.medical_agent._is_valid_rag_query') as mock_gate, \
             patch('backend.services.agent.medical_agent._check_followup_needed') as mock_followup, \
             patch('backend.services.agent.medical_agent.rewrite_medical_question') as mock_rewrite, \
             patch('backend.services.agent.medical_agent.semantic_search') as mock_search:

            mock_classify.return_value = "medical"
            mock_gate.return_value = True
            mock_followup.return_value = (False, None)
            mock_rewrite.return_value = "重写后的查询"
            mock_search.return_value = []  # 检索结果为空

            result = self.agent.prepare("奇怪的症状")

            assert result.status == "empty"
            assert result.error_message == "知识库未收录相关内容。"

    @pytest.mark.asyncio
    async def test_with_history(self):
        """测试带历史对话的情况"""
        with patch('backend.services.agent.medical_agent.classify_medical_question') as mock_classify, \
             patch('backend.services.agent.medical_agent._is_valid_rag_query') as mock_gate, \
             patch('backend.services.agent.medical_agent._check_followup_needed') as mock_followup, \
             patch('backend.services.agent.medical_agent._build_contextual_query') as mock_contextual, \
             patch('backend.services.agent.medical_agent.rewrite_medical_question') as mock_rewrite, \
             patch('backend.services.agent.medical_agent.semantic_search') as mock_search, \
             patch('backend.services.agent.medical_agent._format_history') as mock_format:

            mock_classify.return_value = "medical"
            mock_gate.return_value = True
            mock_followup.return_value = (False, None)
            mock_contextual.return_value = "改写的问题"
            mock_rewrite.return_value = "重写后的查询"
            mock_search.return_value = [
                {"text": "文档内容", "metadata": {"filename": "test.txt", "chunk_index": 0}}
            ]
            mock_format.return_value = "格式化的历史"

            # Mock 历史对话
            with patch('backend.services.agent.medical_agent.memory_manager') as mock_memory:
                mock_memory.get_session_history.return_value = [
                    {"user_question": "之前的问题", "assistant_answer": "之前的回答"}
                ]
                mock_memory.get_turn_count.return_value = 1

                result = self.agent.prepare("继续讨论", session_id="test_session")

                assert result.history_turns == 1
                assert "历史对话" in result.full_context


if __name__ == "__main__":
    # 运行简单测试
    import pytest
    pytest.main([__file__, "-v"])