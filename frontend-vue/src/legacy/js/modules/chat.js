let renderScheduled = false;

function normalizeAnswerMarkdown(rawText = "") {
    let text = String(rawText || "")
        .replace(/\r\n/g, "\n")
        .replace(/\n{3,}/g, "\n\n");

    // 压缩标题与正文之间的过大空行
    text = text.replace(/(^|\n)(#{1,6}[^\n]*)\n{2,}/g, "$1$2\n");

    // 去掉行首孤立的 **（未闭合加粗）造成的异常显示
    text = text
        .split("\n")
        .map((line) => {
            const trimmed = line.trimStart();
            if (trimmed.startsWith("**") && trimmed.indexOf("**", 2) === -1) {
                return line.replace("**", "");
            }
            return line;
        })
        .join("\n");

    return text.trim();
}

function updateMessage(id, content = null, source = null, replaceContent = false, forceReplace = false) {
    const msg = window.state.messages.find(m => m.id === id);
    if (!msg) return;

    if (content !== null) {
        if (forceReplace || replaceContent) {
            msg.content = content;
        } else {
            msg.content += content;
        }
        const compactContent = String(msg.content || "").replace(/\s+/g, "");
        msg.isThinking = compactContent.includes("🤔思考中");
    }

    if (source) {
        if (Array.isArray(source)) {
            msg.sources = source;
        } else {
            if (!msg.sources) {
                msg.sources = [];
            }

            const exists = msg.sources.some(
                s => s.filename === source.filename && s.chunk_index === source.chunk_index
            );

            if (!exists) {
                msg.sources.push(source);
            }
        }
    }

    if (!renderScheduled) {
        renderScheduled = true;
        requestAnimationFrame(() => {
            window.renderMessages(id);
            renderScheduled = false;
        });
    }
}

function setMessageThinking(id, isThinking) {
    const msg = window.state.messages.find(m => m.id === id);
    if (!msg) return;
    msg.isThinking = Boolean(isThinking);

    if (!renderScheduled) {
        renderScheduled = true;
        requestAnimationFrame(() => {
            window.renderMessages(id);
            renderScheduled = false;
        });
    }
}

function setMessageStreaming(id, isStreaming) {
    const msg = window.state.messages.find(m => m.id === id);
    if (!msg) return;
    msg.isStreaming = Boolean(isStreaming);

    if (!renderScheduled) {
        renderScheduled = true;
        requestAnimationFrame(() => {
            window.renderMessages(id);
            renderScheduled = false;
        });
    }
}

function addMessage(content, role) {
    const compactContent = String(content || "").replace(/\s+/g, "");
    const message = {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        role,
        content: content || '',
        sources: [],
        isThinking: role === "ai" && compactContent.includes("🤔思考中")
    };

    window.state.messages.push(message);

    const messageElement = document.createElement('div');
    messageElement.className = `chat-message ${role}-message`;
    messageElement.dataset.messageId = message.id;
    messageElement.innerHTML = window.buildMessageInnerHTML(message);

    window.elements.chatMessages.appendChild(messageElement);

    if (window.elements.chatMessages) {
        window.elements.chatMessages.scrollTop = window.elements.chatMessages.scrollHeight;
    }

    return message.id;
}

function buildSourceHTML(sources = []) {
    console.info("[sources_debug][frontend.render] input_message_sources=", sources);
    const groupedSources = window.groupSourcesByFile(sources);
    console.info("[sources_debug][frontend.render] grouped_by_filename=", groupedSources);
    if (!groupedSources.length) return "";

    return `
        <div class="sources">
            ${groupedSources.map(item => {
                const chunkText = (item.chunks || []).slice(0, 3).map(chunk => `第${chunk}段`).join("、");
                const label = chunkText ? `${item.filename}（${chunkText}）` : item.filename;
                return `<span class="source-tag" title="${window.escapeHtml(label)}">📄 ${window.escapeHtml(label)}</span>`;
            }).join("")}
        </div>
    `;
}

function buildMessageInnerHTML(msg) {
    if (msg.role === "ai") {
        const isStreaming = msg.isStreaming === true;
        const rawContent = String(msg.content || "");
        const compactContent = rawContent.replace(/\s+/g, "");
        const isThinking = msg.isThinking === true || compactContent.includes("🤔思考中");

        if (isThinking) {
            return `
                <div class="ai-message-wrap">
                    <div class="ai-avatar">思医</div>
                    <div class="message-bubble thinking-bubble-wrap">
                        <div class="thinking-inline" aria-live="polite">
                            <span class="thinking-emoji">🤔</span>
                            <span class="thinking-text">思考中</span>
                            <span class="thinking-dots" aria-hidden="true">
                                <i></i><i></i><i></i>
                            </span>
                        </div>
                    </div>
                </div>
            `;
        }

        let formattedContent = window.formatText(rawContent);
        try {
            formattedContent = window.marked.parse(
                normalizeAnswerMarkdown(rawContent)
            );
        } catch (_) {
            // Fallback to plain text when partial markdown is malformed mid-stream.
            formattedContent = window.formatText(rawContent);
        }
        const contentClass = isStreaming
            ? "message-content chat-content ai-message-content streaming-message"
            : "message-content chat-content ai-message-content";

        return `
            <div class="ai-message-wrap">
                <div class="ai-avatar">思医</div>
                <div class="message-bubble">
                    <div class="${contentClass}">${formattedContent}</div>
                    ${msg.sources && msg.sources.length > 0 ? buildSourceHTML(msg.sources) : ""}
                </div>
            </div>
        `;
    }

    return `
        <div class="message-bubble">
            <div class="message-content chat-content user-message-content">${window.formatText(msg.content || "")}</div>
        </div>
    `;
}

function renderMessages(targetId = null) {
    if (!window.elements.chatMessages) return;

    if (targetId) {
        const msg = window.state.messages.find(m => m.id === targetId);
        if (!msg) return;

        let msgElement = document.querySelector(`[data-message-id="${targetId}"]`);

        if (!msgElement) {
            msgElement = document.createElement('div');
            msgElement.className = `chat-message ${msg.role}-message`;
            msgElement.dataset.messageId = msg.id;
            window.elements.chatMessages.appendChild(msgElement);
        }

        msgElement.innerHTML = buildMessageInnerHTML(msg);
        window.elements.chatMessages.scrollTop = window.elements.chatMessages.scrollHeight;
        return;
    }

    const welcome = document.getElementById('welcomeCard');
    const notice = document.querySelector('.medical-notice');
    window.elements.chatMessages.innerHTML = '';

    if (window.state.messages.length === 0) {
        if (welcome) window.elements.chatMessages.appendChild(welcome);
        if (notice) window.elements.chatMessages.appendChild(notice);
    }

    window.state.messages.forEach(msg => {
        const msgElement = document.createElement('div');
        msgElement.className = `chat-message ${msg.role}-message`;
        msgElement.dataset.messageId = msg.id;
        msgElement.innerHTML = buildMessageInnerHTML(msg);
        window.elements.chatMessages.appendChild(msgElement);
    });

    window.elements.chatMessages.scrollTop = window.elements.chatMessages.scrollHeight;
}

function hideWelcomeCard() {
    const welcomeCard = document.getElementById('welcomeCard');
    if (welcomeCard) welcomeCard.style.display = 'none';
}

function addWelcomeMessage() {
    if (window.state.messages.length > 0) return;
    window.addMessage(
        "您好，我是思医。\n\n我支持上传医学文档、构建医疗知识库，并基于知识库进行问答与来源追溯，帮助医学学习和知识查询。",
        "ai"
    );
}

function resetChat() {
    window.state.messages = [];
    window.renderMessages();
}

window.updateMessage = updateMessage;
window.setMessageThinking = setMessageThinking;
window.setMessageStreaming = setMessageStreaming;
window.addMessage = addMessage;
window.buildSourceHTML = buildSourceHTML;
window.buildMessageInnerHTML = buildMessageInnerHTML;
window.renderMessages = renderMessages;
window.hideWelcomeCard = hideWelcomeCard;
window.addWelcomeMessage = addWelcomeMessage;
window.resetChat = resetChat;
window.renderScheduled = renderScheduled;
