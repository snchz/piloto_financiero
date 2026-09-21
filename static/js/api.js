/**
 * API Service Client
 * Manejo centralizado de peticiones HTTP JSON con soporte para GET y POST
 */
const API = {
    async fetch(url, options = {}) {
        const res = await fetch(url, options);
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.error || 'Error de comunicación con el servidor');
        }
        return res.json();
    },

    async post(url, data = {}) {
        return this.fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }
};

window.API = API;
