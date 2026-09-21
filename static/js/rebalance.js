/**
 * Strategy & Rebalance Service
 * Cálculo de rebalanceo por aportaciones de flujo de caja y gestión de categorías estratégicas
 */

let debounceRebalanceoTimer = null;
let lastRebalanceoData = null;

function setAportacionRapida(importe) {
    const input = document.getElementById('input-aportacion-mes');
    if (input) {
        input.value = importe;
        ejecutarCalculoRebalanceo();
    }
}
window.setAportacionRapida = setAportacionRapida;

function debounceCalcularRebalanceo() {
    clearTimeout(debounceRebalanceoTimer);
    debounceRebalanceoTimer = setTimeout(() => {
        ejecutarCalculoRebalanceo();
    }, 350);
}
window.debounceCalcularRebalanceo = debounceCalcularRebalanceo;

async function ejecutarCalculoRebalanceo() {
    const input = document.getElementById('input-aportacion-mes');
    const aportacion = parseFloat(input?.value || 0) || 0;
    await cargarRebalanceo(aportacion);
}
window.ejecutarCalculoRebalanceo = ejecutarCalculoRebalanceo;

async function cargarRebalanceo(aportacion = null) {
    const grid = document.getElementById('rebalanceo-tags-grid');
    const sugContainer = document.getElementById('rebalanceo-sugerencias-container');
    if (!grid) return;

    if (aportacion === null) {
        const input = document.getElementById('input-aportacion-mes');
        aportacion = parseFloat(input?.value || 0) || 0;
    }

    try {
        const mironParam = window.modoMiron ? '&miron=1' : '';
        const res = await API.fetch(`/api/rebalanceo?aportacion=${aportacion}${mironParam}`);
        lastRebalanceoData = res;

        // 1. Renderizar Tarjetas de Categorías
        if (res.tags && res.tags.length > 0) {
            const cardsHtml = res.tags.map(t => {
                let estadoBadgeClass = 'bg-secondary text-white';
                let estadoText = t.estado;
                if (t.estado === 'SOBREPONDERADO') {
                    estadoBadgeClass = 'bg-primary bg-opacity-20 text-primary border border-primary border-opacity-40';
                } else if (t.estado === 'DÉFICIT') {
                    estadoBadgeClass = 'bg-warning bg-opacity-20 text-warning border border-warning border-opacity-40';
                } else if (t.estado === 'DISPONIBLE') {
                    estadoBadgeClass = 'bg-info bg-opacity-20 text-info border border-info border-opacity-40';
                } else if (t.estado === 'EQUILIBRADO') {
                    estadoBadgeClass = 'bg-success bg-opacity-20 text-success border border-success border-opacity-40';
                }

                const desvSign = t.desviacion_eur >= 0 ? '+' : '';
                const desvEurClass = t.desviacion_eur >= 0 ? 'text-primary' : (t.valor_actual_eur === 0 ? 'text-info' : 'text-warning');
                const desvPctSign = t.desviacion_pct >= 0 ? '+' : '';

                const progressWidth = Math.min(Math.max((t.pct_actual / Math.max(t.target_pct * 1.5, 100)) * 100, 2), 100);
                const targetMarkerPos = Math.min((t.target_pct / Math.max(t.target_pct * 1.5, 100)) * 100, 100);

                const activosSummary = t.activos && t.activos.length > 0 
                    ? t.activos.map(a => `<span class="badge font-monospace" style="background: rgba(255,255,255,0.06); color: #cbd5e1; font-size: 0.65rem;">${a.ticker} (${UI.formatCurrency(a.valor_eur, 'EUR')})</span>`).join(' ')
                    : '<span class="text-secondary font-monospace" style="font-size: 0.65rem;">Sin posiciones abiertas</span>';

                return `
                <div class="col-xl-4 col-md-6">
                    <div class="p-3 rounded-3 h-100 d-flex flex-column justify-content-between" style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.06);">
                        <div>
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <div class="d-flex align-items-center gap-2">
                                    <span class="d-inline-block rounded-circle" style="width: 10px; height: 10px; background-color: ${t.color}; box-shadow: 0 0 8px ${t.color}88;"></span>
                                    <span class="fw-bold text-white small">${t.nombre}</span>
                                </div>
                                <span class="badge ${estadoBadgeClass} font-monospace" style="font-size: 0.65rem;">${estadoText}</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-baseline mb-2">
                                <div>
                                    <span class="text-secondary font-monospace" style="font-size: 0.75rem;">Actual: </span>
                                    <span class="fw-bold text-white font-monospace fs-6">${t.pct_actual.toFixed(1)}%</span>
                                    <span class="text-secondary small font-monospace">(${UI.formatCurrency(t.valor_actual_eur, 'EUR')})</span>
                                </div>
                                <div class="text-end">
                                    <span class="text-secondary font-monospace" style="font-size: 0.72rem;">Objetivo: </span>
                                    <span class="fw-bold font-monospace text-light" style="font-size: 0.85rem;">${t.target_pct.toFixed(1)}%</span>
                                </div>
                            </div>
                            
                            <div class="position-relative mb-2" style="height: 7px; background: rgba(255,255,255,0.06); border-radius: 4px; overflow: visible;">
                                <div style="width: ${progressWidth}%; height: 100%; background: ${t.color}; border-radius: 4px;"></div>
                                <div style="position: absolute; left: ${targetMarkerPos}%; top: -3px; bottom: -3px; width: 2px; background: #ffffff; box-shadow: 0 0 4px #ffffff; z-index: 2;" title="Objetivo: ${t.target_pct}%"></div>
                            </div>

                            <div class="d-flex justify-content-between align-items-center mb-2 font-monospace" style="font-size: 0.72rem;">
                                <span class="text-secondary">Desviación:</span>
                                <span class="${desvEurClass} fw-semibold">${desvSign}${UI.formatCurrency(t.desviacion_eur, 'EUR')} (${desvPctSign}${t.desviacion_pct.toFixed(1)}%)</span>
                            </div>
                        </div>
                        
                        <div class="pt-2 border-top border-secondary border-opacity-10 d-flex flex-wrap gap-1 align-items-center">
                            ${activosSummary}
                        </div>
                    </div>
                </div>`;
            }).join('');

            grid.innerHTML = cardsHtml;
        } else {
            grid.innerHTML = '<div class="col-12 text-center text-secondary small py-2">No hay categorías configuradas</div>';
        }

        // 2. Renderizar Sugerencias de Aportación
        if (sugContainer) {
            if (aportacion > 0) {
                if (res.sugerencias_compra && res.sugerencias_compra.length > 0) {
                    const recItems = res.sugerencias_compra.map((s, idx) => {
                        const prioBadge = s.prioridad === 'MÁXIMA'
                            ? 'bg-danger bg-opacity-25 text-danger border border-danger border-opacity-40'
                            : (s.prioridad === 'ALTA'
                                ? 'bg-warning bg-opacity-25 text-warning border border-warning border-opacity-40'
                                : 'bg-info bg-opacity-25 text-info border border-info border-opacity-40');

                        return `
                        <div class="d-flex justify-content-between align-items-center p-2 rounded-2" style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05);">
                            <div class="d-flex align-items-center gap-2">
                                <span class="badge rounded-circle d-flex align-items-center justify-content-center fw-bold font-monospace" style="width: 22px; height: 22px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; font-size: 0.72rem;">${idx + 1}</span>
                                <div>
                                    <div class="fw-semibold text-white small">${s.name}</div>
                                    <div class="d-flex align-items-center gap-2">
                                        <span class="text-secondary font-monospace" style="font-size: 0.68rem;">${s.ticker || 'Reserva'}</span>
                                        <span class="badge px-1 py-0 font-monospace" style="background: ${s.color}22; color: ${s.color}; border: 1px solid ${s.color}44; font-size: 0.65rem;">${s.tag_nombre}</span>
                                    </div>
                                </div>
                            </div>
                            <div class="text-end">
                                <div class="fw-bold font-monospace text-success fs-6">+${UI.formatCurrency(s.importe, 'EUR')}</div>
                                <span class="badge ${prioBadge} font-monospace" style="font-size: 0.65rem;">Prioridad ${s.prioridad}</span>
                            </div>
                        </div>`;
                    }).join('');

                    sugContainer.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="text-white small fw-semibold">👉 Asignación óptima recomendada este mes:</span>
                            <span class="badge bg-success bg-opacity-25 text-success border border-success border-opacity-40 font-monospace">Total: +${UI.formatCurrency(aportacion, 'EUR')}</span>
                        </div>
                        <div class="d-flex flex-column gap-2">${recItems}</div>
                    `;
                } else {
                    sugContainer.innerHTML = `
                        <div class="text-center py-2 text-secondary small">
                            ✅ Tu cartera se encuentra en equilibrio objetivo. La aportación se repartirá proporcionalmente a los targets fijados.
                        </div>
                    `;
                }
            } else {
                sugContainer.innerHTML = `
                    <div class="text-center py-2 text-secondary small">
                        ℹ️ Introduce una cantidad arriba (ej. 500 €) para calcular la distribución óptima de tu aportación mensual.
                    </div>
                `;
            }
        }

    } catch (err) {
        console.error('Error cargando rebalanceo:', err);
        if (grid) grid.innerHTML = `<div class="col-12 text-center text-danger small py-2">Error cargando rebalanceo: ${err.message || err}</div>`;
    }
}
window.cargarRebalanceo = cargarRebalanceo;

// --- Gestión de Modal de Estrategia y Etiquetas ---
async function abrirConfigTagsModal() {
    try {
        const res = await API.fetch('/api/rebalanceo/tags');
        const tags = res.tags || [];
        const assetTags = res.asset_tags || {};

        // 1. Renderizar inputs de configuración de tags
        const container = document.getElementById('tags-inputs-container');
        let totalPct = 0;
        if (container) {
            container.innerHTML = tags.map(t => {
                totalPct += t.target_pct;
                return `
                <div class="p-2 rounded-2" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);">
                    <div class="row g-2 align-items-center">
                        <div class="col-md-5">
                            <div class="d-flex align-items-center gap-2">
                                <input type="color" class="form-control form-control-color bg-transparent border-0 p-0" id="tag-color-${t.tag_id}" value="${t.color}" style="width: 24px; height: 24px; cursor: pointer;">
                                <input type="text" class="form-control form-control-sm bg-dark text-white border-secondary border-opacity-50" id="tag-name-${t.tag_id}" value="${t.nombre}">
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="input-group input-group-sm">
                                <input type="number" step="0.5" min="0" max="100" class="form-control bg-dark text-white border-secondary border-opacity-50 font-monospace text-end tag-pct-input" id="tag-pct-${t.tag_id}" value="${t.target_pct}" oninput="actualizarSumaTagsPct()">
                                <span class="input-group-text bg-dark border-secondary border-opacity-50 text-secondary">%</span>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <input type="text" class="form-control form-control-sm bg-dark text-secondary border-secondary border-opacity-25" id="tag-desc-${t.tag_id}" value="${t.descripcion || ''}" placeholder="Descripción">
                        </div>
                    </div>
                </div>`;
            }).join('');
        }

        actualizarSumaTagsPct();

        // 2. Renderizar pestaña de mapeo de activos
        const mapContainer = document.getElementById('asset-mapping-container');
        const activosEnCartera = (window.operacionesData && window.operacionesData.cartera) ? Object.entries(window.operacionesData.cartera) : [];
        
        if (mapContainer) {
            if (activosEnCartera.length > 0) {
                mapContainer.innerHTML = activosEnCartera.filter(([ticker, m]) => m.tipo !== 'INMUEBLE').map(([ticker, m]) => {
                    const currentTag = assetTags[ticker] || '';
                    const optionsHtml = `
                        <option value="" ${!currentTag ? 'selected' : ''}>-- Sin Categoría / Táctico --</option>
                        ${tags.map(t => `<option value="${t.tag_id}" ${currentTag === t.tag_id ? 'selected' : ''}>${t.nombre} (${t.target_pct}%)</option>`).join('')}
                    `;

                    return `
                    <div class="d-flex justify-content-between align-items-center p-2 rounded-2" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05);">
                        <div>
                            <div class="fw-bold text-white small">${m.name || ticker}</div>
                            <div class="text-secondary font-monospace" style="font-size: 0.7rem;">${ticker}</div>
                        </div>
                        <div style="min-width: 200px;">
                            <select class="form-select form-select-sm bg-dark text-white border-secondary border-opacity-50" onchange="asignarTagActivo('${ticker}', this.value)">
                                ${optionsHtml}
                            </select>
                        </div>
                    </div>`;
                }).join('');
            } else {
                mapContainer.innerHTML = '<div class="text-secondary small text-center py-2">No hay posiciones abiertas para asignar</div>';
            }
        }

        document.getElementById('tagsModal').showModal();
    } catch (err) {
        console.error('Error abriendo modal de tags:', err);
        UI.showToast(`Error: ${err.message || err}`, 'error');
    }
}
window.abrirConfigTagsModal = abrirConfigTagsModal;

function actualizarSumaTagsPct() {
    const inputs = document.querySelectorAll('.tag-pct-input');
    let total = 0;
    inputs.forEach(inp => total += parseFloat(inp.value || 0) || 0);
    
    const badge = document.getElementById('tags-total-pct-badge');
    if (badge) {
        badge.textContent = `Total: ${total.toFixed(1)}%`;
        if (Math.abs(total - 100.0) < 0.1) {
            badge.className = 'badge bg-success font-monospace';
        } else {
            badge.className = 'badge bg-danger font-monospace';
        }
    }
}
window.actualizarSumaTagsPct = actualizarSumaTagsPct;

async function guardarTagsConfig(event) {
    if (event) event.preventDefault();
    try {
        const inputs = document.querySelectorAll('.tag-pct-input');
        let total = 0;
        inputs.forEach(inp => total += parseFloat(inp.value || 0) || 0);

        if (Math.abs(total - 100.0) > 0.5) {
            return UI.showToast(`Los porcentajes deben sumar 100% (actual: ${total.toFixed(1)}%)`, 'error');
        }

        const tagsPayload = [];
        inputs.forEach(inp => {
            const tagId = inp.id.replace('tag-pct-', '');
            const name = document.getElementById(`tag-name-${tagId}`)?.value || tagId;
            const pct = parseFloat(inp.value || 0) || 0;
            const color = document.getElementById(`tag-color-${tagId}`)?.value || '#3b82f6';
            const desc = document.getElementById(`tag-desc-${tagId}`)?.value || '';

            tagsPayload.push({
                tag_id: tagId,
                nombre: name,
                target_pct: pct,
                color: color,
                descripcion: desc
            });
        });

        await API.post('/api/rebalanceo/tags', { tags: tagsPayload });

        UI.showToast('Estrategia y objetivos guardados con éxito', 'success');
        document.getElementById('tagsModal').close();
        await window.cargarOperaciones();
    } catch (err) {
        console.error('Error guardando tags:', err);
        UI.showToast(`Error: ${err.message || err}`, 'error');
    }
}
window.guardarTagsConfig = guardarTagsConfig;

async function asignarTagActivo(ticker, tagId) {
    try {
        await API.post('/api/rebalanceo/map-asset', { ticker: ticker, tag_id: tagId });
        UI.showToast(`Asignación de ${ticker} actualizada`, 'success');
        await window.cargarOperaciones();
    } catch (err) {
        console.error('Error mapeando activo:', err);
        UI.showToast(`Error: ${err.message || err}`, 'error');
    }
}
window.asignarTagActivo = asignarTagActivo;
