function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('show');
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('show');
}

// 挂到 window 上供原 script.js 使用
window.openModal = openModal;
window.closeModal = closeModal;

// ===== 以下为通用输入与删除模态框逻辑（从 script.js 迁移） =====

function openInputModal({
    title = '请输入内容',
    label = '请输入',
    placeholder = '',
    defaultValue = '',
    confirmText = '确定',
    onConfirm
}) {
    const modal = document.getElementById('inputModal');
    if (!modal) return;
    const titleEl = document.getElementById('inputModalTitle');
    const labelEl = document.getElementById('inputModalLabel');
    const inputEl = document.getElementById('inputModalField');
    const errorEl = document.getElementById('inputModalError');
    const confirmBtn = document.getElementById('confirmInputBtn');
    const cancelBtn = document.getElementById('cancelInputBtn');

    titleEl.innerText = title;
    labelEl.innerText = label;
    inputEl.placeholder = placeholder;
    inputEl.value = defaultValue;
    errorEl.innerText = '';
    confirmBtn.innerText = confirmText;

    modal.style.display = 'flex';

    setTimeout(() => {
        inputEl.focus();
        inputEl.select();
    }, 0);

    const close = () => {
        modal.style.display = 'none';
        errorEl.innerText = '';
        confirmBtn.onclick = null;
        inputEl.onkeydown = null;
    };

    cancelBtn.onclick = close;

    confirmBtn.onclick = async () => {
        const value = inputEl.value.trim();

        try {
            const result = await onConfirm?.(value);
            if (result === false) return;
            close();
        } catch (error) {
            errorEl.innerText = error.message || '操作失败';
        }
    };

    inputEl.onkeydown = async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            confirmBtn.click();
        }
    };
}

function openDeleteModal(data) {
    const modal = document.getElementById('deleteModal');
    if (!modal) return;

    // 把数据挂到 DOM（替代全局变量）
    modal.dataset.deletePayload = JSON.stringify(data);

    const textEl = document.getElementById('deleteModalText');

    if (data.type === 'delete_library') {
        textEl.innerText = `确定要删除知识库「${data.libraryName}」吗？`;
    } else if (data.type === 'remove') {
        textEl.innerText = `确定从「${data.libraryName}」中移除文件「${data.fileName}」吗？`;
    } else if (data.type === 'delete_document') {
        textEl.innerText = `确定要删除文档「${data.filename}」吗？\n删除后将无法恢复。`;
    }

    modal.style.display = 'flex';
}

// 挂到 window 以兼容旧调用方式
window.openInputModal = openInputModal;
window.openDeleteModal = openDeleteModal;

// 绑定删除模态框的确认/取消按钮处理（保持与原逻辑一致）
(function bindDeleteModalHandlers() {
    const cancelBtn = document.getElementById('cancelDeleteBtn');
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            const modal = document.getElementById('deleteModal');
            if (!modal) return;
            modal.style.display = 'none';
            modal.dataset.deletePayload = '';
        });
    }

    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {
            const modal = document.getElementById('deleteModal');
            if (!modal) return;
            const payloadStr = modal.dataset.deletePayload;
            if (!payloadStr) return;

            const data = JSON.parse(payloadStr);

            try {

                switch (data.type) {

                    case 'delete_library': {
                        const { libraryName } = data;

                        window.state.libraries = window.state.libraries.filter(
                            item => item.name !== libraryName
                        );

                        if (window.state.currentLibraryName === libraryName) {
                            window.setCurrentLibrary(null);
                        }

                        window.persistLibraries();
                        window.renderKbGrid();

                        window.showToast(`知识库「${libraryName}」已删除`, 'success');
                        break;
                    }

                    case 'remove': {
                        const { libraryName, fileName, documentId } = data;
                        if (!documentId) {
                            throw new Error('缺少 document_id');
                        }

                        await window.apiRemoveDocumentFromKB(
                            documentId,
                            window.state.currentKbId || null
                        );

                        if (window.state.currentKbId) {
                            await window.openLibraryById(window.state.currentKbId, libraryName);
                        }
                        await window.fetchKnowledgeFiles();
                        window.renderKnowledgeFiles();

                        window.renderKbGrid();
                        window.showToast(`已移除：${fileName}`, 'success');
                        break;
                    }

                    case 'delete_document': {
                        const { documentId, filename } = data;
                        const numericDocumentId = Number(documentId);
                    
                        if (!Number.isInteger(numericDocumentId) || numericDocumentId <= 0) {
                            throw new Error('document_id 非法');
                        }
                    
                        const response = await fetch(`${window.API_BASE_URL}/knowledge/document/delete`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                ...window.getAuthHeaders()
                            },
                            body: JSON.stringify({ document_id: numericDocumentId })
                        });
                    
                        const result = await response.json().catch(() => ({}));
                        window.handleAuthError?.(response, result);
                    
                        if (!response.ok) throw new Error(result.detail || '删除失败');
                    
                        await window.fetchKnowledgeFiles();
                        window.renderKnowledgeFiles();
                        window.updateUI();
                    
                        window.showToast(`文档"${filename}"删除成功`, 'success');
                        break;
                    }
                }

            } catch (error) {
                window.showToast(error.message || '删除失败', 'error');
            }

            // ✅ 收尾
            modal.style.display = 'none';
            modal.dataset.deletePayload = '';
        });
    }
})();

