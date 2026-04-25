function showToast(message, type = 'success') {
    const toast = document.getElementById('custom-toast');
    if (!toast) return;

    toast.textContent = message;
    toast.className = `toast show ${type}`;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => {
        toast.className = 'toast';
    }, 2200);
}

window.showToast = showToast;
