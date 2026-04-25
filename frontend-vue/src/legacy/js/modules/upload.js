function handleFileUpload(e) {
    const file = e.target.files[0];

    if (!file) {
        window.showUploadStatus('请选择文件', 'error');
        return;
    }

    window.handleFile(file);

    if (window.elements.pdfUpload) {
        window.elements.pdfUpload.value = '';
    }
}

async function handleFile(file) {
    if (!file) {
        window.showToast('请选择文件', 'error');
        return;
    }

    const allowedTypes = ['pdf', 'txt', 'md', 'docx'];
    const ext = file.name.split('.').pop().toLowerCase();

    if (!allowedTypes.includes(ext)) {
        window.showToast('仅支持 PDF / TXT / MD / DOCX 文件', 'error');
        return;
    }

    window.setUploadAreaDisabled(true);

    window.updateState({
        uploadedFile: file,
        uploadedFileName: file.name,
        uploadStatus: 'uploading'
    });

    window.showUploadStatus(`正在上传：${file.name}`, 'idle');

    try {
        const result = await window.uploadFileToBackend(file, window.state.currentKbId || null);

        if (result.status === 'success') {
            window.updateState({
                uploadedFileName: result.filename || file.name,
                uploadStatus: 'success'
            });

            window.renderUploadPreview([result.filename || file.name]);
            window.showUploadStatus(`上传成功：${result.filename || file.name}`, 'success');
            window.showToast(`文件 "${result.filename || file.name}" 上传成功`, 'success');

            try {
                await window.fetchKnowledgeFiles();
                window.renderKnowledgeFiles(window.elements.fileSearch?.value || '');
                window.updateKnowledgeBaseStatus();
            } catch (refreshError) {
                console.error('上传成功，但刷新知识库列表失败:', refreshError);
            }

            setTimeout(() => {
                window.showUploadStatus('', 'idle');
                if (window.elements.uploadPreview) {
                    window.elements.uploadPreview.innerHTML = '';
                }
                window.closeModal('uploadModal');
            }, 900);
        } else {
            window.updateState({
                uploadStatus: 'error',
                systemStatus: 'empty'
            });

            window.showUploadStatus(result.message || '上传失败', 'error');
            window.showToast(result.message || '上传失败', 'error');
        }
    } catch (error) {
        window.updateState({
            uploadStatus: 'error',
            systemStatus: 'empty'
        });

        window.showUploadStatus(error.message || '上传失败，请重试', 'error');
        window.showToast(error.message || '上传失败，请重试', 'error');
        console.error('上传失败:', error);
    } finally {
        window.setUploadAreaDisabled(false);

        setTimeout(() => {
            if (window.state.uploadStatus !== 'uploading') {
                window.updateState({ uploadStatus: 'idle' });
            }
        }, 1000);
    }
}

function renderUploadPreview(fileNames) {
    if (!window.elements.uploadPreview) return;
    const names = Array.isArray(fileNames) ? fileNames : [];
    window.elements.uploadPreview.innerHTML = names.map(name => `
        <div class="upload-pill" title="${window.escapeHtml(name)}">${window.escapeHtml(name)}</div>
    `).join('');
}

function showUploadStatus(message, type = 'idle') {
    if (!window.elements.uploadStatus) return;
    window.elements.uploadStatus.textContent = message;
    window.elements.uploadStatus.className = `upload-status ${type}`;
}

function setUploadAreaDisabled(disabled) {
    if (!window.elements.uploadArea) return;

    window.elements.uploadArea.style.pointerEvents = disabled ? 'none' : 'auto';
    window.elements.uploadArea.style.opacity = disabled ? '0.7' : '1';
}

window.handleFileUpload = handleFileUpload;
window.handleFile = handleFile;
window.renderUploadPreview = renderUploadPreview;
window.showUploadStatus = showUploadStatus;
window.setUploadAreaDisabled = setUploadAreaDisabled;
