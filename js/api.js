/* ════════════════════════════════════════════════════════════════
   C-Aui Portal — Backend API wrapper
   ──────────────────────────────────────────────────────────────── */

// Backend URL: same-origin in production; ?api=... is allowed only on local dev.
const LEGACY_API_BASE = 'https://api.c-aui.com';
const API_BASE = (() => {
    const isLocal =
        window.location.hostname === 'localhost' ||
        window.location.hostname.startsWith('127.');
    const override = new URLSearchParams(window.location.search).get('api');
    if (isLocal && override) return override.replace(/\/$/, '');
    if (isLocal) {
        return 'http://localhost:8000';
    }
    return '';
})();

function apiUrl(base, path) {
    return `${base}${path}`;
}


async function apiFetch(path, options = {}) {
    const token = await getAccessToken();
    const isFormData = options.body instanceof FormData;

    const headers = {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
    };

    let activeBase = API_BASE;
    console.log('[PORTAL] apiFetch →', {
        url: apiUrl(activeBase, path),
        method: options.method || 'GET',
        has_token: !!token,
    });

    let res;
    try {
        res = await fetch(apiUrl(activeBase, path), { ...options, headers });
    } catch (netErr) {
        console.error('[PORTAL] apiFetch network FAIL', { url: apiUrl(activeBase, path), err: netErr?.message || netErr });
        throw netErr;
    }
    console.log('[PORTAL] apiFetch ←', { url: apiUrl(activeBase, path), status: res.status });

    // During DNS cutover, GitHub Pages may still serve the frontend and return
    // 404/405 for /api/*. Fallback keeps the old split-host deployment working.
    if (API_BASE === '' && (res.status === 404 || res.status === 405)) {
        activeBase = LEGACY_API_BASE;
        console.warn('[PORTAL] same-origin API unavailable → falling back to legacy API host');
        res = await fetch(apiUrl(activeBase, path), { ...options, headers });
        console.log('[PORTAL] apiFetch fallback ←', { url: apiUrl(activeBase, path), status: res.status });
    }

    // Refresh + retry once on 401
    if (res.status === 401) {
        console.warn('[PORTAL] apiFetch 401 → attempting refresh');
        const { data, error } = await sb.auth.refreshSession();
        console.log('[PORTAL] refreshSession', { ok: !error && !!data?.session, error: error?.message });
        if (!error && data.session) {
            const headers2 = { ...headers, Authorization: `Bearer ${data.session.access_token}` };
            res = await fetch(apiUrl(activeBase, path), { ...options, headers: headers2 });
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
