from unittest.mock import Mock, patch

from backend.services.agent.smart_router import SmartRouter


def test_route_chitchat_keyword():
    router = SmartRouter()
    result = router.route("你好")
    assert result["type"] == "chitchat"


def test_route_medical_by_llm():
    router = SmartRouter()
    with patch("backend.services.agent.smart_router.get_llm_client") as mock_client_factory:
        mock_client = Mock()
        mock_client_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content='{"type":"medical","reason":"医疗问题"}'))]
        )
        result = router.route("高血压怎么办")
    assert result["type"] == "medical"


def test_route_out_of_scope_keyword():
    router = SmartRouter()
    result = router.route("帮我写Python代码")
    assert result["type"] == "out_of_scope"


def test_route_high_risk_keyword():
    router = SmartRouter()
    result = router.route("安眠药吃多少会死")
    assert result["type"] == "high_risk"


def test_route_llm_invalid_json_fallback():
    router = SmartRouter()
    with patch("backend.services.agent.smart_router.get_llm_client") as mock_client_factory:
        mock_client = Mock()
        mock_client_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="not json"))]
        )
        result = router.route("这是一条未知测试问题")
    assert result == {"type": "medical", "reason": "fallback"}


def test_route_short_medical_keyword_should_not_use_llm():
    router = SmartRouter()
    with patch("backend.services.agent.smart_router.get_llm_client") as mock_client_factory:
        result = router.route("解剖学")
    assert result["type"] == "medical"
    assert mock_client_factory.call_count == 0
