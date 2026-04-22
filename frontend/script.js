const API_BASE_URL = 'http://127.0.0.1:8000';

// 确保 marked 可用
if (typeof marked === 'undefined') {
    window.marked = {
        parse: text => text
    };
}

// 模拟知识库卡片（前端层）
const DEFAULT_LIBRARIES = [
    { name: '内科知识库', icon: '🏥', files: [] },
    { name: '外科知识库', icon: '⚕️', files: [] },
    { name: '儿科知识库', icon: '👶', files: [] },
    { name: '药学知识库', icon: '💊', files: [] },
    { name: '急诊知识库', icon: '🚑', files: [] },
    { name: '检验知识库', icon: '🧪', files: [] }
];

function loadLibrariesFromStorage() {
    try {
        const raw = localStorage.getItem('rag_libraries');
        if (!raw) return DEFAULT_LIBRARIES;
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed) || !parsed.length) return DEFAULT_LIBRARIES;
        return parsed;
    } catch (e) {
        return DEFAULT_LIBRARIES;
    }
}

function saveLibrariesToStorage(libraries) {
    localStorage.setItem('rag_libraries', JSON.stringify(libraries));
}

function getStoredUser() {
    try {
        const raw = localStorage.getItem('rag_user');
        return raw ? JSON.parse(raw) : null;
    } catch (e) {
        return null;
    }
}

// 应用状态管理（仅保留全局 state）
const state = {
    uploadedFile: null,
    uploadedFileName: "",
    uploadStatus: "idle",

    messages: [],
    chatInput: "",
    isSending: false,

    systemStatus: "empty",

    knowledgeFiles: [],
    selectedDocumentId: null,
    selectedDocumentName: null,
    kbFilesPanelOpen: false,
    isStreaming: false,

    sessionId: localStorage.getItem("rag_session_id") || (() => {
        const id = `session_${Date.now()}`;
        localStorage.setItem("rag_session_id", id);
        return id;
    })(),

    libraries: loadLibrariesFromStorage(),
    currentLibraryName: localStorage.getItem('rag_current_library') || null,
    currentUser: getStoredUser()
};

// DOM 元素引用
const elements = {
    pdfUpload: document.getElementById('pdf-upload'),
    uploadArea: document.getElementById('uploadAreaModal'),
    uploadStatus: document.getElementById('upload-status'),
    uploadPreview: document.getElementById('uploadPreview'),

    kbStatus: document.getElementById('kb-status'),
    chatMessages: document.getElementById('chat-messages'),
    chatInput: document.getElementById('chat-input'),
    sendButton: document.getElementById('send-button'),

    toggleKbFilesButton: document.getElementById('toggle-kb-files'),
    kbFilesPanel: document.getElementById('kb-files-panel'),
    kbFilesList: document.getElementById('kb-files-list'),
    selectedDoc: document.getElementById('selected-doc'),
    fileSearch: document.getElementById('fileSearch'),

    profileBtn: document.getElementById('profileBtn'),
    profileMenu: document.getElementById('profileMenu'),
    uploadBtn: document.getElementById('uploadBtn'),
    kbBtn: document.getElementById('kbBtn'),
    newChatBtn: document.getElementById('newChatBtn'),

    currentKbBadge: document.getElementById('currentKbBadge'),
    sidebarCurrentKb: document.getElementById('sidebarCurrentKb'),

    kbGrid: document.getElementById('kbGrid'),
    libFiles: document.getElementById('libFiles'),
    libTitle: document.getElementById('libTitle'),
    libraryTip: document.getElementById('libraryTip'),
    addFileToLibBtn: document.getElementById('addFileToLibBtn'),

    toast: document.getElementById('custom-toast'),

    // 鉴权相关
    authScreen: document.getElementById('auth-screen'),
    appScreen: document.getElementById('app-screen'),
    authMessage: document.getElementById('authMessage'),

    showLoginTab: document.getElementById('showLoginTab'),
    showRegisterTab: document.getElementById('showRegisterTab'),

    loginPanel: document.getElementById('loginPanel'),
    registerPanel: document.getElementById('registerPanel'),

    loginUsername: document.getElementById('loginUsername'),
    loginPassword: document.getElementById('loginPassword'),

    registerUsername: document.getElementById('registerUsername'),
    registerPassword: document.getElementById('registerPassword'),
    registerPhone: document.getElementById('registerPhone'),

    loginBtn: document.getElementById('loginBtn'),
    registerBtn: document.getElementById('registerBtn'),

    profileName: document.getElementById('profileName'),
    profileModalUsername: document.getElementById('profileModalUsername'),
    historyList: document.getElementById('historyList')
};

// 挂到 window 供模块使用（桥接）
window.state = state;
window.elements = elements;
window.saveLibrariesToStorage = saveLibrariesToStorage;
window.API_BASE_URL = API_BASE_URL;
window.updateUI = updateUI;

// 基础工具：escape / format
function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
function escapeAttr(text) { return escapeHtml(text); }
function escapeJs(str) { return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'"); }
function formatText(text) { return escapeHtml(text).replace(/\n/g, '<br>'); }

window.escapeHtml = escapeHtml;
window.escapeAttr = escapeAttr;
window.escapeJs = escapeJs;
window.formatText = formatText;

// ================= 会话系统 =================

// 获取会话列表
async function fetchSessions() {
    try {
        const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
            headers: {
                ...window.getAuthHeaders()
            }
        });

        const data = await res.json();
        if (data.status !== 'success') return [];

        return data.sessions || [];
    } catch (e) {
        console.error("获取会话失败", e);
        return [];
    }
}
window.fetchSessions = fetchSessions;

function groupSessions(sessions) {
    const today = [];
    const yesterday = [];
    const older = [];

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterdayStart = new Date(todayStart);
    yesterdayStart.setDate(todayStart.getDate() - 1);

    sessions.forEach(s => {
        const t = new Date(s.created_at || s.updated_at || Date.now());

        if (t >= todayStart) {
            today.push(s);
        } else if (t >= yesterdayStart) {
            yesterday.push(s);
        } else {
            older.push(s);
        }
    });

    return { today, yesterday, older };
}
window.groupSessions = groupSessions;

// 渲染历史列表
function groupSessions(sessions) {
    const today = [];
    const yesterday = [];
    const older = [];

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterdayStart = new Date(todayStart);
    yesterdayStart.setDate(todayStart.getDate() - 1);

    sessions.forEach(s => {
        const t = new Date(s.created_at || s.updated_at || Date.now());

        if (t >= todayStart) {
            today.push(s);
        } else if (t >= yesterdayStart) {
            yesterday.push(s);
        } else {
            older.push(s);
        }
    });

    return { today, yesterday, older };
}
window.groupSessions = groupSessions;

function renderSessionList(sessions) {
    const container = elements.historyList;
    if (!container) return;

    container.innerHTML = '';

    if (!sessions.length) {
        container.innerHTML = `<div class="history-empty">暂无历史对话</div>`;
        return;
    }

    const groups = groupSessions(sessions);

    function renderGroup(title, list) {
        if (!list.length) return;

        const header = document.createElement('div');
        header.className = 'history-group';
        header.textContent = title;
        container.appendChild(header);

        list.forEach(s => {
            const row = document.createElement('div');
            row.className = 'history-row';

            const item = document.createElement('div');
            item.className = 'history-item';

            if (s.session_id === state.sessionId) {
                item.classList.add('active');
            }

            item.textContent = s.title || '新对话';

            item.onclick = async () => {
                await switchSession(s.session_id);
                const latestSessions = await fetchSessions();
                renderSessionList(latestSessions);
            };

            const delBtn = document.createElement('span');
            delBtn.className = 'delete-btn';
            delBtn.textContent = '×';
            delBtn.title = '删除该对话';

            delBtn.onclick = async (e) => {
                e.stopPropagation();

                const ok = confirm(`确定删除对话「${s.title || '新对话'}」吗？`);
                if (!ok) return;

                const isDeletingCurrent = state.sessionId === s.session_id;
                const deleted = await deleteSession(s.session_id);

                if (!deleted) {
                    showToast('删除失败', 'error');
                    return;
                }

                // 删的是当前会话：直接进入新会话空态
                if (isDeletingCurrent) {
                    resetSessionId();
                    if (window.resetChat) window.resetChat();
                    if (window.addWelcomeMessage) window.addWelcomeMessage();
                }

                const latestSessions = await fetchSessions();
                renderSessionList(latestSessions);
                showToast('对话已删除', 'success');
            };

            row.appendChild(item);
            row.appendChild(delBtn);
            container.appendChild(row);
        });
    }

    renderGroup('今天', groups.today);
    renderGroup('昨天', groups.yesterday);
    renderGroup('更早', groups.older);
}
window.renderSessionList = renderSessionList;

async function deleteSession(sessionId) {
    try {
        const res = await fetch(`${API_BASE_URL}/chat/session`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                ...window.getAuthHeaders()
            },
            body: JSON.stringify({
                session_id: sessionId
            })
        });

        if (!res.ok) {
            console.error('删除会话失败', res.status);
            return false;
        }

        const data = await res.json();
        return data.status === 'success';
    } catch (e) {
        console.error("删除会话失败", e);
        return false;
    }
}
window.deleteSession = deleteSession;

// 加载历史消息
async function loadMessages(sessionId) {
    try {
        const res = await fetch(
            `${API_BASE_URL}/chat/messages?session_id=${sessionId}`,
            {
                headers: {
                    ...window.getAuthHeaders()
                }
            }
        );

        const data = await res.json();
        if (data.status !== 'success') return;

        const msgs = data.messages || [];

        state.messages = msgs.map(m => ({
            id: m.id,
            role: m.role === 'assistant' ? 'ai' : 'user',
            content: m.content,
            sources: m.metadata_json?.sources || []
        }));

        if (window.renderMessages) window.renderMessages();

    } catch (e) {
        console.error("加载消息失败", e);
    }
}
window.loadMessages = loadMessages;

// 切换会话
async function switchSession(sessionId) {
    state.sessionId = sessionId;
    localStorage.setItem("rag_session_id", sessionId);

    await loadMessages(sessionId);
}
window.switchSession = switchSession;

async function generateTitle(text) {
    try {
        const title = text.slice(0, 20);

        const res = await fetch(`${API_BASE_URL}/chat/session/title`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...window.getAuthHeaders()
            },
            body: JSON.stringify({
                session_id: state.sessionId,
                title
            })
        });

        if (!res.ok) {
            console.error('更新会话标题失败', res.status);
            return;
        }

        const sessions = await fetchSessions();
        renderSessionList(sessions);
    } catch (e) {
        console.error("生成标题失败", e);
    }
}
window.generateTitle = generateTitle;

// 状态更新与 UI 控制
function updateState(newState) {
    Object.assign(state, newState);
    updateUI();
}
window.updateState = updateState;

function hasAvailableKnowledge() {
    return state.systemStatus === 'ready' || (state.knowledgeFiles && state.knowledgeFiles.length > 0);
}

function showToast(message, type = 'success') {
    const toast = elements.toast;
    if (!toast) return;

    toast.textContent = message;
    toast.className = `toast show ${type}`;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => {
        toast.className = 'toast';
    }, 2200);
}
window.showToast = showToast;

function updateProfileUI(user) {
    const username = user?.username || '医疗用户';

    if (elements.profileName) {
        elements.profileName.textContent = username;
    }

    if (elements.profileModalUsername) {
        elements.profileModalUsername.textContent = username;
    }
}

function showAuthScreen(message = '') {
    if (elements.authScreen) elements.authScreen.style.display = 'flex';
    if (elements.appScreen) elements.appScreen.style.display = 'flex';
    if (elements.authMessage) elements.authMessage.textContent = message || '';
}

function showAppScreen() {
    if (elements.authScreen) elements.authScreen.style.display = 'none';
    if (elements.appScreen) elements.appScreen.style.display = 'flex';
    if (elements.authMessage) elements.authMessage.textContent = '';
}

function switchAuthTab(tab) {
    const isLogin = tab === 'login';

    if (elements.loginPanel) {
        elements.loginPanel.style.display = isLogin ? 'block' : 'none';
    }

    if (elements.registerPanel) {
        elements.registerPanel.style.display = isLogin ? 'none' : 'block';
    }

    if (elements.showLoginTab) {
        elements.showLoginTab.classList.toggle('active', isLogin);
    }

    if (elements.showRegisterTab) {
        elements.showRegisterTab.classList.toggle('active', !isLogin);
    }

    if (elements.authMessage) {
        elements.authMessage.textContent = '';
    }
}

function resetSessionId() {
    const id = `session_${Date.now()}`;
    state.sessionId = id;
    localStorage.setItem("rag_session_id", id);
    return id;
}

function updateUI() {
    const canChat = hasAvailableKnowledge();

    if (elements.chatInput) {
        elements.chatInput.disabled = !canChat;
        elements.chatInput.placeholder = canChat
            ? '请输入你的问题...'
            : '当前知识库为空，请先上传文件';
    }

    if (elements.sendButton) {
        elements.sendButton.disabled = !canChat || state.isSending;
        elements.sendButton.textContent = state.isSending ? '发送中...' : '发送';
    }

    if (state.uploadStatus === 'uploading') {
        if (window.showUploadStatus) window.showUploadStatus('正在上传...', 'idle');
    }
}

function resetUserScopedState() {
    state.messages = [];
    state.selectedSessionId = null;
    state.selectedDocumentId = null;
    state.selectedDocumentName = null;
    state.knowledgeFiles = [];
    state.kbs = [];
    state.currentKbId = null;
    state.systemStatus = 'empty';

    if (window.state) {
        window.state.messages = [];
        window.state.selectedSessionId = null;
        window.state.selectedDocumentId = null;
        window.state.selectedDocumentName = null;
        window.state.knowledgeFiles = [];
        window.state.kbs = [];
        window.state.currentKbId = null;
        window.state.systemStatus = 'empty';
    }

    if (elements.chatMessages) {
        elements.chatMessages.innerHTML = '';
    }

    if (elements.historyList) {
        elements.historyList.innerHTML = '';
    }

    if (window.renderKnowledgeFiles) {
        window.renderKnowledgeFiles('');
    }

    if (window.updateSelectedDocumentDisplay) {
        window.updateSelectedDocumentDisplay();
    }

    if (window.updateKnowledgeBaseStatus) {
        window.updateKnowledgeBaseStatus({
            status: 'empty',
            filename: ''
        });
    }

    if (window.renderKbGrid) {
        window.renderKbGrid();
    }

    updateUI();
}

async function bootstrapAfterLogin() {
    resetUserScopedState();

    try {
        const user = await window.getCurrentUser();
        state.currentUser = user;
        localStorage.setItem('rag_user', JSON.stringify(user));
        updateProfileUI(user);
    } catch (error) {
        const user = getStoredUser();
        state.currentUser = user;
        updateProfileUI(user);
    }

    showAppScreen();

    state.kbFilesPanelOpen = true;
    if (window.syncKbToggleButtonText) {
        window.syncKbToggleButtonText();
    }

    if (window.setCurrentLibrary) {
        window.setCurrentLibrary(state.currentLibraryName);
    }

    if (window.fetchKnowledgeBases) {
        await window.fetchKnowledgeBases();
    }

    if (window.fetchKnowledgeFiles) {
        await window.fetchKnowledgeFiles();
    }

    if (window.fetchKnowledgeBaseStatus) {
        await window.fetchKnowledgeBaseStatus();
    }

    if (window.renderKbGrid) {
        window.renderKbGrid();
    }

    updateUI();

    const sessions = await fetchSessions();
    renderSessionList(sessions);

    if (sessions.length > 0) {
        await switchSession(sessions[0].session_id);
    } else {
        if (window.state.messages.length === 0 && window.addWelcomeMessage) {
            window.addWelcomeMessage();
        }
    }
}

// 保留原 init 名称，内部改为登录后的初始化
async function init() {
    await bootstrapAfterLogin();
}

function setupEventListeners() {
    document.querySelectorAll('[data-close]').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.dataset.close;
            const modal = document.getElementById(id);
            if (modal) modal.classList.remove('show');
        });
    });

    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.remove('show');
        });
    });

    if (elements.showLoginTab) {
        elements.showLoginTab.addEventListener('click', () => switchAuthTab('login'));
    }

    if (elements.showRegisterTab) {
        elements.showRegisterTab.addEventListener('click', () => switchAuthTab('register'));
    }

    if (elements.loginBtn) {
        elements.loginBtn.addEventListener('click', async () => {
            const username = elements.loginUsername?.value?.trim() || '';
            const password = elements.loginPassword?.value?.trim() || '';

            if (!username || !password) {
                showAuthScreen('请输入用户名和密码');
                return;
            }

            try {
                if (elements.authMessage) elements.authMessage.textContent = '';
                await window.login(username, password);
                resetSessionId();
                state.messages = [];
                await bootstrapAfterLogin();
                showToast('登录成功', 'success');
            } catch (error) {
                showAuthScreen(error.message || '登录失败');
            }
        });
    }

    if (elements.registerBtn) {
        elements.registerBtn.addEventListener('click', async () => {
            const username = elements.registerUsername?.value?.trim() || '';
            const password = elements.registerPassword?.value?.trim() || '';
            const phone = elements.registerPhone?.value?.trim() || '';

            if (!username || !password) {
                showAuthScreen('请输入注册用户名和密码');
                switchAuthTab('register');
                return;
            }

            try {
                await window.register(username, password, phone);
                switchAuthTab('login');

                if (elements.loginUsername) elements.loginUsername.value = username;
                if (elements.loginPassword) elements.loginPassword.value = password;

                showAuthScreen('注册成功，请登录');
            } catch (error) {
                showAuthScreen(error.message || '注册失败');
                switchAuthTab('register');
            }
        });
    }

    if (elements.profileBtn && elements.profileMenu) {
        elements.profileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            elements.profileMenu.classList.toggle('show');
        });

        document.addEventListener('click', (e) => {
            if (!elements.profileMenu.contains(e.target) && !elements.profileBtn.contains(e.target)) {
                elements.profileMenu.classList.remove('show');
            }
        });
    }

    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const root = document.documentElement;
            const isLight = root.classList.contains('light-mode');
            root.classList.toggle('light-mode', !isLight);
            root.classList.toggle('dark-mode', isLight);
            showToast(isLight ? '已切换为暗色模式' : '已切换为明亮模式', 'success');
        });
    }

    const viewProfileBtn = document.getElementById('viewProfileBtn');
    if (viewProfileBtn) {
        viewProfileBtn.addEventListener('click', () => {
            if (elements.profileMenu) elements.profileMenu.classList.remove('show');
            if (window.openModal) window.openModal('profileModal');
        });
    }

    const switchAccountBtn = document.getElementById('switchAccountBtn');
    if (switchAccountBtn) {
        switchAccountBtn.addEventListener('click', () => {
            if (elements.profileMenu) elements.profileMenu.classList.remove('show');
            window.logout?.();
            state.currentUser = null;
            state.messages = [];
            resetSessionId();
            showAuthScreen('请重新登录');
            switchAuthTab('login');
            showToast('已切换账号', 'success');
        });
    }

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            if (elements.profileMenu) elements.profileMenu.classList.remove('show');

            window.logout?.();
            state.currentUser = null;
            state.messages = [];
            resetSessionId();

            if (window.renderMessages) window.renderMessages();
            showAuthScreen('已退出登录');
            switchAuthTab('login');

            showToast('退出登录成功', 'success');
        });
    }

    if (elements.uploadBtn) {
        elements.uploadBtn.addEventListener('click', () => {
            if (window.openModal) window.openModal('uploadModal');
        });
    }

    if (elements.kbBtn) {
        elements.kbBtn.addEventListener('click', () => {
            if (window.openModal) window.openModal('kbModal');
        });
    }

    if (elements.newChatBtn) {
        elements.newChatBtn.addEventListener('click', async () => {
            resetSessionId();
            if (window.resetChat) window.resetChat();
            if (window.addWelcomeMessage) window.addWelcomeMessage();

            const sessions = await fetchSessions();
            renderSessionList(sessions);

            showToast('已新建对话', 'success');
        });
    }

    const createKbBtn = document.getElementById('createKbBtn');
    if (createKbBtn) {
        createKbBtn.addEventListener('click', () => {
            if (window.createNewLibrary) window.createNewLibrary();
        });
    }

    if (elements.pdfUpload) {
        elements.pdfUpload.addEventListener('change', (e) => {
            if (window.handleFileUpload) window.handleFileUpload(e);
        });
    }

    if (elements.uploadArea) {
        elements.uploadArea.addEventListener('click', (e) => {
            // label[for=pdf-upload] 会自动触发文件选择，避免双触发
            if (e.target.closest('.upload-label')) {
                return;
            }
            if (elements.pdfUpload && state.uploadStatus !== 'uploading') {
                elements.pdfUpload.click();
            }
        });

        elements.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (state.uploadStatus !== 'uploading') {
                elements.uploadArea.classList.add('drag-over');
            }
        });

        elements.uploadArea.addEventListener('dragleave', () => {
            elements.uploadArea.classList.remove('drag-over');
        });

        elements.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            elements.uploadArea.classList.remove('drag-over');

            if (state.uploadStatus === 'uploading') return;

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                if (window.handleFile) window.handleFile(files[0]);
            } else {
                if (window.showUploadStatus) window.showUploadStatus('请选择文件', 'error');
            }
        });
    }

    if (elements.chatInput) {
        elements.chatInput.addEventListener('input', (e) => {
            state.chatInput = e.target.value;
        });

        elements.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (window.sendMessage) window.sendMessage();
            }
        });
    }

    if (elements.sendButton) {
        elements.sendButton.addEventListener('click', (e) => {
            e.preventDefault();
            if (window.sendMessage) window.sendMessage();
        });
    }

    if (elements.toggleKbFilesButton) {
        elements.toggleKbFilesButton.addEventListener('click', () => {
            if (window.toggleKnowledgeFilesPanel) window.toggleKnowledgeFilesPanel();
        });
    }

    if (elements.fileSearch) {
        elements.fileSearch.addEventListener('input', (e) => {
            if (window.renderKnowledgeFiles) window.renderKnowledgeFiles(e.target.value);
        });
    }

    if (elements.addFileToLibBtn) {
        elements.addEventListener;
        elements.addFileToLibBtn.addEventListener('click', () => {
            const libraryName = state.currentLibraryName;

            if (!libraryName) {
                showToast('请先选择知识库', 'error');
                return;
            }

            if (window.openSelectFileModal) window.openSelectFileModal(libraryName);
        });
    }

    const confirmAddFilesBtn = document.getElementById('confirmAddFilesBtn');
    if (confirmAddFilesBtn) {
        confirmAddFilesBtn.addEventListener('click', async () => {
            const libraryName = state.tempSelectLibrary;
            const library = window.findLibraryByName ? window.findLibraryByName(libraryName) : null;

            if (!library) {
                showToast('知识库不存在', 'error');
                return;
            }

            const checked = document.querySelectorAll('#selectFileList input:checked');
            if (!checked.length) {
                showToast('请选择文件', 'error');
                return;
            }

            const targetKbId = window.state.currentKbId || null;
            if (!targetKbId) {
                showToast('当前知识库无效', 'error');
                return;
            }

            let addedCount = 0;
            for (const input of checked) {
                await window.apiAttachDocumentToKB(input.value, targetKbId);
                addedCount++;
            }

            if (window.closeModal) window.closeModal('selectFileModal');
            if (window.openLibraryById) {
                await window.openLibraryById(targetKbId, libraryName);
            }
            if (window.fetchKnowledgeFiles) {
                await window.fetchKnowledgeFiles();
            }
            if (window.renderKbGrid) window.renderKbGrid();

            showToast(`已添加 ${addedCount} 个文件到「${libraryName}」`, 'success');
        });
    }
}

// editLibrary 留在入口文件
function editLibrary(event, btn) {
    event.stopPropagation();

    const input = btn.parentElement.previousElementSibling;
    const oldName = input.value;
    const card = btn.closest('.kb-card');
    const kbId = card?.dataset?.id;

    input.readOnly = false;
    input.focus();
    input.select();

    const finishEdit = async () => {
        const newName = input.value.trim() || oldName;
        const conflict = window.state.libraries.some(item => item.name === newName && item.name !== oldName);

        if (conflict) {
            input.value = oldName;
            window.showToast('名称重复，已恢复原名称', 'error');
        } else {
            try {
                if (kbId && newName !== oldName && window.apiUpdateKB) {
                    await window.apiUpdateKB(kbId, { name: newName });
                }
                if (window.fetchKnowledgeBases) {
                    await window.fetchKnowledgeBases();
                }
                if (window.state.currentLibraryName === oldName && window.setCurrentLibrary) {
                    window.setCurrentLibrary(newName);
                }
                if (window.renderKbGrid) window.renderKbGrid();
                window.showToast('知识库名称已更新', 'success');
            } catch (err) {
                input.value = oldName;
                window.showToast(err?.message || '知识库名称更新失败', 'error');
            }
        }

        input.readOnly = true;
        input.onblur = null;
        input.onkeydown = null;
    };

    input.onblur = finishEdit;
    input.onkeydown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            input.blur();
        }
    };
}
window.editLibrary = editLibrary;

// 删除知识库逻辑保留对外桥接
function deleteLibrary(event, btn) {
    event.stopPropagation();

    const card = btn.closest('.kb-card');
    const name = card.querySelector('.kb-card-name').value;

    if (window.openDeleteModal) window.openDeleteModal({
        type: 'delete_library',
        libraryName: name
    });
}
window.deleteLibrary = deleteLibrary;

// 页面行为：移动端菜单与启动
const mobileMenuBtn = document.getElementById("mobile-menu-btn");
if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener("click", function () {
        document.body.classList.toggle("mobile-sidebar-open");
    });
}

document.addEventListener("click", function (e) {
    const sidebar = document.querySelector(".sidebar");
    const isMobile = window.innerWidth <= 980;

    if (!isMobile || !sidebar) return;

    const clickedMenuBtn = e.target.closest("#mobile-menu-btn");
    const clickedSidebar = e.target.closest(".sidebar");

    if (!clickedMenuBtn && !clickedSidebar) {
        document.body.classList.remove("mobile-sidebar-open");
    }
});

window.addEventListener("resize", function () {
    if (window.innerWidth > 980) {
        document.body.classList.remove("mobile-sidebar-open");
    }
});

window.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();

    const token = window.getToken?.();
    if (!token) {
        updateProfileUI(null);
        showAuthScreen();
        switchAuthTab('login');
        return;
    }

    try {
        await init();
    } catch (error) {
        window.logout?.();
        updateProfileUI(null);
        showAuthScreen('登录已失效，请重新登录');
        switchAuthTab('login');
    }
});