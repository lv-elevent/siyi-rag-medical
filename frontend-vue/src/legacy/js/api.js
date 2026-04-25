function handleAuthError(response, result) {
    if (response.status === 401) {
        window.logout?.();
        window.showAuthScreen?.('登录已过期，请重新登录');
        throw new Error('未登录或登录过期');
    }
}

function getToken() {
    return localStorage.getItem('rag_token') || '';
}

function setToken(token) {
    localStorage.setItem('rag_token', token);
}

function clearToken() {
    localStorage.removeItem('rag_token');
}

function getAuthHeaders() {
    const token = getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
}

async function register(username, password, phone = "") {
    const response = await fetch(`${window.API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username,
            password,
            phone
        })
    });

    const result = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(result.detail || result.message || '注册失败');
    }

    return result;
}

async function login(username, password) {
    const response = await fetch(`${window.API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username,
            password
        })
    });

    const result = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(result.detail || result.message || '登录失败');
    }

    if (!result.access_token) {
        throw new Error('登录成功但未返回 access_token');
    }

    setToken(result.access_token);

    if (result.user) {
        localStorage.setItem('rag_user', JSON.stringify(result.user));
    }

    return result;
}

async function getCurrentUser() {
    const response = await fetch(`${window.API_BASE_URL}/auth/me`, {
        method: 'GET',
        headers: {
            ...getAuthHeaders()
        }
    });

    const result = await response.json().catch(() => ({}));

    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '获取用户信息失败');
    }

    return result;
}

function logout() {
    clearToken();
    localStorage.removeItem('rag_user');
    localStorage.removeItem('rag_session_id');
}

async function apiFetchKBs() {
    const response = await fetch(`${window.API_BASE_URL}/knowledge`, {
        method: 'GET',
        headers: {
            ...getAuthHeaders()
        }
    });

    const result = await response.json().catch(() => ({}));
    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '获取知识库列表失败');
    }

    return result;
}

async function apiCreateKB(name, description = null) {
    const response = await fetch(`${window.API_BASE_URL}/knowledge`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
        },
        body: JSON.stringify({
            name,
            description
        })
    });

    const result = await response.json().catch(() => ({}));
    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '创建知识库失败');
    }

    return result;
}

async function apiDeleteKB(kbId) {
    const response = await fetch(`${window.API_BASE_URL}/knowledge/${kbId}`, {
        method: 'DELETE',
        headers: {
            ...getAuthHeaders()
        }
    });

    const result = await response.json().catch(() => ({}));
    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '删除知识库失败');
    }

    return result;
}

async function apiUpdateKB(kbId, payload) {
    const response = await fetch(`${window.API_BASE_URL}/knowledge/${kbId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
        },
        body: JSON.stringify(payload || {})
    });

    const result = await response.json().catch(() => ({}));
    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '更新知识库失败');
    }

    return result;
}

async function apiFetchKBFiles(kbId) {
    const response = await fetch(`${window.API_BASE_URL}/knowledge/${kbId}/files`, {
        method: 'GET',
        headers: {
            ...getAuthHeaders()
        }
    });

    const result = await response.json().catch(() => ({}));
    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '获取知识库文件失败');
    }

    return result;
}

async function apiFetchAllFiles() {
    const response = await fetch(`${window.API_BASE_URL}/knowledge/files/all`, {
        method: 'GET',
        headers: {
            ...getAuthHeaders()
        }
    });

    const result = await response.json().catch(() => ({}));
    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '获取全部文件失败');
    }

    return result;
}

async function apiRemoveDocumentFromKB(documentId, knowledgeBaseId) {
    const response = await fetch(`${window.API_BASE_URL}/knowledge/document/remove`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
        },
        body: JSON.stringify({
            document_id: documentId,
            knowledge_base_id: knowledgeBaseId
        })
    });

    const result = await response.json().catch(() => ({}));
    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '移除文档失败');
    }

    return result;
}

async function apiAttachDocumentToKB(documentId, knowledgeBaseId) {
    const response = await fetch(`${window.API_BASE_URL}/knowledge/document/attach`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
        },
        body: JSON.stringify({
            document_id: documentId,
            knowledge_base_id: knowledgeBaseId
        })
    });

    const result = await response.json().catch(() => ({}));
    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '添加文档到知识库失败');
    }

    return result;
}

async function uploadFileToBackend(file, kbId = null) {
    const formData = new FormData();
    formData.append('file', file);
    if (kbId !== null && kbId !== undefined) {
        formData.append('knowledge_base_id', String(kbId));
    }

    const response = await fetch(`${window.API_BASE_URL}/upload`, {
        method: 'POST',
        headers: {
            ...getAuthHeaders()
        },
        body: formData
    });

    let result = null;
    try {
        result = await response.json();
    } catch (error) {
        throw new Error('服务器返回的不是有效 JSON');
    }

    window.handleAuthError?.(response, result);

    if (!response.ok) {
        throw new Error(result.detail || result.message || '上传失败');
    }

    return result;
}

window.getToken = getToken;
window.setToken = setToken;
window.clearToken = clearToken;
window.getAuthHeaders = getAuthHeaders;
window.register = register;
window.login = login;
window.getCurrentUser = getCurrentUser;
window.logout = logout;
window.apiFetchKBs = apiFetchKBs;
window.apiCreateKB = apiCreateKB;
window.apiDeleteKB = apiDeleteKB;
window.apiUpdateKB = apiUpdateKB;
window.apiFetchKBFiles = apiFetchKBFiles;
window.apiFetchAllFiles = apiFetchAllFiles;
window.apiRemoveDocumentFromKB = apiRemoveDocumentFromKB;
window.apiAttachDocumentToKB = apiAttachDocumentToKB;
window.uploadFileToBackend = uploadFileToBackend;
window.handleAuthError = handleAuthError;
