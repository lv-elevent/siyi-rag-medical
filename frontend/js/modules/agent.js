async function sendMessage() {
    if (!window.getToken()) {
        window.showAuthScreen?.('请先登录');
        return;
    }

    if (window.state.isSending || window.state.isStreaming) return;

    const message = window.elements.chatInput?.value?.trim() || '';
    if (!message) return;

    window.updateState({ isSending: true });

    try {
        window.elements.chatInput.value = '';
        window.state.chatInput = '';

        window.hideWelcomeCard();
        window.addMessage(message, 'user');

        await window.askQuestionToBackendStream(message);

        // 流式完成后刷新左侧历史，拿到后端自动生成的标题
        if (window.fetchSessions && window.renderSessionList) {
            const sessions = await window.fetchSessions();
            window.renderSessionList(sessions);
        }

    } catch (error) {
        console.error(`发送消息失败: ${error.message}`);
        window.addMessage("服务器错误，请稍后重试", "ai");
    } finally {
        window.updateState({ isSending: false });

        if (window.elements.chatInput) {
            window.elements.chatInput.disabled = false;
            window.elements.chatInput.focus();
        }

        if (window.elements.sendButton) {
            window.elements.sendButton.disabled = false;
        }
    }
}

async function askQuestionToBackendStream(question) {
    if (window.state.isStreaming) {
        return;
    }

    window.state.isStreaming = true;

    const requestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;

    try {
        const response = await window.fetch(`${window.API_BASE_URL}/chat-stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
                'X-Request-Id': requestId,
                // 仅新增：自动携带登录Token鉴权
                ...window.getAuthHeaders()
            },
            body: JSON.stringify({
                question,
                document_id: window.state.selectedDocumentId || "",
                knowledge_base_id: window.state.currentKbId || null,
                session_id: window.state.sessionId,
                stream: true,
                use_agent: true
            })
        });

        if (response.status === 401) {
            window.logout?.();
            window.showAuthScreen?.('请先登录');
            return;
        }

        if (!response.ok) {
            throw new Error(`请求失败: ${response.status}`);
        }

        if (!response.body) {
            throw new Error("流式响应失败");
        }

        const aiMessageId = window.addMessage('正在思考...', 'ai');
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let buffer = "";
        let accumulatedText = "";

        while (true) {
            let done, value;

            try {
                ({ done, value } = await reader.read());
            } catch (readError) {
                console.error(`流式读取错误: ${readError.message}`);
                break;
            }

            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";

            for (const part of parts) {
                if (!part.trim()) continue;
                if (!part.startsWith("data: ")) continue;

                const payload = part.slice(6).trim();

                if (payload === "[DONE]") {
                    break;
                }

                try {
                    const data = JSON.parse(payload);

                    if (data.type === "chunk") {
                        const chunk = data.data || "";
                        accumulatedText = `${accumulatedText}${chunk}`;
                        window.updateMessage(aiMessageId, accumulatedText, null, true);
                    } else if (data.type === "message") {
                        window.updateMessage(aiMessageId, data.data || "系统消息", null, false, true);
                    } else if (data.type === "followup") {
                        const followupText = data.data?.question || "请补充更多信息。";
                        window.updateMessage(aiMessageId, followupText, null, false, true);
                    } else if (data.type === "sources") {
                        window.updateMessage(aiMessageId, null, data.data || [], false, false);
                    }
                } catch (e) {
                    console.warn("解析流数据失败:", e);
                }
            }
        }
    } finally {
        window.state.isStreaming = false;
    }
}

// 挂到 window 上供原 script.js 使用
window.sendMessage = sendMessage;
window.askQuestionToBackendStream = askQuestionToBackendStream;