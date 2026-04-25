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
    const aiMessageId = window.addMessage('', 'ai');
    window.updateMessage(aiMessageId, '🤔 思考中...', null, false, true);
    window.setMessageThinking?.(aiMessageId, true);
    window.setMessageStreaming?.(aiMessageId, false);

    const requestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;

    try {
        const response = await window.fetch(`${window.API_BASE_URL}/chat-stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
                'X-Request-Id': requestId,
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

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let buffer = "";
        let fullText = "";
        let streamBuffer = "";
        let lastUpdate = Date.now();
        let thinkingActive = true;
        let streamDone = false;

        const flushMarkdownRender = (force = false) => {
            if (!streamBuffer) return;
            const now = Date.now();
            if (!force && now - lastUpdate < 50) return;
            fullText += streamBuffer;
            streamBuffer = "";
            lastUpdate = now;
            window.updateMessage(aiMessageId, fullText, null, true);
        };

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
                    flushMarkdownRender(true);
                    streamDone = true;
                    break;
                }

                try {
                    const data = JSON.parse(payload);

                    if (data.type === "thinking_start") {
                        thinkingActive = true;
                        const thinkingText = data.data || "🤔 思考中...";
                        window.updateMessage(aiMessageId, thinkingText, null, false, true);
                        window.setMessageThinking?.(aiMessageId, true);
                        window.setMessageStreaming?.(aiMessageId, false);
                    } else if (data.type === "thinking_end") {
                        thinkingActive = false;
                        window.setMessageThinking?.(aiMessageId, false);
                    } else if (data.type === "chunk") {
                        const chunk = data.data || "";
                        streamBuffer += chunk;
                        if (thinkingActive) {
                            thinkingActive = false;
                            window.setMessageThinking?.(aiMessageId, false);
                        }
                        window.setMessageStreaming?.(aiMessageId, true);
                        flushMarkdownRender(false);
                    } else if (data.type === "message") {
                        flushMarkdownRender(true);
                        if (thinkingActive) {
                            thinkingActive = false;
                            window.setMessageThinking?.(aiMessageId, false);
                        }
                        window.setMessageStreaming?.(aiMessageId, false);
                        window.updateMessage(aiMessageId, data.data || "系统消息", null, false, true);
                    } else if (data.type === "followup") {
                        flushMarkdownRender(true);
                        if (thinkingActive) {
                            thinkingActive = false;
                            window.setMessageThinking?.(aiMessageId, false);
                        }
                        window.setMessageStreaming?.(aiMessageId, false);
                        const followupText = data.data?.question || "请补充更多信息。";
                        window.updateMessage(aiMessageId, followupText, null, false, true);
                    } else if (data.type === "sources") {
                        console.info("[sources_debug][frontend.receive] event_type=sources payload=", data.data);
                        console.info("[sources_debug][frontend.receive] render_field=message.sources via updateMessage(source=array)");
                        window.updateMessage(aiMessageId, null, data.data || [], false, false);
                    }
                } catch (e) {
                    console.warn("解析流数据失败:", e);
                }
            }

            if (streamDone) {
                break;
            }
        }
        flushMarkdownRender(true);
    } finally {
        window.setMessageThinking?.(aiMessageId, false);
        window.setMessageStreaming?.(aiMessageId, false);
        window.state.isStreaming = false;
    }
}

window.sendMessage = sendMessage;
window.askQuestionToBackendStream = askQuestionToBackendStream;
