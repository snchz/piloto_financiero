/**
 * Operations Management Service
 * Registro, edición, borrado, filtros y relleno predictivo de operaciones
 */

let filtroTipoOperacion = 'TODOS';

window.filtrarOperacionesPorTipo = (tipo, btn) => {
    filtroTipoOperacion = tipo;
    document.querySelectorAll('.op-filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    aplicarFiltroOperaciones();
};

function aplicarFiltroOperaciones() {
    const table = document.getElementById('operaciones-table');
    if (!table) return;
    const rows = table.querySelectorAll('tbody tr');
    const filtroInput = document.getElementById('filtro-operaciones');
    const textoFiltro = filtroInput ? filtroInput.value.toLowerCase().trim() : '';

    rows.forEach(row => {
        const tipoOp = row.getAttribute('data-tipo');
        if (!tipoOp) return;
        
        let coincideTipo = false;
        if (filtroTipoOperacion === 'TODOS') {
            coincideTipo = true;
        } else if (filtroTipoOperacion === 'COMPRA') {
            coincideTipo = (tipoOp === 'COMPRA' || tipoOp === 'APORTACION');
        } else if (filtroTipoOperacion === 'VENTA') {
            coincideTipo = (tipoOp === 'VENTA');
        } else if (filtroTipoOperacion === 'DIVIDENDO') {
            coincideTipo = (tipoOp === 'DIVIDENDO');
        } else if (filtroTipoOperacion === 'INMUEBLE') {
            coincideTipo = ['ENTRADA_INMUEBLE', 'HIPOTECA_CUOTA', 'REFORMA_MEJORA'].includes(tipoOp);
        }

        const textoFila = row.innerText.toLowerCase();
        const coincideTexto = !textoFiltro || textoFila.includes(textoFiltro);

        row.style.display = (coincideTipo && coincideTexto) ? '' : 'none';
    });
}
window.aplicarFiltroOperaciones = aplicarFiltroOperaciones;

function setupOperacionesFilter() {
    const filtroInput = document.getElementById('filtro-operaciones');
    if (filtroInput && !filtroInput.dataset.listenerAttached) {
        filtroInput.addEventListener('input', aplicarFiltroOperaciones);
        filtroInput.dataset.listenerAttached = 'true';
    }
}
window.setupOperacionesFilter = setupOperacionesFilter;

// --- Toggles de Categoría y Tipo ---
window.toggleAddAssetFields = (tipo) => {
    const isInmueble = tipo === 'INMUEBLE';
    document.querySelectorAll('.fields-financiero').forEach(el => el.classList.toggle('d-none', isInmueble));
    document.querySelectorAll('.fields-inmueble').forEach(el => el.classList.toggle('d-none', !isInmueble));
    const lbl = document.getElementById('label-ticker');
    if (lbl) lbl.textContent = isInmueble ? 'Identificador Inmueble (Ticker)' : 'Ticker o ISIN';
    const targetEl = document.getElementById('target');
    if (targetEl) targetEl.required = !isInmueble;
};

window.switchOpCategory = (cat) => {
    const isInmueble = cat === 'INMUEBLE';
    
    document.querySelectorAll('#op-tipo .opt-fin').forEach(el => el.classList.toggle('d-none', isInmueble));
    document.querySelectorAll('#op-tipo .opt-inm').forEach(el => el.classList.toggle('d-none', !isInmueble));
    
    document.querySelectorAll('.field-fin-only').forEach(el => el.classList.toggle('d-none', isInmueble));
    document.querySelectorAll('.field-inm-only').forEach(el => el.classList.toggle('d-none', !isInmueble));
    
    const lblTicker = document.getElementById('lbl-op-ticker');
    const inputTicker = document.getElementById('op-ticker');
    const selectTipo = document.getElementById('op-tipo');
    
    if (isInmueble) {
        if (lblTicker) lblTicker.textContent = 'Nombre / Identificador Inmueble';
        if (inputTicker) inputTicker.placeholder = 'Ej. Vivienda Habitual, MONEGRO 10';
        if (!['ENTRADA_INMUEBLE', 'HIPOTECA_CUOTA', 'REFORMA_MEJORA'].includes(selectTipo.value)) {
            selectTipo.value = 'ENTRADA_INMUEBLE';
        }
    } else {
        if (lblTicker) lblTicker.textContent = 'Ticker o ISIN';
        if (inputTicker) inputTicker.placeholder = 'Ej. AAPL, ES0105065009';
        if (['ENTRADA_INMUEBLE', 'HIPOTECA_CUOTA', 'REFORMA_MEJORA'].includes(selectTipo.value)) {
            selectTipo.value = 'COMPRA';
        }
    }
    
    toggleOpTypeFields(selectTipo.value);
};

window.toggleOpTypeFields = (tipo) => {
    const isHipoteca = tipo === 'HIPOTECA_CUOTA';
    const isRealEstateOp = tipo === 'ENTRADA_INMUEBLE' || tipo === 'HIPOTECA_CUOTA' || tipo === 'REFORMA_MEJORA';
    
    document.querySelectorAll('.fields-hipoteca').forEach(el => el.classList.toggle('d-none', !isHipoteca));
    document.querySelectorAll('.field-inm-only').forEach(el => el.classList.toggle('d-none', !isRealEstateOp));
    
    const lblPrecio = document.getElementById('lbl-op-precio');
    const lblComisiones = document.getElementById('lbl-op-comisiones');
    const lblImpuestos = document.getElementById('lbl-op-impuestos');
    
    if (isRealEstateOp) {
        if (lblPrecio) lblPrecio.textContent = isHipoteca ? 'Cuota Total Pagada por ti (€)' : 'Tu Aportación en Dinero (€)';
        if (lblComisiones) lblComisiones.textContent = 'Notaría / Gestión (€)';
        if (lblImpuestos) lblImpuestos.textContent = 'Impuestos / ITP (€)';
    } else {
        if (lblPrecio) lblPrecio.textContent = 'Precio Unitario (€)';
        if (lblComisiones) lblComisiones.textContent = 'Comisiones';
        if (lblImpuestos) lblImpuestos.textContent = 'Impuestos';
    }
};

// --- Relleno Predictivo al Teclear o Seleccionar Ticker ---
window.handleTickerPredictivo = function() {
    const input = document.getElementById('op-ticker');
    if (!input) return;
    const ticker = input.value.trim().toUpperCase();
    if (!ticker) return;

    // Buscar en la cartera actual
    if (window.operacionesData && window.operacionesData.cartera && window.operacionesData.cartera[ticker]) {
        const item = window.operacionesData.cartera[ticker];
        const monedaSelect = document.getElementById('op-moneda');
        if (monedaSelect && item.currency) {
            monedaSelect.value = item.currency;
        }
        const precioInput = document.getElementById('op-precio');
        if (precioInput && (!precioInput.value || parseFloat(precioInput.value) === 0)) {
            if (item.precio_actual) {
                precioInput.value = item.precio_actual;
            }
        }
        const tagSelect = document.getElementById('op-tag');
        if (tagSelect && window.operacionesData.asset_tags && window.operacionesData.asset_tags[ticker]) {
            tagSelect.value = window.operacionesData.asset_tags[ticker];
        }
        consultarTasaCambioModal();
        actualizarPreviewOperacion();
    }
};

// --- Modal Operación ---
window.abrirModalOperacion = (opId = null) => {
    const form = document.getElementById('op-form');
    form.reset();
    
    const modalTitle = document.getElementById('opModalTitle');
    const idInput = document.getElementById('op-id');
    const monedaSelect = document.getElementById('op-moneda');
    let op = null;

    // Poblar autocompletado de datalist de tickers
    const dl = document.getElementById('ticker-suggestions');
    if (dl && window.operacionesData && window.operacionesData.cartera) {
        dl.innerHTML = Object.entries(window.operacionesData.cartera)
            .map(([tkr, data]) => `<option value="${tkr}">${data.name || tkr} (${data.currency || 'EUR'})</option>`)
            .join('');
    }

    if (opId) {
        modalTitle.innerHTML = '✏️ Editar Operación';
        idInput.value = opId;
        op = window.operacionesData?.operaciones.find(o => o.id === opId);
        if (op) {
            const isRealEstate = ['ENTRADA_INMUEBLE', 'HIPOTECA_CUOTA', 'REFORMA_MEJORA'].includes(op.tipo);
            if (isRealEstate) {
                document.getElementById('op-cat-inmueble').checked = true;
                switchOpCategory('INMUEBLE');
                
                const infoInm = window.operacionesData?.activos_info?.[op.ticker] || {};
                if (infoInm.comunidad_autonoma) document.getElementById('op-inm-comunidad').value = infoInm.comunidad_autonoma;
                if (infoInm.pct_titularidad !== undefined) document.getElementById('op-inm-pct').value = (infoInm.pct_titularidad * 100);
                if (infoInm.precio_compra_total !== undefined) document.getElementById('op-inm-precio-compra').value = infoInm.precio_compra_total;
                if (infoInm.hipoteca_inicial !== undefined) document.getElementById('op-inm-hipoteca-ini').value = infoInm.hipoteca_inicial;
            } else {
                document.getElementById('op-cat-financial').checked = true;
                switchOpCategory('FINANCIERO');
            }

            document.getElementById('op-fecha').value = op.fecha.split(' ')[0];
            document.getElementById('op-ticker').value = op.ticker;
            document.getElementById('op-tipo').value = op.tipo;
            const cantVal = (window.modoMiron && op.raw_cantidad !== undefined) ? op.raw_cantidad : (op.cantidad || 1);
            document.getElementById('op-cantidad').value = cantVal;
            document.getElementById('op-precio').value = op.precio;
            
            const opMoneda = op.moneda || '';
            if (opMoneda && !Array.from(monedaSelect.options).some(opt => opt.value === opMoneda)) {
                monedaSelect.add(new Option(opMoneda + ' (Importada)', opMoneda));
            }
            monedaSelect.value = opMoneda;
            
            const comVal = (window.modoMiron && op.raw_comisiones !== undefined) ? op.raw_comisiones : (op.comisiones || 0);
            document.getElementById('op-comisiones').value = comVal;
            const impVal = (window.modoMiron && op.raw_impuestos !== undefined) ? op.raw_impuestos : (op.impuestos || 0);
            document.getElementById('op-impuestos').value = impVal;
            document.getElementById('op-tasa-cambio').value = op.tasa_cambio || '';
            document.getElementById('op-amortizacion').value = op.amortizacion || '';
            document.getElementById('op-intereses').value = op.intereses || '';

            toggleOpTypeFields(op.tipo);
        } else {
            return UI.showToast('No se encontraron los datos de la operación', 'error');
        }
    } else {
        modalTitle.innerHTML = '➕ Registrar Operación';
        idInput.value = '';
        document.getElementById('op-cat-financial').checked = true;
        switchOpCategory('FINANCIERO');
        document.getElementById('op-fecha').valueAsDate = new Date();
        document.getElementById('op-moneda').value = '';
    }

    const tagSelect = document.getElementById('op-tag');
    if (tagSelect) {
        const currentTag = (op && window.operacionesData?.asset_tags?.[op.ticker]) || '';
        const tagsList = window.operacionesData?.tags_config || [];
        tagSelect.innerHTML = `
            <option value="">🎯 Capital Táctico (Por defecto / 5%)</option>
            ${tagsList.map(t => `<option value="${t.tag_id}" ${currentTag === t.tag_id ? 'selected' : ''}>${t.nombre} (${t.target_pct}%)</option>`).join('')}
        `;
        tagSelect.value = currentTag;
    }
    
    actualizarPreviewOperacion();
    document.getElementById('opModal').showModal();
};

window.consultarTasaCambioModal = async () => {
    const fecha = document.getElementById('op-fecha')?.value || new Date().toISOString().split('T')[0];
    let moneda = document.getElementById('op-moneda')?.value;
    const ticker = document.getElementById('op-ticker')?.value.trim().toUpperCase();
    
    if (!moneda && ticker && window.operacionesData?.activos_info?.[ticker]?.currency) {
        moneda = window.operacionesData.activos_info[ticker].currency;
    }
    if (!moneda || moneda === 'EUR') {
        const tasaInput = document.getElementById('op-tasa-cambio');
        if (tasaInput) tasaInput.value = '1.0';
        window.actualizarPreviewOperacion();
        return;
    }
    
    const btn = document.getElementById('btn-fetch-rate');
    try {
        if (btn) btn.innerHTML = '<span class="spinner-border spinner-border-sm" style="width:0.8rem; height:0.8rem;"></span>';
        const res = await API.fetch(`/api/exchange-rate?currency=${encodeURIComponent(moneda)}&date=${encodeURIComponent(fecha)}`);
        if (res && res.rate) {
            const tasaInput = document.getElementById('op-tasa-cambio');
            if (tasaInput) tasaInput.value = res.rate;
            UI.showToast(`Tasa obtenida: 1 ${moneda} = ${parseFloat(res.rate).toFixed(4)} €`, 'info');
            window.actualizarPreviewOperacion();
        }
    } catch (e) {
        UI.showToast('No se pudo obtener la tasa de cambio: ' + (e.message || e), 'error');
    } finally {
        if (btn) btn.innerHTML = '🔄';
    }
};

window.actualizarPreviewOperacion = () => {
    const tipo = document.getElementById('op-tipo')?.value || 'COMPRA';
    const isCompra = ['COMPRA', 'APORTACION', 'ENTRADA_INMUEBLE', 'HIPOTECA_CUOTA', 'REFORMA_MEJORA'].includes(tipo);
    const cantidad = parseFloat(document.getElementById('op-cantidad')?.value) || 0;
    const precio = parseFloat(document.getElementById('op-precio')?.value) || 0;
    const comisiones = parseFloat(document.getElementById('op-comisiones')?.value) || 0;
    const impuestos = parseFloat(document.getElementById('op-impuestos')?.value) || 0;
    const tasa = parseFloat(document.getElementById('op-tasa-cambio')?.value) || 1.0;
    
    let moneda = document.getElementById('op-moneda')?.value;
    const ticker = document.getElementById('op-ticker')?.value.trim().toUpperCase();
    if (!moneda && ticker && window.operacionesData?.activos_info?.[ticker]?.currency) {
        moneda = window.operacionesData.activos_info[ticker].currency;
    }
    moneda = moneda || 'EUR';

    const subtotal = isCompra
        ? (cantidad * precio) + comisiones + impuestos
        : (cantidad * precio) - comisiones - impuestos;
    const totalEur = subtotal * tasa;

    const previewEl = document.getElementById('op-live-total');
    if (previewEl) {
        if (moneda !== 'EUR') {
            previewEl.innerHTML = `${UI.formatCurrency(totalEur, 'EUR')} <span class="text-secondary opacity-75 font-monospace" style="font-size:0.75rem;">(${UI.formatCurrency(subtotal, moneda)})</span>`;
        } else {
            previewEl.textContent = UI.formatCurrency(totalEur, 'EUR');
        }
    }
};

window.borrarOperacion = async (id) => {
    if (!confirm('¿Seguro que deseas eliminar esta operación?')) return;
    try {
        await API.fetch(`/api/operaciones/${id}`, { method: 'DELETE' });
        UI.showToast('Operación eliminada');
        window.cargarOperaciones();
    } catch (err) {
        UI.showToast('No se pudo eliminar', 'error');
    }
};

window.exportExcel = (type) => window.location.href = `/api/export/${type}`;

window.importExcel = async (type, inputElement) => {
    const file = inputElement.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`/api/import/${type}`, { method: 'POST', body: formData });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.error || 'Error al importar');
        }
        UI.showToast('Datos importados correctamente');
        if (type === 'operaciones') window.cargarOperaciones();
    } catch (err) {
        UI.showToast(err.message, 'error');
    } finally {
        inputElement.value = '';
    }
};

// --- Listeners de Formularios ---
document.addEventListener('DOMContentLoaded', () => {
    // Relleno predictivo en ticker
    const tickerInput = document.getElementById('op-ticker');
    if (tickerInput) {
        tickerInput.addEventListener('input', window.handleTickerPredictivo);
        tickerInput.addEventListener('change', window.handleTickerPredictivo);
    }

    // Actualización de preview interactiva
    ['op-cantidad', 'op-precio', 'op-comisiones', 'op-impuestos', 'op-tasa-cambio', 'op-moneda', 'op-tipo'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', window.actualizarPreviewOperacion);
            el.addEventListener('change', window.actualizarPreviewOperacion);
        }
    });

    // Formulario de Registrar Alerta / Inmueble
    const addForm = document.getElementById('add-form');
    if (addForm) {
        addForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('add-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            try {
                const formData = new FormData(e.target);
                const tipoActivo = formData.get('tipo_activo') || 'FINANCIERO';
                
                if (tipoActivo === 'INMUEBLE') {
                    const payload = {
                        tipo_activo: 'INMUEBLE',
                        ticker: formData.get('ticker'),
                        name: formData.get('name') || formData.get('ticker'),
                        comunidad_autonoma: formData.get('comunidad_autonoma'),
                        pct_titularidad: (parseFloat(formData.get('pct_titularidad')) || 100) / 100.0,
                        precio_compra_total: parseFloat(formData.get('precio_compra_total')) || 0,
                        hipoteca_inicial: parseFloat(formData.get('hipoteca_inicial')) || 0
                    };
                    await API.post('/api/add', payload);
                    UI.showToast('Inmueble registrado correctamente');
                } else {
                    const ticker = formData.get('ticker');
                    const target = formData.get('target');
                    const target_pct = formData.get('target_pct');
                    await API.post('/api/add', { 
                        ticker, 
                        target, 
                        target_pct: target_pct ? parseFloat(target_pct) : 0 
                    });
                    UI.showToast('Alerta añadida correctamente');
                }
                addForm.reset();
                toggleAddAssetFields('FINANCIERO');
                window.cargarOperaciones();
            } catch (err) {
                UI.showToast(err.message, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Guardar';
            }
        });
    }

    // Formulario de Operación (op-form)
    const opForm = document.getElementById('op-form');
    if (opForm) {
        opForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('op-submit-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            
            try {
                const formData = new FormData(e.target);
                const opId = formData.get('id');
                const isEdit = !!opId;
                const tasaVal = formData.get('tasa_cambio');
                
                const getSafeFloat = (name) => {
                    const val = formData.get(name);
                    if (val === null || val === undefined) return 0;
                    const parsed = parseFloat(String(val).trim().replace(',', '.'));
                    return isNaN(parsed) ? 0 : parsed;
                };

                const getSafeString = (name) => {
                    const val = formData.get(name);
                    return val ? String(val).trim() : '';
                };

                const payload = {
                    fecha: getSafeString('fecha'),
                    ticker: getSafeString('ticker').toUpperCase(),
                    tipo: getSafeString('tipo'),
                    cantidad: getSafeFloat('cantidad') || 1,
                    precio: getSafeFloat('precio'),
                    moneda: getSafeString('moneda') || null,
                    comisiones: getSafeFloat('comisiones'),
                    impuestos: getSafeFloat('impuestos'),
                    tag_id: getSafeString('tag_id') || null,
                    tasa_cambio: tasaVal ? getSafeFloat('tasa_cambio') : null,
                    amortizacion: getSafeFloat('amortizacion'),
                    intereses: getSafeFloat('intereses'),
                    comunidad_autonoma: getSafeString('comunidad_autonoma'),
                    pct_titularidad: getSafeFloat('pct_titularidad') ? getSafeFloat('pct_titularidad') / 100.0 : null,
                    precio_compra_total: getSafeFloat('precio_compra_total'),
                    hipoteca_inicial: getSafeFloat('hipoteca_inicial')
                };
                
                const url = isEdit ? `/api/operaciones/edit/${opId}` : '/api/operaciones/add';
                const method = isEdit ? 'PUT' : 'POST';

                await API.fetch(url, {
                    method: method,
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                
                UI.showToast(`Operación ${isEdit ? 'actualizada' : 'registrada'} con éxito`);
                document.getElementById('opModal').close();
                window.cargarOperaciones();
            } catch (err) {
                UI.showToast(err.message || err, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Guardar Operación';
            }
        });
    }
});
