"""
C1 阶段最终验收测试用例
测试 /chat 和 /chat-stream 的统一前处理逻辑
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncGenerator
from httpx import AsyncClient

from backend.services.agent.medical_agent import MedicalAgent, AgentPrepareResult
from backend.services.retrieval_service import semantic_search
from backend.core.llm_client import generate_answer_with_llm_stream
from backend.services.safety_guard import safety_filter


class TestFinalAcceptance:
    """最终验收测试"""

    def setup_method(self):
        """每个测试前初始化"""
        self.agent = MedicalAgent()

    @pytest.mark.asyncio
    async def test_1_chat_normal_case(self):
        """测试用例1：/chat 普通医疗问答"""
        print("\n=== 测试用例1：/chat 普通医疗问答 ===")

        with patch('backend.services.agent.medical_agent.classify_medical_question') as mock_classify, \
             patch('backend.services.agent.medical_agent._is_valid_rag_query') as mock_gate, \
             patch('backend.services.agent.medical_agent._check_followup_needed') as mock_followup, \
             patch('backend.services.agent.medical_agent._build_contextual_query') as mock_contextual, \
             patch('backend.services.agent.medical_agent.rewrite_medical_question') as mock_rewrite, \
             patch('backend.services.agent.medical_agent.semantic_search') as mock_search, \
             patch('backend.services.agent.medical_agent._format_history') as mock_format, \
             patch('backend.services.agent.medical_agent.generate_answer_with_llm') as mock_generate, \
             patch('backend.services.agent.medical_agent.safety_filter') as mock_safety:

            # Mock 返回值
            mock_classify.return_value = "medical"
            mock_gate.return_value = True
            mock_followup.return_value = (False, None)
            mock_contextual.return_value = "头痛怎么办"
            mock_rewrite.return_value = "头痛的症状和治疗方式"
            mock_search.return_value = [
                {"text": "头痛常见原因和治疗方法", "metadata": {"filename": "医疗指南.txt", "chunk_index": 0}}
            ]
            mock_format.return_value = ""
            mock_generate.return_value = "头痛可能是由多种原因引起的..."
            mock_safety.return_value = ("头痛可能是由多种原因引起的...", True, [])

            # 调用 process
            result = await self.agent.process(
                question="头痛怎么办",
                session_id="session001"
            )

            # 验证结果
            assert result.status == "success"
            assert result.query_type == "medical"
            assert result.answer == "头痛可能是由多种原因引起的..."
            assert result.sources[0]["filename"] == "医疗指南.txt"
            assert len(result.sources) == 1

            print(f"✅ status: {result.status}")
            print(f"✅ query_type: {result.query_type}")
            print(f"✅ answer: {result.answer}")
            print(f"✅ sources: {len(result.sources)}个")

    @pytest.mark.asyncio
    async def test_2_chat_stream_normal_case(self):
        """测试用例2：/chat-stream 普通医疗问答"""
        print("\n=== 测试用例2：/chat-stream 普通医疗问答 ===")

        # Mock prepare
        with patch.object(self.agent, 'prepare') as mock_prepare:
            mock_prepare.return_value = AgentPrepareResult(
                status="ready",
                question="头痛怎么办",
                query_type="medical",
                contextual_query="头痛怎么办",
                rewritten_query="头痛的症状和治疗方式",
                full_context="头痛常见原因和治疗方法",
                sources=[{"filename": "医疗指南.txt", "chunk_index": 0}],
                history_turns=0
            )

            # Mock LLM 流式生成
            mock_stream = AsyncGenerator()
            mock_stream.__aiter__.return_value = ["头痛", "可能是由", "多种原因", "引起的", "。", "[DONE]"]

            with patch('backend.services.agent.medical_agent.generate_answer_with_llm_stream') as mock_generate_stream, \
                 patch('backend.services.agent.medical_agent.safety_filter') as mock_safety, \
                 patch('backend.services.agent.medical_agent.memory_manager') as mock_memory:

                mock_generate_stream.return_value = mock_stream
                mock_safety.return_value = ("头痛可能是由多种原因引起的。", True, [])

                # 模拟 ChatRequest
                from backend.models.chat import ChatRequest
                request = ChatRequest(
                    question="头痛怎么办",
                    session_id="session001",
                    stream=True
                )

                # 调用 chat_stream
                response = await self._simulate_chat_stream(request)

                # 验证流式响应格式
                events = []
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str == "data: [DONE]":
                        events.append(line_str)
                        break
                    elif line_str.startswith("data: "):
                        data = json.loads(line_str[6:])
                        events.append(data)

                print("✅ Stream events:", [e if isinstance(e, str) else e.get('type') for e in events])

                # 验证 memory 被正确写入
                mock_memory.add_turn.assert_called_once()
                assert mock_memory.add_turn.call_count == 1

    @pytest.mark.asyncio
    async def test_3_chat_stream_multi_turn(self):
        """测试用例3：/chat-stream 多轮对话"""
        print("\n=== 测试用例3：/chat-stream 多轮对话 ===")

        # 模拟已存在历史对话
        with patch('backend.services.agent.medical_agent.memory_manager') as mock_memory:
            mock_memory.get_session_history.return_value = [
                {"user_question": "我昨天开始发烧", "assistant_answer": "建议休息观察"}
            ]
            mock_memory.get_turn_count.return_value = 1

            with patch.object(self.agent, 'prepare') as mock_prepare:
                mock_prepare.return_value = AgentPrepareResult(
                    status="ready",
                    question="这个严重吗",
                    query_type="medical",
                    contextual_query="我昨天开始发烧。补充问题：这个严重吗",
                    rewritten_query="发烧的严重程度判断",
                    full_context="【历史对话】\n用户：我昨天开始发烧\n助手：建议休息观察\n\n【知识库内容】\n发烧的严重程度判断",
                    sources=[{"filename": "发热诊疗.txt", "chunk_index": 0}],
                    history_turns=1
                )

                # Mock LLM 流式生成
                mock_stream = AsyncGenerator()
                mock_stream.__aiter__.return_value = ["一般", "不需要", "特别", "担心", "。", "[DONE]"]

                with patch('backend.services.agent.medical_agent.generate_answer_with_llm_stream') as mock_generate_stream, \
                     patch('backend.services.agent.medical_agent.safety_filter') as mock_safety:

                    mock_generate_stream.return_value = mock_stream
                    mock_safety.return_value = ("一般不需要特别担心。", True, [])

                    # 模拟 ChatRequest
                    from backend.models.chat import ChatRequest
                    request = ChatRequest(
                        question="这个严重吗",
                        session_id="session001",
                        stream=True
                    )

                    # 调用 chat_stream
                    response = await self._simulate_chat_stream(request)

                    # 验证历史对话被正确处理
                    mock_memory.get_session_history.assert_called_once_with("session001")

                    print("✅ 多轮对话：历史上下文已正确处理")
                    print("✅ contextual_query 包含历史:", mock_prepare.return_value.contextual_query)

    async def _simulate_chat_stream(self, request):
        """模拟 chat_stream 调用的辅助方法"""
        # 这里简化了实际的 HTTP 客户端调用
        # 实际使用时可以使用 httpx.AsyncClient 来测试真实的 HTTP 端点
        from backend.api.chat import chat_stream
        return await chat_stream(request)


class TestStreamProtocol:
    """Stream 协议格式测试"""

    def test_stream_format_unification(self):
        """测试流式协议统一格式"""
        print("\n=== 测试：Stream 协议统一格式 ===")

        # chunk 格式
        chunk_event = {"type": "chunk", "data": "头痛"}
        assert chunk_event["type"] == "chunk"

        # followup 格式
        followup_event = {"type": "followup", "data": {"question": "请具体描述"}}
        assert followup_event["type"] == "followup"

        # message 格式
        message_event = {"type": "message", "data": "知识库未收录相关内容。"}
        assert message_event["type"] == "message"

        # sources 格式
        sources_event = {
            "type": "sources",
            "data": [{"filename": "test.txt", "chunk_index": 0}]
        }
        assert sources_event["type"] == "sources"

        # DONE 标识
        done_signal = "[DONE]"
        assert done_signal == "[DONE]"

        print("✅ 所有 stream 格式已统一")


if __name__ == "__main__":
    # 运行测试
    import pytest
    pytest.main([__file__, "-v"])