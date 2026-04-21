const API_BASE = '/api/v1';

function formatApiErrorDetail(detail) {
    if (!detail) return 'Ошибка запроса';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail.map(item => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object') {
                const path = Array.isArray(item.loc) ? item.loc.join('.') : '';
                const message = item.msg || JSON.stringify(item);
                return path ? `${path}: ${message}` : message;
            }
            return String(item);
        }).join('; ');
    }
    if (typeof detail === 'object') {
        return detail.message || detail.msg || JSON.stringify(detail);
    }
    return String(detail);
}

const api = {
    getToken() {
        return localStorage.getItem('token');
    },

    setToken(token) {
        localStorage.setItem('token', token);
    },

    removeToken() {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        localStorage.removeItem('current_project');
    },

    getUser() {
        const u = localStorage.getItem('user');
        return u ? JSON.parse(u) : null;
    },

    setUser(user) {
        localStorage.setItem('user', JSON.stringify(user));
    },

    getCurrentProject() {
        const raw = localStorage.getItem('current_project');
        return raw ? JSON.parse(raw) : null;
    },

    setCurrentProject(project) {
        localStorage.setItem('current_project', JSON.stringify(project));
    },

    clearCurrentProject() {
        localStorage.removeItem('current_project');
    },

    async fetch(path, options = {}) {
        const token = this.getToken();
        const headers = {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...(options.headers || {}),
        };

        const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

        if (res.status === 401) {
            this.removeToken();
            window.location.href = '/login.html';
            return;
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(formatApiErrorDetail(err.detail));
        }

        if (res.status === 204) return null;
        return res.json();
    },

    async login(username, password) {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Ошибка авторизации' }));
            throw new Error(formatApiErrorDetail(err.detail || 'Неверный логин или пароль'));
        }
        return res.json();
    },

    async me() {
        return this.fetch('/auth/me');
    },

    async updateMe(data) {
        return this.fetch('/auth/me', { method: 'PATCH', body: JSON.stringify(data) });
    },

    // --- Projects ---
    async getProjects(activeOnly = true) {
        const q = activeOnly ? '?active_only=true' : '?active_only=false';
        return this.fetch(`/projects/${q}`);
    },

    async getProject(id) {
        return this.fetch(`/projects/${id}`);
    },

    async createProject(data) {
        return this.fetch('/projects/', { method: 'POST', body: JSON.stringify(data) });
    },

    async updateProject(id, data) {
        return this.fetch(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
    },

    async deleteProject(id) {
        return this.fetch(`/projects/${id}`, { method: 'DELETE' });
    },

    // --- Reports ---
    async getReports(projectId) {
        return this.fetch(`/reports/?project_id=${encodeURIComponent(projectId)}`);
    },

    async getReport(projectId, reportKey) {
        return this.fetch(`/reports/${encodeURIComponent(reportKey)}?project_id=${encodeURIComponent(projectId)}`);
    },

    // --- Sites ---
    async getSites(params = {}) {
        const q = new URLSearchParams(
            Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null))
        ).toString();
        return this.fetch(`/sites/${q ? '?' + q : ''}`);
    },

    async getSite(id) {
        return this.fetch(`/sites/${id}`);
    },

    async createSite(data) {
        return this.fetch('/sites/', { method: 'POST', body: JSON.stringify(data) });
    },

    async updateSite(id, data) {
        return this.fetch(`/sites/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
    },

    async deleteSite(id) {
        return this.fetch(`/sites/${id}`, { method: 'DELETE' });
    },

    // --- Users ---
    async getUsers() {
        return this.fetch('/users/');
    },

    async createUser(data) {
        return this.fetch('/users/', { method: 'POST', body: JSON.stringify(data) });
    },

    async updateUser(id, data) {
        return this.fetch(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
    },

    async deleteUser(id) {
        return this.fetch(`/users/${id}`, { method: 'DELETE' });
    },

    // --- Contractors ---
    async getContractors(activeOnly = false) {
        const q = activeOnly ? '?active_only=true' : '';
        return this.fetch(`/contractors/${q}`);
    },

    async createContractor(data) {
        return this.fetch('/contractors/', { method: 'POST', body: JSON.stringify(data) });
    },

    async updateContractor(id, data) {
        return this.fetch(`/contractors/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
    },

    async deleteContractor(id) {
        return this.fetch(`/contractors/${id}`, { method: 'DELETE' });
    },

    // --- Regions ---
    async getRegions(activeOnly = false) {
        const q = activeOnly ? '?active_only=true' : '';
        return this.fetch(`/regions/${q}`);
    },

    async createRegion(data) {
        return this.fetch('/regions/', { method: 'POST', body: JSON.stringify(data) });
    },

    async updateRegion(id, data) {
        return this.fetch(`/regions/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
    },

    async deleteRegion(id) {
        return this.fetch(`/regions/${id}`, { method: 'DELETE' });
    },

    // --- Logs ---
    async getLogs(params = {}) {
        const q = new URLSearchParams(
            Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null))
        ).toString();
        return this.fetch(`/logs/${q ? '?' + q : ''}`);
    },

    // --- History / Rollback ---
    async getSiteHistory(siteId, params = {}) {
        const q = new URLSearchParams(
            Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null))
        ).toString();
        return this.fetch(`/sync/history/${siteId}${q ? '?' + q : ''}`);
    },

    async getHistoryFields() {
        return this.fetch('/sync/history-fields');
    },

    async rollbackSite(siteId, toTimestamp, fieldName = null) {
        return this.fetch('/sync/rollback', {
            method: 'POST',
            body: JSON.stringify({
                site_id: siteId,
                field_name: fieldName,
                to_timestamp: toTimestamp,
            }),
        });
    },

    async rollbackHistoryEntry(historyId) {
        return this.fetch('/sync/rollback-entry', {
            method: 'POST',
            body: JSON.stringify({ history_id: historyId }),
        });
    },

    async rollbackHistoryBatch(siteId, batchId) {
        return this.fetch('/sync/rollback-batch', {
            method: 'POST',
            body: JSON.stringify({
                site_id: siteId,
                batch_id: batchId,
            }),
        });
    },

    // --- Excel ---
    async exportExcel(projectId) {
        const token = this.getToken();
        const res = await fetch(`${API_BASE}/excel/export?project_id=${encodeURIComponent(projectId)}`, {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        });
        if (res.status === 401) {
            this.removeToken();
            window.location.href = '/login.html';
            return;
        }
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Ошибка экспорта' }));
            throw new Error(err.detail || 'Ошибка экспорта');
        }
        return res.blob();
    },

    async importExcel(file, projectId) {
        const token = this.getToken();
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${API_BASE}/excel/import?project_id=${encodeURIComponent(projectId)}`, {
            method: 'POST',
            headers: token ? { 'Authorization': `Bearer ${token}` } : {},
            body: formData,
        });
        if (res.status === 401) {
            this.removeToken();
            window.location.href = '/login.html';
            return;
        }
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Ошибка импорта' }));
            throw new Error(err.detail || 'Ошибка импорта');
        }
        return res.json();
    },
};
