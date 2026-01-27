const API_BASE = '/api/audit';

export const api = {
    async fetchMeta() {
        const res = await fetch(`${API_BASE}/meta`);
        return await res.json();
    },

    async fetchBundle(payload) {
        const res = await fetch(`${API_BASE}/bundle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        return await res.json();
    },

    async fetchSeasonContrast(payload, date = null) {
        const body = { ...payload, split_date: date };
        const res = await fetch(`${API_BASE}/season-contrast`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        return await res.json();
    }
};
