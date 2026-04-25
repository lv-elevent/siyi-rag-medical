import './utils.js';
import './api.js';
import './modules/modal.js';
import './components/toast.js';
import './modules/upload.js';
import './modules/chat.js';
import './modules/agent.js';
import './modules/kb.js';

if (typeof window.fetchKnowledgeFiles === 'function') {
    const _originalFetchKnowledgeFiles = window.fetchKnowledgeFiles;
    let _kbBootstrapped = false;
    window.fetchKnowledgeFiles = async (...args) => {
        if (!_kbBootstrapped && typeof window.fetchKnowledgeBases === 'function') {
            _kbBootstrapped = true;
            await window.fetchKnowledgeBases();
        }
        return _originalFetchKnowledgeFiles(...args);
    };
}

console.log('[frontend] app.js loaded');
