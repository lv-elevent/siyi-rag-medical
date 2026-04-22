// KB 模块：知识库管理功能
// 包含 renderKbGrid、createNewLibrary、openLibrary、removeFromLibrary、deleteDocument、setCurrentLibrary、findLibraryByName、persistLibraries

window.state.kbs = Array.isArray(window.state.kbs) ? window.state.kbs : [];
window.state.currentKbId = window.state.currentKbId || null;

/**
 * 渲染知识库网格
 */
function renderKbGrid() {
    if (!window.elements.kbGrid) return;

    window.elements.kbGrid.innerHTML = (window.state.kbs || []).map(kb => {
        const activeClass = String(window.state.currentKbId || '') === String(kb.id) ? 'active' : '';
        return `
            <div class="kb-card ${activeClass}" data-id="${kb.id}" data-name="${window.escapeHtml(kb.name || '')}">
                <div class="kb-card-icon">📂</div>
                <input type="text" class="kb-card-name" value="${window.escapeAttr(kb.name || '')}" readonly>
                <div class="kb-card-actions">
                    <button class="kb-btn edit" type="button" onclick="editLibrary(event,this)">编辑</button>
                    <button class="kb-btn del" type="button" onclick="deleteLibrary(event,this)">删除</button>
                </div>
            </div>
        `;
    }).join('');

    document.querySelectorAll('.kb-card').forEach(card => {
        card.addEventListener('click', () => {
            const kbId = card.dataset.id;
            const name = card.querySelector('.kb-card-name').value;
            window.setCurrentLibrary(name);
            window.openLibraryById(kbId, name);
        });
    });
}

/**
 * 创建新知识库
 */
function createNewLibrary() {
    window.openInputModal({
        title: '新建知识库',
        label: '请输入知识库名称',
        placeholder: '例如：心内科知识库',
        confirmText: '创建',
        onConfirm: async (value) => {
            if (!value) {
                throw new Error('知识库名称不能为空');
            }

            const finalName = value.trim();
            await window.apiCreateKB(finalName, null);
            await window.fetchKnowledgeBases();
            window.showToast(`知识库「${finalName}」创建成功`, 'success');
        }
    });
}

/**
 * 打开知识库
 */
function openLibrary(name) {
    const kb = (window.state.kbs || []).find(item => item.name === name);
    if (!kb) return;
    return openLibraryById(kb.id, kb.name);
}

async function openLibraryById(kbId, kbName) {
    if (!window.elements.libTitle || !window.elements.libFiles || !window.elements.libraryTip) return;

    window.state.currentKbId = kbId ? Number(kbId) : null;
    window.setCurrentLibrary(kbName);
    window.elements.libTitle.textContent = `${kbName} · 文件列表`;
    window.elements.libraryTip.innerHTML =
        `当前正在查看「<strong>${window.escapeHtml(kbName)}</strong>」，可在此查看文档、移除文件，或继续通过左侧拖拽的方式添加文档。`;

    const result = await window.apiFetchKBFiles(kbId);
    const files = Array.isArray(result.files) ? result.files : [];
    window.state.knowledgeFiles = files;
    if (!files.length) {
        window.elements.libFiles.innerHTML = `
            <div style="text-align:center; padding:24px; color:var(--text-secondary); border:1px dashed var(--border-color); border-radius:14px;">
                该知识库暂无文件
            </div>
        `;
    } else {
        window.elements.libFiles.innerHTML = files.map(file => `
            <div class="lib-file-item" title="${window.escapeHtml(file.filename || '未命名文档')}">
                <div class="lib-file-name" title="${window.escapeHtml(file.filename || '未命名文档')}">${window.escapeHtml(file.filename || '未命名文档')}</div>
                <div class="lib-file-actions">
                    <button
                        type="button"
                        class="lib-remove-btn"
                        onclick="removeFromLibrary('${window.escapeJs(kbName)}','${window.escapeJs(file.filename || '未命名文档')}','${window.escapeJs(String(file.document_id || ''))}')"
                    >
                        移除
                    </button>
                </div>
            </div>
        `).join('');
    }

    setTimeout(() => {
        const btn = document.getElementById('addFileToLibBtn');
        if (btn) {
            btn.onclick = () => {
                const libraryName = window.state.currentLibraryName;
                if (!libraryName) {
                    window.showToast('请先选择知识库', 'error');
                    return;
                }
                window.openSelectFileModal(libraryName);
            };
        }
    }, 0);

    window.openModal('libraryModal');
}

/**
 * 从知识库中移除文件
 */
function removeFromLibrary(libraryName, fileName, documentId = null) {
    window.openDeleteModal({
        type: 'remove',
        libraryName,
        fileName,
        documentId
    });
}

/**
 * 打开选择文件弹窗
 */
function openSelectFileModal(libraryName) {
    const library = window.findLibraryByName(libraryName);
    if (!library) {
        window.showToast('知识库不存在', 'error');
        return;
    }

    const allFiles = Array.isArray(window.state.allKnowledgeFiles) ? window.state.allKnowledgeFiles : [];
    const existingDocIds = new Set((window.state.knowledgeFiles || []).map(f => String(f.document_id)));
    const availableFiles = allFiles.filter(file => !existingDocIds.has(String(file.document_id)));

    const container = document.getElementById('selectFileList');
    if (!container) return;

    if (!availableFiles.length) {
        container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-secondary);">没有可添加的文件</div>`;
    } else {
        container.innerHTML = availableFiles.map(file => `
            <label style="display:flex; align-items:center; gap:8px; padding:8px 4px; cursor:pointer;">
                <input type="checkbox" value="${window.escapeHtml(String(file.document_id))}">
                <span title="${window.escapeHtml(file.filename || '未命名文档')}" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${window.escapeHtml(file.filename || '未命名文档')}</span>
            </label>
        `).join('');
    }

    window.state.tempSelectLibrary = libraryName;
    window.openModal('selectFileModal');
}

/**
 * 删除文档
 */
async function deleteDocument(documentId, filename) {
    window.openDeleteModal({
        type: 'delete_document',
        documentId,
        filename,
        // 新增：确认后调用真实请求
        onConfirm: () => confirmDeleteDocument(documentId)
    });
}

/**
 * 设置当前知识库
 */
function setCurrentLibrary(name) {
    window.state.currentLibraryName = name || null;
    const targetKb = (window.state.kbs || []).find(item => item.name === window.state.currentLibraryName);
    window.state.currentKbId = targetKb ? targetKb.id : null;
    localStorage.setItem('rag_current_library', window.state.currentLibraryName || '');

    if (window.elements.currentKbBadge) {
        window.elements.currentKbBadge.textContent = `当前知识库：${window.state.currentLibraryName || '未选择'}`;
    }
    if (window.elements.sidebarCurrentKb) {
        window.elements.sidebarCurrentKb.textContent = window.state.currentLibraryName || '未选择';
    }

    window.renderKbGrid();
}

/**
 * 按名称查找知识库
 */
function findLibraryByName(name) {
    const kb = (window.state.kbs || []).find(item => item.name === name);
    if (!kb) return null;
    return {
        ...kb,
        files: Array.isArray(kb.files) ? kb.files : []
    };
}

/**
 * 持久化知识库
 */
function persistLibraries() {
    // 兼容旧调用，知识库主数据源已切换为后端 API
    return;
}

async function fetchKnowledgeBases() {
    const result = await window.apiFetchKBs();
    const kbs = Array.isArray(result.knowledge_bases) ? result.knowledge_bases : [];
    window.state.kbs = kbs;
    window.state.libraries = kbs.map(kb => ({
        name: kb.name,
        icon: '📂',
        files: []
    }));

    const storedName = window.state.currentLibraryName || localStorage.getItem('rag_current_library') || null;
    let current = null;

    if (window.state.currentKbId) {
        current = kbs.find(kb => String(kb.id) === String(window.state.currentKbId)) || null;
    }

    if (!current && storedName) {
        current = kbs.find(kb => kb.name === storedName) || null;
    }

    if (!current) {
        current = kbs[0] || null;
    }

    window.state.currentKbId = current ? current.id : null;
    window.state.currentLibraryName = current ? (current.name || null) : null;
    localStorage.setItem('rag_current_library', window.state.currentLibraryName || '');

    window.renderKbGrid();
}

// 挂载到 window 上供外部调用
window.renderKbGrid = renderKbGrid;
window.createNewLibrary = createNewLibrary;
window.openLibrary = openLibrary;
window.removeFromLibrary = removeFromLibrary;
window.openSelectFileModal = openSelectFileModal;
window.deleteDocument = deleteDocument;
window.setCurrentLibrary = setCurrentLibrary;
window.findLibraryByName = findLibraryByName;
window.persistLibraries = persistLibraries;
window.fetchKnowledgeBases = fetchKnowledgeBases;
window.openLibraryById = openLibraryById;

// ===== 知识库相关的检索与文件列表逻辑（从 script.js 迁移） =====

let isFetchingKnowledge = false;

async function fetchKnowledgeFiles() {
    if (window.state.isStreaming) return;

    if (isFetchingKnowledge) {
        console.log("⛔ 防重复 fetchKnowledgeFiles");
        return;
    }

    isFetchingKnowledge = true;

    try {
        const kbId = window.state.currentKbId;
        const allResult = await window.apiFetchAllFiles();
        const allFiles = Array.isArray(allResult.files) ? allResult.files : [];
        let files = allFiles;
        if (kbId) {
            const result = await window.apiFetchKBFiles(kbId);
            files = Array.isArray(result.files) ? result.files : [];
        }

        window.state.knowledgeFiles = allFiles;
        window.state.currentKbFiles = files;
        window.state.allKnowledgeFiles = allFiles;

        window.updateState({
            knowledgeFiles: allFiles
        });

        if (window.state.selectedDocumentId) {
            const stillExists = allFiles.some(
                file => String(file.document_id) === String(window.state.selectedDocumentId)
            );
            if (!stillExists) {
                window.state.selectedDocumentId = null;
                window.state.selectedDocumentName = null;
            }
        }

        if (!window.state.selectedDocumentId && allFiles.length === 1) {
            window.state.selectedDocumentId = String(allFiles[0].document_id);
            window.state.selectedDocumentName = allFiles[0].filename;
        }

        if (allFiles.length > 0) {
            window.state.systemStatus = 'ready';
        } else {
            window.state.systemStatus = 'empty';
        }

        window.syncFilesToLibraries(allFiles);
        window.renderKnowledgeFiles(window.elements.fileSearch?.value || '');
        window.updateSelectedDocumentDisplay();
        window.updateKnowledgeBaseStatus({
            status: allFiles.length > 0 ? 'ready' : 'empty',
            filename: window.state.selectedDocumentName || ''
        });
        window.renderKbGrid();
        window.updateUI();
        window.syncKbToggleButtonText();

        console.log(`[前端] 获取知识文档列表成功: ${files.length} 个文件`);
    } catch (error) {
        console.error(`[前端] 获取知识文档列表失败: ${error.message}`);

        window.updateState({
            knowledgeFiles: [],
            systemStatus: 'empty'
        });

        window.state.selectedDocumentId = null;
        window.state.selectedDocumentName = null;

        window.renderKnowledgeFiles(window.elements.fileSearch?.value || '');
        window.updateSelectedDocumentDisplay();

        window.updateKnowledgeBaseStatus({
            status: 'empty',
            filename: ''
        });

        window.renderKbGrid();
        window.updateUI();
        window.syncKbToggleButtonText();
    } finally {
        isFetchingKnowledge = false;
    }
}

function syncFilesToLibraries(files) {
    const existingNames = new Set((files || []).map(f => f.filename));
    window.state.libraries = (window.state.kbs || []).map(kb => ({
        name: kb.name,
        icon: '📂',
        files: Array.from(existingNames),
    }));
}

async function deleteLibrary(event, btn) {
    event.stopPropagation();
    const card = btn.closest('.kb-card');
    const kbId = card?.dataset?.id;
    const kbName = card?.dataset?.name || '';
    if (!kbId) return;

    const ok = window.confirm(`确定要删除知识库「${kbName}」吗？`);
    if (!ok) return;

    await window.apiDeleteKB(kbId);
    await window.fetchKnowledgeBases();
    window.showToast(`知识库「${kbName}」已删除`, 'success');
}

window.deleteLibrary = deleteLibrary;

function syncKbToggleButtonText() {
    if (!window.elements.toggleKbFilesButton) return;

    window.elements.toggleKbFilesButton.textContent = window.state.kbFilesPanelOpen
        ? '收起知识文档'
        : '查看知识文档';
}

function renderKnowledgeFiles(filter = '') {
    if (!window.elements.kbFilesList) return;

    const files = window.state.knowledgeFiles || [];
    const keyword = String(filter || '').trim().toLowerCase();
    const filteredFiles = files.filter(file => {
        const filename = (file.filename || '').toLowerCase();
        return filename.includes(keyword);
    });

    window.elements.kbFilesList.innerHTML = '';

    if (filteredFiles.length === 0) {
        window.elements.kbFilesList.innerHTML = '<div class="kb-file-empty">未找到匹配文档</div>';
        return;
    }

    filteredFiles.forEach(file => {
        const item = document.createElement('div');

        const fileDocumentId = String(file.document_id);
        const currentSelectedId = window.state.selectedDocumentId ? String(window.state.selectedDocumentId) : null;
        const isSelected = currentSelectedId && fileDocumentId === currentSelectedId;
        const displayName = file.filename || '未命名文档';

        item.className = `kb-file-item ${isSelected ? 'selected' : ''}`;
        item.setAttribute('data-document-id', fileDocumentId);
        item.setAttribute('draggable', 'true');
        item.dataset.filename = displayName;
        item.title = displayName;

        item.innerHTML = `
            <div class="kb-file-main">
                <div class="kb-file-title-only">
                    <div class="kb-file-name" title="${window.escapeHtml(displayName)}">${window.escapeHtml(displayName)}</div>
                </div>
            </div>
            <button class="kb-file-delete-btn" type="button">删除</button>
        `;

        item.addEventListener('click', () => {
            window.state.selectedDocumentId = String(file.document_id);
            window.state.selectedDocumentName = displayName;

            renderKnowledgeFiles(window.elements.fileSearch?.value || '');
            updateSelectedDocumentDisplay();
            updateKnowledgeBaseStatus({
                status: 'ready',
                filename: window.state.selectedDocumentName
            });
        });

        item.addEventListener('dragstart', (e) => {
            const fileName = item.dataset.filename || item.textContent.trim();
            e.dataTransfer.setData('text/plain', fileName);
        });

        const deleteBtn = item.querySelector('.kb-file-delete-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (event) => {
                event.stopPropagation();
                window.deleteDocument(file.document_id, displayName);
            });
        }

        window.elements.kbFilesList.appendChild(item);
    });
}

function updateSelectedDocumentDisplay() {
    if (!window.elements.selectedDoc) return;
    window.elements.selectedDoc.style.display = 'none';
}

function updateKnowledgeBaseStatus(knowledgeData = null) {
    if (!window.elements.kbStatus) return;

    const filesCount = Array.isArray(window.state.knowledgeFiles)
        ? window.state.knowledgeFiles.length
        : 0;

    const hasKnowledge =
        filesCount > 0 ||
        knowledgeData?.status === 'ready';

    if (!hasKnowledge) {
        window.elements.kbStatus.innerHTML = `
            <div class="status-item"><strong>状态：</strong>暂无文档</div>
            <div class="status-item"><strong>知识库文档数：</strong>0</div>
        `;
        return;
    }

    window.elements.kbStatus.innerHTML = `
        <div class="status-item"><strong>状态：</strong>已加载，可进行问答</div>
        <div class="status-item"><strong>知识库文档数：</strong>${filesCount}</div>
    `;
}

async function fetchKnowledgeBaseStatus() {
    try {
        const response = await fetch(`${window.API_BASE_URL}/knowledge/status`, {
            method: 'GET',
            headers: {
                ...window.getAuthHeaders?.()
            }
        });

        let result = null;
        try {
            result = await response.json();
        } catch (error) {
            throw new Error('服务器返回的不是有效 JSON');
        }

        window.handleAuthError?.(response, result);

        if (!response.ok) {
            throw new Error(result.detail || '获取知识库状态失败');
        }

        window.updateKnowledgeBaseStatus(result);
    } catch (error) {
        console.error('获取知识库状态失败:', error);
    }
}

function toggleKnowledgeFilesPanel() {
    window.state.kbFilesPanelOpen = !window.state.kbFilesPanelOpen;

    if (window.elements.kbFilesPanel) {
        window.elements.kbFilesPanel.style.display = window.state.kbFilesPanelOpen ? 'block' : 'none';
    }

    window.syncKbToggleButtonText();
}

// 挂载到 window 以供其他模块使用
window.fetchKnowledgeFiles = fetchKnowledgeFiles;
window.renderKnowledgeFiles = renderKnowledgeFiles;
window.updateKnowledgeBaseStatus = updateKnowledgeBaseStatus;
window.fetchKnowledgeBaseStatus = fetchKnowledgeBaseStatus;
window.toggleKnowledgeFilesPanel = toggleKnowledgeFilesPanel;
window.syncKbToggleButtonText = syncKbToggleButtonText;
window.syncFilesToLibraries = syncFilesToLibraries;
window.updateSelectedDocumentDisplay = updateSelectedDocumentDisplay;