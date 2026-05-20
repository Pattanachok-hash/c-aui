/* ════════════════════════════════════════════════════════════════
   DSC Portal — Misc utilities (toast, alert, formatters)
   ──────────────────────────────────────────────────────────────── */

function showAlert(containerId, message, type = 'error') {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
    if (type !== 'error') setTimeout(() => { el.innerHTML = ''; }, 4000);
}

function clearAlert(containerId) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = '';
}

// ── Toasts ────────────────────────────────────────────────────────
(function injectToastStyles() {
    if (document.getElementById('toast-styles')) return;
    const css = `
.toast-container {
    position: fixed; top: 1rem; right: 1rem; z-index: 100000;
    display: flex; flex-direction: column; gap: .5rem;
    pointer-events: none;
}
.toast {
    background: #fff;
    border-left: 4px solid var(--gray-400);
    border-radius: 10px;
    padding: .7rem 2.25rem .7rem 1rem;
    box-shadow: 0 8px 24px rgba(0,0,0,.16);
    font-size: .88rem; font-weight: 500;
    color: var(--gray-800);
    min-width: 260px; max-width: 380px;
    position: relative; pointer-events: auto; cursor: pointer;
    animation: toast-slide-in .25s ease-out;
    display: flex; align-items: flex-start; gap: .55rem;
    line-height: 1.4;
}
.toast.leave { animation: toast-slide-out .2s ease-in forwards; }
.toast-success { border-left-color: var(--success); }
.toast-error   { border-left-color: var(--danger); }
.toast-warning { border-left-color: var(--warning); }
.toast-info    { border-left-color: var(--info); }
.toast-icon { font-weight: 700; }
.toast-success .toast-icon { color: var(--success); }
.toast-error   .toast-icon { color: var(--danger);  }
.toast-warning .toast-icon { color: var(--warning); }
.toast-info    .toast-icon { color: var(--info);    }
.toast-close {
    position: absolute; top: .3rem; right: .5rem;
    background: none; border: none; cursor: pointer;
    color: var(--gray-400); padding: .15rem .35rem; font-size: .85rem;
}
@keyframes toast-slide-in  { from { transform: translateX(120%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
@keyframes toast-slide-out { to   { transform: translateX(120%); opacity: 0; } }
@media (max-width: 600px) {
    .toast-container { right: .5rem; left: .5rem; }
    .toast { min-width: 0; max-width: none; width: 100%; }
}
    `;
    const s = document.createElement('style');
    s.id = 'toast-styles';
    s.textContent = css;
    document.head.appendChild(s);
})();

function _toastContainer() {
    let c = document.getElementById('toast-container');
    if (!c) {
        c = document.createElement('div');
        c.id = 'toast-container';
        c.className = 'toast-container';
        document.body.appendChild(c);
    }
    return c;
}

function _toast(message, type = 'info', duration = null) {
    const ICONS    = { success: '✓', error: '✗', warning: '⚠', info: 'ℹ' };
    const DEFAULTS = { success: 3000, error: 5000, warning: 4000, info: 3000 };
    duration = duration ?? DEFAULTS[type] ?? 3000;

    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span class="toast-icon">${ICONS[type]}</span><span class="toast-msg"></span><button class="toast-close" type="button">✕</button>`;
    el.querySelector('.toast-msg').textContent = String(message ?? '');

    const remove = () => { el.classList.add('leave'); setTimeout(() => el.remove(), 250); };
    el.querySelector('.toast-close').addEventListener('click', e => { e.stopPropagation(); remove(); });
    el.addEventListener('click', remove);
    setTimeout(remove, duration);

    _toastContainer().appendChild(el);
}

const toast = {
    success: (m, d) => _toast(m, 'success', d),
    error:   (m, d) => _toast(m, 'error',   d),
    warning: (m, d) => _toast(m, 'warning', d),
    info:    (m, d) => _toast(m, 'info',    d),
};

// ── Formatters ────────────────────────────────────────────────────
function formatDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('th-TH', { dateStyle: 'short', timeStyle: 'short' });
}

function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

function isValidPortalEmail(email) {
    const value = String(email || '').trim().toLowerCase();
    if (/^[a-z0-9._%+-]+@wh\.local$/.test(value)) return true;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

// ── Topbar (for authenticated pages) ──────────────────────────────
function renderTopbar() {
    const email = getUserEmail();
    return `
    <div class="topbar">
        <a href="/" class="brand">DSC PORTAL</a>
        <div class="topbar-right">
            <span class="user-email">${escapeHtml(email)}</span>
            <a href="/change-password.html" class="btn btn-secondary btn-sm">
                <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                Password
            </a>
            <button class="btn btn-secondary btn-sm" onclick="logout()">Logout</button>
        </div>
    </div>`;
}
