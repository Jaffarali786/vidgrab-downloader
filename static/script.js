// ===== YouTube & TikTok Downloader Frontend Logic =====

let currentMode = 'single';
let selectedQuality = 1080;
let activeDownloads = new Map();

// ===== MODE SWITCHING =====
function setMode(mode) {
    currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`mode-${mode}`).classList.add('active');
    document.getElementById('single-input').classList.toggle('hidden', mode !== 'single');
    document.getElementById('bulk-input').classList.toggle('hidden', mode !== 'bulk');
    document.getElementById('preview-section').classList.add('hidden');
}

// ===== QUALITY SELECTION =====
function setQuality(q) {
    selectedQuality = q;
    document.querySelectorAll('.quality-chip').forEach(c => {
        c.classList.toggle('active', parseInt(c.dataset.quality) === q);
    });
}

// ===== TOAST NOTIFICATIONS =====
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===== FORMAT HELPERS =====
function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    if (!seconds) return '';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatETA(seconds) {
    if (!seconds || seconds <= 0) return '';
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
}

// ===== FETCH VIDEO INFO =====
async function fetchInfo() {
    const btn = document.getElementById('fetch-btn');
    const url = document.getElementById('url-input').value.trim();

    if (!url) { showToast('Please enter a URL', 'error'); return; }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';

    try {
        const res = await fetch('/api/info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await res.json();

        if (data.error) {
            showToast(data.error, 'error');
            document.getElementById('preview-section').classList.add('hidden');
        } else {
            showPreview(data);
        }
    } catch (e) {
        showToast('Failed to fetch video info', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '🔍 Fetch';
    }
}

// ===== SHOW PREVIEW =====
function showPreview(data) {
    const section = document.getElementById('preview-section');
    const container = document.getElementById('preview-container');

    if (data.type === 'playlist') {
        let html = `<div style="margin-bottom:12px;font-weight:600;">📋 Playlist: ${data.title} (${data.count} videos)</div>`;
        html += '<div class="bulk-preview-list">';
        for (const entry of data.entries.slice(0, 20)) {
            const badge = entry.platform === 'youtube'
                ? '<span class="platform-badge badge-youtube">YT</span>'
                : '<span class="platform-badge badge-tiktok">TT</span>';
            html += `
                <div class="bulk-preview-item">
                    <img class="bulk-thumb" src="${entry.thumbnail || ''}" alt="" onerror="this.style.display='none'">
                    <div class="bulk-info">
                        <div class="bulk-title">${entry.title}</div>
                        <div class="bulk-url">${badge} ${formatDuration(entry.duration)}</div>
                    </div>
                </div>`;
        }
        html += '</div>';
        container.innerHTML = html;
    } else {
        const badge = data.platform === 'youtube'
            ? '<span class="platform-badge badge-youtube">▶ YouTube</span>'
            : '<span class="platform-badge badge-tiktok">♪ TikTok</span>';

        container.innerHTML = `
            <div class="preview-card">
                <img class="preview-thumb" src="${data.thumbnail || ''}" alt="" onerror="this.style.display='none'">
                <div class="preview-info">
                    <div class="preview-title">${data.title}</div>
                    <div class="preview-meta">
                        ${badge}
                        <span class="preview-uploader">${data.uploader || ''}</span>
                        <span class="preview-duration">${formatDuration(data.duration)}</span>
                    </div>
                </div>
            </div>`;
    }

    section.classList.remove('hidden');
}

// ===== START DOWNLOAD =====
async function startDownload() {
    if (currentMode === 'single') {
        const url = document.getElementById('url-input').value.trim();
        if (!url) { showToast('Please enter a URL', 'error'); return; }

        try {
            const res = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, quality: selectedQuality })
            });
            const data = await res.json();
            if (data.download_id) {
                showToast('Download started!', 'success');
                trackDownload(data.download_id, url);
            }
        } catch (e) {
            showToast('Failed to start download', 'error');
        }
    } else {
        // Bulk mode
        const textarea = document.getElementById('bulk-urls');
        const urls = textarea.value.split('\n').map(u => u.trim()).filter(u => u);
        if (urls.length === 0) { showToast('Please enter URLs', 'error'); return; }

        try {
            const res = await fetch('/api/bulk-download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls, quality: selectedQuality })
            });
            const data = await res.json();
            if (data.download_ids) {
                showToast(`${data.download_ids.length} downloads started!`, 'success');
                data.download_ids.forEach((id, i) => trackDownload(id, urls[i] || ''));
            }
        } catch (e) {
            showToast('Failed to start downloads', 'error');
        }
    }
}

// ===== TRACK DOWNLOAD PROGRESS =====
function trackDownload(downloadId, url) {
    const list = document.getElementById('download-list');
    const empty = document.getElementById('empty-state');
    if (empty) empty.classList.add('hidden');

    // Create download item element
    const item = document.createElement('div');
    item.className = 'download-item';
    item.id = `dl-${downloadId}`;
    item.innerHTML = `
        <div class="download-item-header">
            <div class="download-item-title" id="dl-title-${downloadId}">Fetching info...</div>
            <div class="download-item-status">
                <div class="status-dot starting" id="dl-dot-${downloadId}"></div>
                <span class="status-text starting" id="dl-status-${downloadId}">Starting</span>
            </div>
        </div>
        <div class="progress-bar-container">
            <div class="progress-bar" id="dl-bar-${downloadId}" style="width:0%"></div>
        </div>
        <div class="download-item-footer">
            <span class="progress-text" id="dl-progress-${downloadId}">0%</span>
            <span class="download-speed" id="dl-speed-${downloadId}"></span>
            <div class="download-actions" id="dl-actions-${downloadId}"></div>
        </div>`;
    list.prepend(item);

    updateDownloadCount();

    // SSE for progress
    const eventSource = new EventSource(`/api/progress/${downloadId}`);
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateDownloadItem(downloadId, data);

        if (data.status === 'completed' || data.status === 'error') {
            eventSource.close();
            if (data.status === 'completed') {
                showToast(`Downloaded: ${data.title || 'Video'}`, 'success');
            } else {
                showToast(`Error: ${data.error || 'Unknown error'}`, 'error');
            }
        }
    };
    eventSource.onerror = () => eventSource.close();
}

// ===== UPDATE DOWNLOAD ITEM =====
function updateDownloadItem(id, data) {
    const title = document.getElementById(`dl-title-${id}`);
    const dot = document.getElementById(`dl-dot-${id}`);
    const status = document.getElementById(`dl-status-${id}`);
    const bar = document.getElementById(`dl-bar-${id}`);
    const progress = document.getElementById(`dl-progress-${id}`);
    const speed = document.getElementById(`dl-speed-${id}`);
    const actions = document.getElementById(`dl-actions-${id}`);

    if (!title) return;

    if (data.title) title.textContent = data.title;
    if (data.url && !data.title) title.textContent = data.url.substring(0, 50) + '...';

    // Update status
    const s = data.status || 'starting';
    dot.className = `status-dot ${s}`;
    status.className = `status-text ${s}`;
    status.textContent = s;

    // Update progress
    const pct = data.progress || 0;
    bar.style.width = `${pct}%`;
    if (s === 'completed') bar.classList.add('completed');

    // Progress text
    if (s === 'downloading') {
        const dl = formatBytes(data.downloaded || 0);
        const total = formatBytes(data.total || 0);
        progress.textContent = `${pct}% · ${dl} / ${total}`;
        if (data.speed) speed.textContent = `${formatBytes(data.speed)}/s`;
        if (data.eta) speed.textContent += ` · ETA ${formatETA(data.eta)}`;
    } else if (s === 'completed') {
        progress.textContent = '100% · Complete';
        speed.textContent = '';
        if (data.filename) {
            actions.innerHTML = `<a href="/api/file/${encodeURIComponent(data.filename)}" class="btn-download-file" download>💾 Save</a>`;
        }
    } else if (s === 'error') {
        progress.textContent = data.error || 'Download failed';
        speed.textContent = '';
    } else if (s === 'processing') {
        progress.textContent = 'Merging audio & video...';
        speed.textContent = '';
    } else {
        progress.textContent = 'Starting...';
    }
}

function updateDownloadCount() {
    const count = document.getElementById('download-list').children.length;
    const countEl = document.getElementById('download-count');
    if (countEl) countEl.textContent = count;
}

// ===== KEYBOARD SHORTCUTS =====
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        if (document.activeElement.id === 'url-input') {
            e.preventDefault();
            fetchInfo();
        }
    }
});

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
    setMode('single');
    setQuality(1080);
});
