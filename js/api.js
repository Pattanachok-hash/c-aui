/* ════════════════════════════════════════════════════════════════
   C-Aui Portal — Backend API wrapper
   ──────────────────────────────────────────────────────────────── */

// Backend URL: api.c-aui.com in production, override with ?api=... query for local dev.
const API_BASE = (() => {
    const override = new URLSearchParams(window.location.search).get('api');
    if (override) return override.replace(/\/$/, '');
    if (window.location.hostname === 'localhost' || window.location.hostname.startsWith('127.')) {
        return 'http://localhost:8000';
    }
    return 'https://api.c-aui.com';
})();


async function apiFetch(path, options = {}) {
    const token = await getAccessToken();
    const isFormData = options.body instanceof FormData;

    const headers = {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
    };

    console.log('[PORTAL] apiFetch →', {
        url: `${API_BASE}${path}`,
        method: options.method || 'GET',
        has_token: !!token,
        token_prefix: token ? token.slice(0, 16) + '...' : null,
    });

    let res;
    try {
        res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    } catch (netErr) {
        console.error('[PORTAL] apiFetch network FAIL', { url: `${API_BASE}${path}`, err: netErr?.message || netErr });
        throw netErr;
    }
    console.log('[PORTAL] apiFetch ←', { url: `${API_BASE}${path}`, status: res.status });

    // Refresh + retry once on 401
    if (res.status === 401) {
        console.warn('[PORTAL] apiFetch 401 → attempting refresh');
        const { data, error } = await sb.auth.refreshSession();
        console.log('[PORTAL] refreshSession', { ok: !error && !!data?.session, error: error?.message });
        if (!error && data.session) {
            const headers2 = { ...headers, Authorization: `Bearer ${data.session.access_token}` };
            res = await fetch(`${API_BASE}${path}`, { ...options, headers: headers2 });
            console.log('[PORTAL] apiFetch retry ←', { status: res.status });
        }
        if (res.status === 401) {
            console.error('[PORTAL] apiFetch retry still 401 → signOut + redirect');
            await sb.auth.signOut();
            window.location.href = '/login.html';
            throw new Error('Session expired');
        }
    }

    const text = await res.text();
    const data = text ? (() => { try { return JSON.parse(text); } catch { return text; } })() : null;

    if (!res.ok) {
        const msg = formatApiError(data, res.status);
        const err = new Error(msg);
        err.status = res.status;
        throw err;
    }
    return data;
}

function formatApiError(data, status) {
    if (typeof data === 'string' && data) return data;
    const detail = data && typeof data === 'object' ? data.detail : null;
    if (typeof detail === 'string' && detail) return detail;
    if (Array.isArray(detail) && detail.length) {
        return detail.map(item => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object') return item.msg || item.message || JSON.stringify(item);
            return String(item);
        }).join(', ');
    }
    if (detail && typeof detail === 'object') {
        return detail.msg || detail.message || JSON.stringify(detail);
    }
    return `HTTP ${status}`;
}

const api = {
    get:    (path)         => apiFetch(path),
    post:   (path, body)   => apiFetch(path, { method: 'POST',   body: body ? JSON.stringify(body) : null }),
    patch:  (path, body)   => apiFetch(path, { method: 'PATCH',  body: body ? JSON.stringify(body) : null }),
    delete: (path)         => apiFetch(path, { method: 'DELETE' }),
};
