/* ════════════════════════════════════════════════════════════════
   C-Aui Portal — Auth helpers (Supabase SDK wrapper)
   ──────────────────────────────────────────────────────────────── */

// NOTE: SUPABASE_URL / SUPABASE_ANON_KEY are the SAME as the warehouse project
// because in Option B the warehouse project also hosts auth + user_app_access.
const SUPABASE_URL      = 'https://aprmihzsessyptzqgdvs.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFwcm1paHpzZXNzeXB0enFnZHZzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU2MzI2MzEsImV4cCI6MjA5MTIwODYzMX0.C7qA7-rOl74gNTF1DVmR2xDqha2BPpNDlNnnP4V4lFs';

const { createClient } = supabase;
const sb = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
        persistSession:    true,
        autoRefreshToken:  true,
        detectSessionInUrl: true,   // pick up #access_token=... when redirected from another subdomain
    },
});

/** Resolve the active session (auto-refresh if near expiry). */
async function getCurrentSession() {
    const { data } = await sb.auth.getSession();
    return data.session || null;
}

async function getAccessToken() {
    const s = await getCurrentSession();
    return s?.access_token || '';
}

function getUserEmail() {
    // best-effort sync read from localStorage cache
    try {
        const key = `sb-${new URL(SUPABASE_URL).hostname.split('.')[0]}-auth-token`;
        const raw = localStorage.getItem(key);
        if (!raw) return '';
        const obj = JSON.parse(raw);
        return obj?.user?.email || obj?.currentSession?.user?.email || '';
    } catch {
        return '';
    }
}

async function login(email, password) {
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
    return data;
}

async function logout() {
    await sb.auth.signOut();
    window.location.href = '/login.html';
}

/** Redirect to /login.html if not signed in. Call at top of authenticated pages. */
async function requireAuth() {
    const s = await getCurrentSession();
    if (!s) {
        window.location.href = '/login.html';
        return null;
    }
    return s;
}
