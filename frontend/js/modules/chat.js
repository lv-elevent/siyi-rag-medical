let renderScheduled = false;

function updateMessage(id, content = null, source = null, replaceContent = false, forceReplace = false) {
    const msg = window.state.messages.find(m => m.id === id);
    if (!msg) return;

    if (content !== null) {
        if (forceReplace || replaceContent) {
            msg.content = content;
        } else {
            msg.content += content;
        }
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

function addMessage(content, role) {
    const message = {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        role,
        content: content || '',
        sources: []
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
    const groupedSources = window.groupSourcesByFile(sources);
    if (!groupedSources.length) return "";

    return `
        <div class="message-source">
            <div class="source-title">📚 参考来源</div>
            <div class="source-list">
                ${groupedSources.map(item => `
                    <div class="source-item">
                        <span class="source-file" title="${window.escapeHtml(item.filename)}">
                            📄 ${window.escapeHtml(item.filename)}
                        </span>
                        <span class="source-chunk">第${item.chunks.join('、')}段</span>
                    </div>
                `).join("")}
            </div>
        </div>
    `;
}

function buildMessageInnerHTML(msg) {
    if (msg.role === "ai") {

        const isStreaming = msg.isStreaming === true;

        const formattedContent = isStreaming
            ? window.formatText(msg.content || "")
            : window.marked.parse(
                (msg.content || "")
                    .replace(/\n{3,}/g, '\n\n')
                    .trim()
            );

        return `
            <div class="ai-message-wrap">
                <div class="ai-avatar">思医</div>
                <div class="message-bubble">
                    <div class="message-content">${formattedContent}</div>
                    ${msg.sources && msg.sources.length > 0 ? buildSourceHTML(msg.sources) : ""}
                </div>
            </div>
        `;
    }

    return `
        <div class="message-bubble">
            <div class="message-content">${window.formatText(msg.content || "")}</div>
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
    window.addMessage("您好，我是您的智能医疗助手「思医」\n\n您可以向我咨询疾病知识、用药建议或结合知识库进行问答。", "ai");
}

function resetChat() {
    window.state.messages = [];
    window.renderMessages();
}

// 挂到 window 上供原 script.js 使用
window.updateMessage = updateMessage;
window.addMessage = addMessage;
window.buildSourceHTML = buildSourceHTML;
window.buildMessageInnerHTML = buildMessageInnerHTML;
window.renderMessages = renderMessages;
window.hideWelcomeCard = hideWelcomeCard;
window.addWelcomeMessage = addWelcomeMessage;
window.resetChat = resetChat;
window.renderScheduled = renderScheduled;