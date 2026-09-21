/**
 * UI & Notifications Service
 * Formateo de monedas, toasts, modales de configuración/debug y estado de vista
 */

const UI = {
    version: window.APP_VERSION || '1.0.0',

    formatCurrency(val, currency = 'USD') {
        if (val == null) return '...';
        const isSmall = Math.abs(val) < 1 && Math.abs(val) > 0;
        const maxDecimals = isSmall ? 5 : 2;
        try {
            const curr = (currency && currency !== '-') ? currency.toUpperCase() : 'USD';
            return new Intl.NumberFormat('es-ES', { 
                style: 'currency', 
                currency: curr, 
                minimumFractionDigits: 2, 
                maximumFractionDigits: maxDecimals 
            }).format(val);
        } catch (e) {
            return Number(val).toFixed(maxDecimals) + ' ' + (currency || '');
        }
    },

    updateLastRefreshTime() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('es-ES');
        const dateStr = now.toLocaleDateString('es-ES');
        const timestamp = `${dateStr} ${timeStr}`;
        const el = document.getElementById('last-update-time');
        if (el) el.textContent = timeStr;
        localStorage.setItem('last_price_update', timestamp);
    },

    loadLastRefreshTime() {
        const timestamp = localStorage.getItem('last_price_update');
        const el = document.getElementById('last-update-time');
        if (!el) return;
        if (timestamp) {
            const parts = timestamp.split(' ');
            const timeStr = parts.slice(1).join(' ');
            el.textContent = timeStr;
        } else {
            el.textContent = '--:--:--';
        }
    },

    showToast(message, type = 'success') {
        const container = document.querySelector('.toast-container');
        if (!container) return;
        const id = 'toast-' + Date.now();
        const icon = type === 'success' ? '✓' : (type === 'warning' ? 'ℹ️' : '⚠️');
        const bg = type === 'success' ? 'text-bg-success' : (type === 'warning' ? 'text-bg-warning' : 'text-bg-danger');

        const toastHtml = `
            <div id="${id}" class="toast align-items-center ${bg} border-0 mb-2 shadow-lg" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <strong>${icon}</strong> ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', toastHtml);
        const toastEl = document.getElementById(id);
        const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
        toast.show();
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    },

    renderTable(monitores) {
        const tbody = document.getElementById('monitors-table');
        if (!tbody) return;
        const entries = Object.entries(monitores);
        if (entries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-secondary">No hay alertas configuradas</td></tr>';
            return;
        }

        const html = entries.map(([id, m]) => {
            const variacion = m.current && m.previous_close ? ((m.current - m.previous_close) / m.previous_close * 100) : 0;
            const variacionClass = variacion >= 0 ? 'text-success' : 'text-danger';
            const variacionSign = variacion >= 0 ? '+' : '';
            
            const distObj = (m.current > 0 && m.target) ? ((m.target - m.current) / m.current * 100) : null;
            const distObjText = distObj !== null ? `${distObj > 0 ? '+' : ''}${distObj.toFixed(2)}%` : '-';
            
            return `
            <tr>
                <td class="ps-4">
                    <div class="fw-bold text-white">${m.name || m.ticker}</div>
                    <div class="text-secondary font-monospace" style="font-size: 0.7rem;">${m.ticker}</div>
                </td>
                <td class="text-center"><span class="badge bg-dark border border-secondary border-opacity-25 font-monospace">${m.currency || '-'}</span></td>
                <td class="text-end" title="Actualizado: ${m.current_price_time || 'N/A'}" style="cursor: help;">
                    <div class="font-monospace fs-6 fw-semibold text-white">${UI.formatCurrency(m.current, m.currency)}</div>
                </td>
                <td class="text-end font-monospace fs-6 fw-semibold ${variacionClass}">${variacion ? `${variacionSign}${variacion.toFixed(2)}%` : '-'}</td>
                <td class="text-end font-monospace fs-6 fw-semibold text-white">${UI.formatCurrency(m.target, m.currency)}</td>
                <td class="text-end font-monospace fs-6 fw-semibold text-secondary">${distObjText}</td>
                <td class="text-center">
                    <span class="badge-status ${m.triggered ? 'badge-alert' : 'badge-active'}">
                        ${m.triggered ? 'ALERTA' : 'Vigilando'}
                    </span>
                </td>
                <td class="pe-4 text-end">
                    <button onclick="openEditModal('${id}', ${m.target}, ${m.target_pct || 0})" class="action-btn me-1" title="Editar objetivo">
                        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                    </button>
                    <button onclick="handleDelete('${id}')" class="action-btn delete" title="Eliminar">
                        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                </td>
            </tr>
        `}).join('');
        tbody.innerHTML = html;
    },

    renderFeed(alertas) {
        const feed = document.getElementById('alerts-feed');
        if (!feed) return;
        if (!alertas || alertas.length === 0) {
            feed.innerHTML = '<div class="text-secondary small text-center py-5">Sin actividad reciente</div>';
            return;
        }
        const html = alertas.map(a => {
            const isVolatilidad = a.msg.toLowerCase().includes('volatilidad') || a.msg.includes('%');
            const isTarget = a.msg.toLowerCase().includes('objetivo') || a.msg.toLowerCase().includes('alerta');
            
            let accentColor = '#6366f1';
            let icon = 'ℹ️';
            let label = 'SISTEMA';
            
            if (isVolatilidad) {
                accentColor = '#f59e0b';
                icon = '⚡';
                label = 'VOLATILIDAD';
            } else if (isTarget) {
                accentColor = '#f43f5e';
                icon = '🎯';
                label = 'ALERTA';
            }
            
            return `
                <div class="p-3 mb-2 rounded-3" style="background: rgba(17, 20, 30, 0.7); border: 1px solid rgba(255,255,255,0.06); border-left: 4px solid ${accentColor};">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span class="badge font-monospace px-2 py-1" style="background: ${accentColor}20; color: ${accentColor}; border: 1px solid ${accentColor}40; font-size: 0.68rem;">
                            ${icon} ${label}
                        </span>
                        <span class="text-secondary font-monospace" style="font-size: 0.72rem;">${a.time}</span>
                    </div>
                    <div class="text-white fw-medium mt-1" style="font-size: 0.88rem; font-family: 'Inter', sans-serif;">${a.msg}</div>
                </div>
            `;
        }).join('');
        feed.innerHTML = html;
    },

    checkVersion(newVersion) {
        if (this.version !== newVersion) {
            this.version = newVersion;
            const el = document.getElementById('version');
            if (el) el.textContent = newVersion;
            this.showToast(`Actualizado a v${newVersion}`, 'success');
        }
    }
};

window.UI = UI;

// --- Conmutador Vista Esencial vs Avanzada ---
window.toggleVistaEsencial = function() {
    const isEsencial = document.body.classList.toggle('vista-esencial');
    localStorage.setItem('vista_esencial', isEsencial ? '1' : '0');
    actualizarBotonVistaEsencial(isEsencial);
};

function actualizarBotonVistaEsencial(isEsencial) {
    const btn = document.getElementById('btn-toggle-vista');
    if (!btn) return;
    if (isEsencial) {
        btn.classList.add('active');
        btn.innerHTML = '🎯 Vista: Esencial';
        btn.title = 'Modo Esencial: Ocultando volatilidad, Sharpe y drawdowns. Clic para Vista Avanzada.';
    } else {
        btn.classList.remove('active');
        btn.innerHTML = '📊 Vista: Completa';
        btn.title = 'Modo Completo: Mostrando todas las métricas cuantitativas y de riesgo. Clic para Vista Esencial.';
    }
}

// Inicializar preferencia de vista
document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('vista_esencial');
    if (saved === '1') {
        document.body.classList.add('vista-esencial');
        actualizarBotonVistaEsencial(true);
    } else {
        actualizarBotonVistaEsencial(false);
    }
});

// --- Modal de Configuración General ---
window.abrirConfig = async () => {
    try {
        const config = await API.fetch('/api/config');
        document.getElementById('cfg-app-title').value = config.app_title || 'Piloto Financiero';
        document.getElementById('cfg-telegram-token').value = config.telegram_token || '';
        document.getElementById('cfg-telegram-chat-id').value = config.telegram_chat_id || '';
        document.getElementById('cfg-refresh-interval').value = config.refresh_interval || 30;
        document.getElementById('cfg-activity-retention').value = config.activity_retention_days || 2;
        document.getElementById('cfg-exchange-rate-ttl').value = config.exchange_rate_ttl_hours || 12;
        document.getElementById('cfg-check-market-hours').checked = !!config.check_market_hours;
        document.getElementById('cfg-debug-ui').checked = !!config.debug_ui;
        document.getElementById('configModal').showModal();
    } catch (err) {
        UI.showToast('Error cargando configuración', 'error');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const configForm = document.getElementById('config-form');
    if (configForm) {
        configForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                app_title: document.getElementById('cfg-app-title').value || 'Piloto Financiero',
                telegram_token: document.getElementById('cfg-telegram-token').value || '',
                telegram_chat_id: document.getElementById('cfg-telegram-chat-id').value || '',
                refresh_interval: parseInt(document.getElementById('cfg-refresh-interval').value) || 30,
                activity_retention_days: parseInt(document.getElementById('cfg-activity-retention').value) || 2,
                exchange_rate_ttl_hours: parseFloat(document.getElementById('cfg-exchange-rate-ttl').value) || 12,
                check_market_hours: document.getElementById('cfg-check-market-hours').checked,
                debug_ui: document.getElementById('cfg-debug-ui').checked
            };
            
            try {
                await API.post('/api/config', payload);
                document.title = payload.app_title;
                const brand = document.getElementById('brand-text');
                if (brand) brand.textContent = payload.app_title;
                document.getElementById('configModal').close();
                UI.showToast('Configuración guardada correctamente');
            } catch (err) {
                UI.showToast('Error guardando configuración', 'error');
            }
        });
    }
});

// --- Debug Panel & Logs ---
let logInterval = null;
async function syncLogs() {
    try {
        const data = await API.fetch('/api/logs');
        const container = document.getElementById('debugLogs');
        if (container) {
            container.innerHTML = (data.logs || []).map(l => 
                `<div class="log-entry font-monospace mb-1">
                    <span class="text-secondary me-2">${l.timestamp}</span>
                    <span class="text-${l.level === 'ERROR' ? 'danger' : (l.level === 'WARNING' ? 'warning' : 'info')}">[${l.level}]</span> 
                    <span class="text-light">${l.message}</span>
                </div>`
            ).join('');
        }
    } catch (err) {}
}
window.syncLogs = syncLogs;

window.toggleDebug = () => {
    const panel = document.getElementById('debugPanel');
    if (!panel) return;
    const isHidden = panel.style.display === 'none' || panel.style.display === '';
    panel.style.display = isHidden ? 'block' : 'none';
    if (isHidden) {
        syncLogs();
        logInterval = setInterval(syncLogs, 2000);
    } else if (logInterval) {
        clearInterval(logInterval);
    }
};

window.clearLogs = async () => {
    try {
        await API.fetch('/api/logs', { method: 'DELETE' });
        const container = document.getElementById('debugLogs');
        if (container) container.innerHTML = '';
    } catch (e) {}
};

window.copyLogs = () => {
    const container = document.getElementById('debugLogs');
    if (!container) return;
    const logsText = container.innerText;
    if (!logsText.trim()) return UI.showToast('No hay logs para copiar', 'error');
    navigator.clipboard.writeText(logsText).then(() => UI.showToast('Logs copiados'));
};

// --- Gestión de Actividad y Monitores ---
window.limpiarActividad = async () => {
    if (!confirm('¿Seguro que deseas borrar toda la actividad reciente?')) return;
    try {
        await API.fetch('/api/alertas', { method: 'DELETE' });
        UI.showToast('Actividad reciente borrada');
    } catch (err) {
        UI.showToast('No se pudo borrar la actividad', 'error');
    }
};

window.handleDelete = async (id) => {
    if (!confirm('¿Seguro que deseas eliminar esta alerta?')) return;
    try {
        await API.fetch(`/api/delete/${id}`, { method: 'DELETE' });
        UI.showToast('Alerta eliminada');
    } catch (err) {
        UI.showToast('No se pudo eliminar', 'error');
    }
};

let currentEditId = null;
window.openEditModal = (id, target, targetPct) => {
    currentEditId = id;
    const editTarget = document.getElementById('edit-target');
    const editPct = document.getElementById('edit-target-pct');
    if (editTarget) editTarget.value = target;
    if (editPct) editPct.value = targetPct || '';
    document.getElementById('editModal').showModal();
};

document.addEventListener('DOMContentLoaded', () => {
    const editForm = document.getElementById('edit-form');
    if (editForm) {
        editForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!currentEditId) return;

            const formData = new FormData(e.target);
            const target = parseFloat(formData.get('target').replace(',', '.'));
            const targetPct = parseFloat(formData.get('target_pct').replace(',', '.')) || 0;

            if (isNaN(target) || target <= 0) return UI.showToast('Precio objetivo inválido', 'error');

            try {
                await API.fetch(`/api/edit/${currentEditId}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ target, target_pct: targetPct })
                });
                document.getElementById('editModal').close();
                UI.showToast('Objetivo actualizado con éxito');
            } catch (err) {
                UI.showToast('No se pudo actualizar el objetivo', 'error');
            }
        });
    }

    // SSE connection for live updates
    try {
        const evtSource = new EventSource('/api/stream');
        evtSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                UI.checkVersion(data.version);
                UI.updateLastRefreshTime();
                UI.renderTable(data.monitores);
                UI.renderFeed(data.alertas);
            } catch (err) {
                console.error("SSE error:", err);
            }
        };
    } catch (e) {
        console.warn("EventSource not supported or failed:", e);
    }
});
