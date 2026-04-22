function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeAttr(text) {
    return escapeHtml(text);
}

function escapeJs(str) {
    return String(str)
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'");
}

function formatText(text) {
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function groupSourcesByFile(sources = []) {
    const map = new Map();

    sources.forEach(s => {
        const filename = s?.filename || '未知文件';
        const chunkIndex = Number(s?.chunk_index ?? 0) + 1;

        if (!map.has(filename)) {
            map.set(filename, []);
        }

        map.get(filename).push(chunkIndex);
    });

    return Array.from(map.entries()).map(([filename, chunks]) => ({
        filename,
        chunks: [...new Set(chunks)].sort((a, b) => a - b)
    }));
}

// 挂到 window 上供原 script.js 使用
window.escapeHtml = escapeHtml;
window.escapeAttr = escapeAttr;
window.escapeJs = escapeJs;
window.formatText = formatText;
window.groupSourcesByFile = groupSourcesByFile;