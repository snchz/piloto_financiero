/**
 * Portfolio & Market Visualization Service
 * Gestión de cartera en vivo, Modo Mirón, curvas de patrimonio, benchmark VWCE y distribución
 */

let operacionesData = null;
window.operacionesData = null;
let rawHistoryData = null;

// --- Modo Mirón ---
window.modoMiron = false;

window.toggleModoMiron = () => {
    window.modoMiron = !window.modoMiron;
    const btn = document.getElementById('btn-modo-miron');
    const icono = document.getElementById('icono-miron');
    if (btn && icono) {
        if (window.modoMiron) {
            btn.style.background = 'rgba(99, 102, 241, 0.25)';
            btn.style.borderColor = 'rgba(129, 140, 248, 0.5)';
            btn.style.boxShadow = '0 0 10px rgba(99, 102, 241, 0.35)';
            icono.style.opacity = '1';
            icono.style.filter = 'none';
            icono.style.transform = 'scale(1.15)';
        } else {
            btn.style.background = 'rgba(255, 255, 255, 0.04)';
            btn.style.borderColor = 'var(--border-color)';
            btn.style.boxShadow = 'none';
            icono.style.opacity = '0.55';
            icono.style.filter = 'grayscale(1)';
            icono.style.transform = 'scale(1)';
        }
    }
    window.cargarOperaciones();
    if (typeof window.cargarFire === 'function') window.cargarFire();
};

// --- Filtro de Rango Temporal para la Curva de Patrimonio ---
window.filtrarRangoHistorico = (rango, btnEl) => {
    if (!rawHistoryData || !rawHistoryData.labels) return;
    
    if (btnEl) {
        document.querySelectorAll('#time-range-selector .time-btn').forEach(b => b.classList.remove('active'));
        btnEl.classList.add('active');
    }

    const labels = rawHistoryData.labels;
    if (labels.length === 0) return;

    const lastDateStr = labels[labels.length - 1];
    const lastDate = new Date(lastDateStr);
    let minDate = new Date(0);

    if (rango === '1M') {
        minDate = new Date(lastDate); minDate.setMonth(minDate.getMonth() - 1);
    } else if (rango === '3M') {
        minDate = new Date(lastDate); minDate.setMonth(minDate.getMonth() - 3);
    } else if (rango === '6M') {
        minDate = new Date(lastDate); minDate.setMonth(minDate.getMonth() - 6);
    } else if (rango === '1Y') {
        minDate = new Date(lastDate); minDate.setFullYear(minDate.getFullYear() - 1);
    } else if (rango === 'YTD') {
        minDate = new Date(lastDate.getFullYear(), 0, 1);
    }

    const filteredIndices = [];
    labels.forEach((dStr, idx) => {
        if (new Date(dStr) >= minDate) filteredIndices.push(idx);
    });

    const newLabels = filteredIndices.map(i => labels[i]);
    const newCapital = filteredIndices.map(i => rawHistoryData.capital[i]);
    const newValues = filteredIndices.map(i => rawHistoryData.values[i]);
    const newBench = rawHistoryData.benchmark_values ? filteredIndices.map(i => rawHistoryData.benchmark_values[i]) : null;

    renderizarGraficoEvolucion({
        labels: newLabels,
        capital: newCapital,
        values: newValues,
        benchmark_values: newBench
    });
};

function renderizarGraficoEvolucion(history) {
    if (window.equityCurveChartInstance) {
        window.equityCurveChartInstance.destroy();
    }
    const ctxLine = document.getElementById('equityCurveChart');
    if (!ctxLine) return;

    if (!history || history.labels.length === 0) {
        history = { labels: [new Date().toISOString().split('T')[0]], capital: [0], values: [0] };
    }

    const ctx = ctxLine.getContext('2d');
    const gradientValue = ctx.createLinearGradient(0, 0, 0, 240);
    gradientValue.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
    gradientValue.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

    const gradientCapital = ctx.createLinearGradient(0, 0, 0, 240);
    gradientCapital.addColorStop(0, 'rgba(99, 102, 241, 0.2)');
    gradientCapital.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

    const datasets = [
        {
            label: 'Capital Aportado',
            data: history.capital,
            borderColor: '#6366f1',
            backgroundColor: gradientCapital,
            borderWidth: 2,
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 5
        },
        {
            label: 'Valor de Mercado',
            data: history.values,
            borderColor: '#10b981',
            backgroundColor: gradientValue,
            borderWidth: 2.5,
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 6
        }
    ];

    if (history.benchmark_values && history.benchmark_values.length > 0) {
        datasets.push({
            label: 'Benchmark (VWCE)',
            data: history.benchmark_values,
            borderColor: '#f59e0b',
            backgroundColor: 'transparent',
            borderWidth: 2,
            borderDash: [5, 5],
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.35,
            fill: false
        });
    }

    window.equityCurveChartInstance = new Chart(ctxLine, {
        type: 'line',
        data: {
            labels: history.labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    position: 'top',
                    align: 'end',
                    labels: { color: '#94a3b8', font: { size: 11, family: "'Inter', sans-serif" }, usePointStyle: true, boxWidth: 8 }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 18, 26, 0.95)',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
                    bodyFont: { family: "'Inter', sans-serif", size: 12 },
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) label += ': ';
                            if (context.parsed.y !== null) {
                                label += UI.formatCurrency(context.parsed.y, 'EUR');
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: { 
                    grid: { color: 'rgba(255, 255, 255, 0.04)', drawBorder: false }, 
                    ticks: { 
                        color: '#94a3b8', 
                        font: { size: 10, family: "'JetBrains Mono', monospace" },
                        maxTicksLimit: 8,
                        maxRotation: 0
                    } 
                },
                y: {
                    beginAtZero: false,
                    grid: { color: 'rgba(255, 255, 255, 0.04)', drawBorder: false },
                    ticks: { 
                        color: '#94a3b8', 
                        font: { size: 10, family: "'JetBrains Mono', monospace" },
                        callback: function(value) { return new Intl.NumberFormat('es-ES', { notation: "compact", compactDisplay: "short" }).format(value); }
                    }
                }
            }
        }
    });

    const toggle = document.getElementById('toggleBenchmark');
    if (toggle && window.equityCurveChartInstance) {
        const chart = window.equityCurveChartInstance;
        const benchIdx = chart.data.datasets.findIndex(ds => ds.label === 'Benchmark (VWCE)');
        if (benchIdx > -1) {
            chart.setDatasetVisibility(benchIdx, toggle.checked);
            chart.update('none');
        }
    }
}

// --- Carga Principal de Operaciones y Métricas ---
window.cargarOperaciones = async () => {
    try {
        const includeRealEstate = document.getElementById('toggleRealEstate')?.checked ?? false;
        const mironParam = window.modoMiron ? '&miron=1' : '';
        const data = await API.fetch(`/api/operaciones?include_real_estate=${includeRealEstate ? 1 : 0}${mironParam}`);
        operacionesData = data;
        window.operacionesData = data;
        
        if (data.warning_api_error) {
            UI.showToast('No se pudieron actualizar algunos precios en tiempo real.', 'warning');
        }
        
        // 1. Renderizar Cartera y calcular variación del día
        let totalValor = 0;
        let totalLatente = 0;
        let totalVariacionDiaEur = 0;
        let totalPrevCloseValor = 0;
        let activosCount = 0;

        const carteraEntries = Object.entries(data.cartera);
        activosCount = carteraEntries.length;
        const countEl = document.getElementById('count-cartera-activos');
        if (countEl) countEl.textContent = `${activosCount} activo${activosCount === 1 ? '' : 's'}`;

        const carteraHtml = carteraEntries.map(([ticker, metrics]) => {
            const latenteClass = metrics.pnl_latente >= 0 ? 'text-success' : 'text-danger';
            const latenteSign = metrics.pnl_latente >= 0 ? '+' : '';
            const currency = metrics.currency || 'USD';
            const tasa = metrics.tasa_cambio || 1;
            const isInmueble = metrics.tipo === 'INMUEBLE';
            
            const valorBase = metrics.valor_actual * tasa;
            totalValor += valorBase;
            totalLatente += metrics.pnl_latente * tasa;

            if (metrics.previous_close && metrics.previous_close > 0 && metrics.cantidad > 0) {
                const prevValorBase = metrics.cantidad * metrics.previous_close * tasa;
                totalPrevCloseValor += prevValorBase;
                totalVariacionDiaEur += (valorBase - prevValorBase);
            }

            const rentPctClass = metrics.rentabilidad_pct >= 0 ? 'text-success' : 'text-danger';
            const rentPctSign = metrics.rentabilidad_pct >= 0 ? '+' : '';
            const rentPctStr = (metrics.rentabilidad_pct * 100).toFixed(2) + '%';

            let varBadgeHtml = '';
            if (metrics.previous_close && metrics.previous_close > 0) {
                const varPct = ((metrics.precio_actual - metrics.previous_close) / metrics.previous_close) * 100;
                const isUp = varPct >= 0;
                const badgeStyle = isUp 
                    ? 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);' 
                    : 'background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3);';
                varBadgeHtml = `<span class="badge font-monospace ms-1 px-2 py-1" style="${badgeStyle} font-size:0.72rem;">${isUp ? '+' : ''}${varPct.toFixed(2)}%</span>`;
            }
            
            let priceTooltip = `Actualizado: ${metrics.current_price_time || 'N/A'}`;
            if (isInmueble) {
                priceTooltip = `Valor Bruto Tu Parte: ${UI.formatCurrency(metrics.valor_bruto || 0, currency)}\nDeuda Pendiente Tu Parte: ${UI.formatCurrency(metrics.deuda_pendiente || 0, currency)}\nRevalorización automática INE IPV (${metrics.comunidad_autonoma || 'NACIONAL'})`;
            } else if (metrics.max_price || metrics.min_price) {
                priceTooltip += `\nMáx compra: ${metrics.max_price ? UI.formatCurrency(metrics.max_price, currency) : '-'}\nMín compra: ${metrics.min_price ? UI.formatCurrency(metrics.min_price, currency) : '-'}`;
            }

            const inmBadge = isInmueble ? `<span class="badge bg-info bg-opacity-10 text-info border border-info border-opacity-25 ms-1" style="font-size:0.65rem;">🏠 INMUEBLE (${metrics.comunidad_autonoma || 'INE'})</span>` : '';

            let tagBadge = '';
            if (!isInmueble) {
                const currentTag = data.asset_tags?.[ticker] || '';
                const activeTagObj = (data.tags_config || []).find(t => t.tag_id === currentTag);
                const tColor = activeTagObj ? (activeTagObj.color || '#3b82f6') : (currentTag === 'tactical' ? '#8b5cf6' : '#64748b');
                const tNombre = activeTagObj ? `${activeTagObj.nombre} (${activeTagObj.target_pct}%)` : (currentTag === 'tactical' ? 'Capital Táctico (5%)' : '⚙️ Asignar Categoría');

                tagBadge = `
                    <div class="dropdown d-inline-block ms-1">
                        <button class="badge font-monospace border-0 dropdown-toggle py-1 px-2" type="button" data-bs-toggle="dropdown" aria-expanded="false" style="background: ${tColor}25; color: ${tColor}; border: 1px solid ${tColor}50; font-size: 0.68rem; cursor: pointer;" title="Clic para asignar o cambiar la categoría estratégica">
                            🏷️ ${tNombre}
                        </button>
                        <ul class="dropdown-menu dropdown-menu-dark p-1 shadow-lg" style="font-size: 0.78rem; z-index: 1050;">
                            <li><h6 class="dropdown-header py-1 text-secondary" style="font-size: 0.7rem;">Asignar a ${ticker}:</h6></li>
                            <li><a class="dropdown-item py-1 ${!currentTag ? 'active' : ''}" href="javascript:void(0)" onclick="asignarTagActivo('${ticker}', '')">🎯 Capital Táctico (Por defecto)</a></li>
                            ${(data.tags_config || []).map(t => `
                                <li><a class="dropdown-item py-1 ${currentTag === t.tag_id ? 'active' : ''}" href="javascript:void(0)" onclick="asignarTagActivo('${ticker}', '${t.tag_id}')">
                                    <span style="color: ${t.color}">●</span> ${t.nombre} (${t.target_pct}%)
                                </a></li>
                            `).join('')}
                        </ul>
                    </div>
                `;
            }

            return `
            <tr>
                <td class="ps-4">
                    <div class="fw-bold text-white d-flex align-items-center flex-wrap gap-1">${metrics.name || ticker} ${inmBadge} ${tagBadge}</div>
                    <div class="text-secondary font-monospace" style="font-size: 0.7rem;">${ticker}</div>
                </td>
                <td class="text-end font-monospace text-light">${metrics.cantidad.toFixed(4)}</td>
                <td class="text-end font-monospace text-secondary">${UI.formatCurrency(metrics.coste_medio, currency)}</td>
                <td class="text-end" title="${priceTooltip}" style="cursor: help;">
                    <div class="d-flex justify-content-end align-items-center gap-1">
                        <span class="font-monospace fs-6 fw-semibold text-white">${UI.formatCurrency(metrics.precio_actual, currency)}</span>
                        ${varBadgeHtml}
                    </div>
                </td>
                <td class="text-end font-monospace text-white fw-bold">${UI.formatCurrency(metrics.valor_actual, currency)}</td>
                <td class="text-end font-monospace ${rentPctClass}">${rentPctSign}${rentPctStr}</td>
                <td class="text-end font-monospace ${latenteClass} pe-4 fw-semibold">${latenteSign}${UI.formatCurrency(metrics.pnl_latente, currency)}</td>
            </tr>
        `}).join('');
        
        const carteraTable = document.getElementById('cartera-table');
        if (carteraTable) carteraTable.innerHTML = carteraHtml || '<tr><td colspan="7" class="text-center py-4 text-secondary">No hay activos en cartera</td></tr>';

        // 2. Renderizar Operaciones
        const sortedOps = [...data.operaciones].reverse();
        const opsHtml = sortedOps.map(op => {
            const isCompra = op.tipo === 'COMPRA' || op.tipo === 'APORTACION' || op.tipo === 'ENTRADA_INMUEBLE' || op.tipo === 'HIPOTECA_CUOTA' || op.tipo === 'REFORMA_MEJORA';
            const isDividendo = op.tipo === 'DIVIDENDO';
            
            let badgeStyle = 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);';
            if (op.tipo === 'APORTACION' || op.tipo === 'ENTRADA_INMUEBLE') {
                badgeStyle = 'background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3);';
            } else if (op.tipo === 'HIPOTECA_CUOTA') {
                badgeStyle = 'background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3);';
            } else if (op.tipo === 'REFORMA_MEJORA') {
                badgeStyle = 'background: rgba(236, 72, 153, 0.15); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.3);';
            } else if (op.tipo === 'VENTA') {
                badgeStyle = 'background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3);';
            } else if (isDividendo) {
                badgeStyle = 'background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3);';
            }
            
            const info = data.activos_info[op.ticker] || {};
            const currency = op.moneda || info.currency || 'USD';
            const name = info.name || '';
            
            let rentabilidadHtml = '-';
            if (op.tipo === 'VENTA' || op.tipo === 'DIVIDENDO') {
                const pnlEur = op.pnl_base !== undefined ? op.pnl_base : (op.pnl !== undefined ? op.pnl : null);
                const pnlOrig = op.pnl !== undefined ? op.pnl : null;
                if (pnlEur !== null) {
                    const pnlClass = pnlEur >= 0 ? 'text-success' : 'text-danger';
                    const pnlSign = pnlEur > 0 ? '+' : '';
                    let rentabPctHtml = '';
                    const pctVal = op.rentabilidad !== undefined ? op.rentabilidad : (op.rentabilidad_pct !== undefined ? op.rentabilidad_pct : null);
                    if (pctVal !== null && op.tipo !== 'DIVIDENDO') {
                        rentabPctHtml = `<br><span style="font-size: 0.75em">(${pctVal > 0 ? '+' : ''}${(pctVal * 100).toFixed(2)}%)</span>`;
                    }
                    const pnlOrigSub = (currency !== 'EUR' && pnlOrig !== null)
                        ? `<br><span class="text-secondary opacity-75 font-monospace" style="font-size:0.7rem;">(${pnlSign}${UI.formatCurrency(pnlOrig, currency)})</span>`
                        : '';
                    rentabilidadHtml = `<span class="${pnlClass}">${pnlSign}${UI.formatCurrency(pnlEur, 'EUR')}</span>${pnlOrigSub}${rentabPctHtml}`;
                }
            }

            const comisiones = op.comisiones || 0;
            const impuestos = op.impuestos || 0;
            const totalOperacion = isCompra 
                ? (op.cantidad * op.precio) + comisiones + impuestos
                : (op.cantidad * op.precio) - comisiones - impuestos;
            const tasaCambio = op.tasa_cambio || 1.0;
            const totalOperacionEur = totalOperacion * tasaCambio;
            const totalSubtext = (currency !== 'EUR')
                ? `<br><span class="text-secondary opacity-75 font-monospace" style="font-size: 0.7rem;">${UI.formatCurrency(totalOperacion, currency)}</span>`
                : '';

            const isHipoteca = op.tipo === 'HIPOTECA_CUOTA';
            const hipoSubtext = isHipoteca && (op.amortizacion || op.intereses)
                ? `<br><span class="text-info opacity-75" style="font-size:0.7rem;">Cap: ${UI.formatCurrency(op.amortizacion || 0, currency)}</span> <span class="text-warning opacity-75" style="font-size:0.7rem;">Int: ${UI.formatCurrency(op.intereses || 0, currency)}</span>`
                : '';

            return `
            <tr data-tipo="${op.tipo}">
                <td class="ps-4 font-monospace text-secondary" style="font-size: 0.82rem">${op.fecha}</td>
                <td>
                    <div class="fw-bold text-white">${name || op.ticker}</div>
                    <div class="text-secondary font-monospace" style="font-size: 0.7rem;">${op.ticker} <span class="badge bg-dark border border-secondary border-opacity-25 opacity-75">${currency}</span></div>
                </td>
                <td class="text-center">
                    <span class="badge font-monospace px-2 py-1" style="${badgeStyle} font-size:0.72rem;">${op.tipo}</span>
                </td>
                <td class="text-end font-monospace text-light">${op.cantidad.toFixed(4)}</td>
                <td class="text-end font-monospace">${UI.formatCurrency(op.precio, currency)}${hipoSubtext}</td>
                <td class="text-end font-monospace text-secondary">${UI.formatCurrency(comisiones, currency)}</td>
                <td class="text-end font-monospace text-secondary">${UI.formatCurrency(impuestos, currency)}</td>
                <td class="text-end font-monospace text-white fw-semibold">${UI.formatCurrency(totalOperacionEur, 'EUR')}${totalSubtext}</td>
                <td class="text-end font-monospace">${rentabilidadHtml}</td>
                <td class="text-end pe-4">
                    <button onclick="abrirModalOperacion('${op.id}')" class="action-btn me-1" title="Editar">
                        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                    </button>
                    <button onclick="borrarOperacion('${op.id}')" class="action-btn delete" title="Eliminar">
                        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                </td>
            </tr>
        `}).join('');
        
        const opTable = document.getElementById('operaciones-table');
        if (opTable) opTable.innerHTML = opsHtml || '<tr><td colspan="10" class="text-center py-4 text-secondary">No hay operaciones registradas</td></tr>';
        
        if (typeof window.setupOperacionesFilter === 'function') window.setupOperacionesFilter();
        if (typeof window.aplicarFiltroOperaciones === 'function') window.aplicarFiltroOperaciones();

        // 3. Renderizar KPIs Resumen Global
        const valTotalEl = document.getElementById('resumen-valor-total');
        if (valTotalEl) valTotalEl.textContent = UI.formatCurrency(totalValor, 'EUR');
        
        // Variación del Día
        let varDiaPct = 0;
        if (totalPrevCloseValor > 0) {
            varDiaPct = (totalVariacionDiaEur / totalPrevCloseValor) * 100;
        }
        const varBadge = document.getElementById('resumen-variacion-dia');
        if (varBadge) {
            if (totalPrevCloseValor > 0 && totalVariacionDiaEur !== 0) {
                varBadge.style.display = 'inline-block';
                varBadge.style.cssText = totalVariacionDiaEur >= 0 
                    ? 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.75rem;'
                    : 'background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); font-size: 0.75rem;';
                varBadge.textContent = `${totalVariacionDiaEur >= 0 ? '▲ +' : '▼ '}${UI.formatCurrency(totalVariacionDiaEur, 'EUR')} (${varDiaPct >= 0 ? '+' : ''}${varDiaPct.toFixed(2)}%) hoy`;
            } else {
                varBadge.style.display = 'none';
            }
        }

        // P&L Combined
        const totalCombinedPnl = totalLatente + (data.total_pnl_realizado || 0);
        const pnlCombinedSpan = document.getElementById('resumen-total-pnl-combined');
        if (pnlCombinedSpan) {
            pnlCombinedSpan.className = `text-secondary small font-monospace ${totalCombinedPnl >= 0 ? 'text-success' : 'text-danger'}`;
            pnlCombinedSpan.textContent = `P&L Total: ${totalCombinedPnl >= 0 ? '+' : ''}${UI.formatCurrency(totalCombinedPnl, 'EUR')}`;
        }

        // TIR & TWR
        const tirEl = document.getElementById('resumen-tir');
        if (tirEl) {
            tirEl.textContent = data.tir_anualizada ? (data.tir_anualizada * 100).toFixed(2) + '%' : 'N/A';
            tirEl.className = 'fs-4 fw-bold font-monospace my-1 ' + (data.tir_anualizada >= 0 ? 'text-success' : 'text-danger');
        }
        
        const tirRealEl = document.getElementById('resumen-tir-real');
        if (tirRealEl) {
            if (data.tir_anualizada_real !== undefined && data.tir_anualizada_real !== null) {
                const tirRealSign = data.tir_anualizada_real >= 0 ? '+' : '';
                tirRealEl.textContent = `Real: ${tirRealSign}${(data.tir_anualizada_real * 100).toFixed(2)}%`;
                tirRealEl.className = 'font-monospace ' + (data.tir_anualizada_real >= 0 ? 'text-info' : 'text-danger') + ' fw-semibold';
            } else {
                tirRealEl.textContent = 'Real: --';
            }
        }

        const metricas = data.metricas_riesgo || { twr: 0, volatilidad: 0, sharpe: 0, max_drawdown: 0 };
        const twrEl = document.getElementById('resumen-twr');
        if (twrEl) {
            twrEl.textContent = metricas.twr !== undefined ? (metricas.twr * 100).toFixed(2) + '%' : 'N/A';
            twrEl.className = 'fs-4 fw-bold font-monospace my-1 ' + (metricas.twr >= 0 ? 'text-success' : 'text-danger');
        }
        
        const twrRealEl = document.getElementById('resumen-twr-real');
        if (twrRealEl) {
            if (metricas.twr_real !== undefined && metricas.twr_real !== null) {
                const twrRealSign = metricas.twr_real >= 0 ? '+' : '';
                twrRealEl.textContent = `Real: ${twrRealSign}${(metricas.twr_real * 100).toFixed(2)}%`;
                twrRealEl.className = 'font-monospace ' + (metricas.twr_real >= 0 ? 'text-info' : 'text-danger') + ' fw-semibold';
            } else {
                twrRealEl.textContent = 'Real: --';
            }
        }

        const latenteEl = document.getElementById('resumen-latente');
        if (latenteEl) {
            latenteEl.textContent = UI.formatCurrency(totalLatente, 'EUR');
            latenteEl.className = 'fs-4 fw-bold font-monospace my-1 ' + (totalLatente >= 0 ? 'text-success' : 'text-danger');
        }
        
        const realizadoEl = document.getElementById('resumen-realizado');
        if (realizadoEl) {
            realizadoEl.textContent = UI.formatCurrency(data.total_pnl_realizado, 'EUR');
            realizadoEl.className = 'fs-4 fw-bold font-monospace my-1 ' + (data.total_pnl_realizado >= 0 ? 'text-success' : 'text-danger');
        }
        
        // Métricas de riesgo
        const volEl = document.getElementById('resumen-volatilidad');
        if (volEl) volEl.textContent = metricas.volatilidad !== undefined ? (metricas.volatilidad * 100).toFixed(2) + '%' : 'N/A';
        
        const sharpeEl = document.getElementById('resumen-sharpe');
        if (sharpeEl) sharpeEl.textContent = metricas.sharpe !== undefined ? metricas.sharpe.toFixed(2) : 'N/A';
        
        const ddEl = document.getElementById('resumen-drawdown');
        if (ddEl) ddEl.textContent = metricas.max_drawdown !== undefined ? (metricas.max_drawdown * 100).toFixed(2) + '%' : 'N/A';
        
        const inflacionEl = document.getElementById('resumen-inflacion');
        if (inflacionEl) {
            if (metricas.inflacion_acumulada !== undefined && metricas.inflacion_acumulada !== null) {
                const infSign = metricas.inflacion_acumulada >= 0 ? '+' : '';
                inflacionEl.textContent = `${infSign}${(metricas.inflacion_acumulada * 100).toFixed(2)}% (${(metricas.inflacion_anualizada * 100).toFixed(2)}% a.)`;
            } else {
                inflacionEl.textContent = 'N/A';
            }
        }

        // 4. Renderizar Gráfico de Líneas con Filtro de Rango
        rawHistoryData = data.history;
        renderizarGraficoEvolucion(rawHistoryData);

        // 5. Renderizar Gráficos Donut
        const allocationLabels = [];
        const allocationData = [];
        const currencyAlloc = {};
        const bgColors = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#f59e0b', '#10b981', '#0ea5e9', '#3b82f6', '#14b8a6'];

        Object.entries(data.cartera).forEach(([ticker, m]) => {
            const valorBase = m.valor_actual * (m.tasa_cambio || 1);
            if (valorBase > 0) {
                allocationLabels.push(m.name || ticker);
                allocationData.push(valorBase);
                const curr = (m.currency && m.currency !== '-') ? m.currency.toUpperCase() : 'EUR';
                currencyAlloc[curr] = (currencyAlloc[curr] || 0) + valorBase;
            }
        });

        if (window.allocationChartInstance) window.allocationChartInstance.destroy();
        if (allocationLabels.length > 0) {
            const ctx = document.getElementById('allocationChart');
            if (ctx) {
                window.allocationChartInstance = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: allocationLabels,
                        datasets: [{
                            data: allocationData,
                            backgroundColor: bgColors.slice(0, allocationLabels.length),
                            borderWidth: 2,
                            borderColor: '#11141e',
                            hoverOffset: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: { color: '#94a3b8', font: { size: 10, family: "'Inter', sans-serif" }, boxWidth: 10 }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        let label = context.label || '';
                                        if (label) label += ': ';
                                        if (context.parsed !== null) {
                                            label += UI.formatCurrency(context.parsed, 'EUR');
                                        }
                                        return label;
                                    }
                                }
                            }
                        },
                        cutout: '72%'
                    }
                });
            }
        }

        if (window.currencyChartInstance) window.currencyChartInstance.destroy();
        const currencyLabels = Object.keys(currencyAlloc);
        const currencyData = Object.values(currencyAlloc);
        if (currencyLabels.length > 0) {
            const ctxCurr = document.getElementById('currencyChart');
            if (ctxCurr) {
                window.currencyChartInstance = new Chart(ctxCurr, {
                    type: 'doughnut',
                    data: {
                        labels: currencyLabels,
                        datasets: [{
                            data: currencyData,
                            backgroundColor: bgColors.slice(0, currencyLabels.length),
                            borderWidth: 2,
                            borderColor: '#11141e',
                            hoverOffset: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 10, family: "'Inter', sans-serif" }, boxWidth: 10 } },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        let label = context.label ? context.label + ': ' : '';
                                        return label + (context.parsed !== null ? UI.formatCurrency(context.parsed, 'EUR') : '');
                                    }
                                }
                            }
                        },
                        cutout: '72%'
                    }
                });
            }
        }

        // 6. Actualizar Estrategia y Rebalanceo
        if (typeof window.cargarRebalanceo === 'function') {
            await window.cargarRebalanceo();
        }

    } catch (err) {
        console.error('Error cargando operaciones:', err);
        UI.showToast(`Error cargando cartera: ${err.message || err}`, 'error');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const toggleBenchmark = document.getElementById('toggleBenchmark');
    if (toggleBenchmark) {
        toggleBenchmark.addEventListener('change', function() {
            if (!window.equityCurveChartInstance) return;
            const chart = window.equityCurveChartInstance;
            const datasetIndex = chart.data.datasets.findIndex(ds => ds.label === 'Benchmark (VWCE)');
            if (datasetIndex > -1) {
                chart.setDatasetVisibility(datasetIndex, this.checked);
                chart.update();
            }
        });
    }

    const chartTabs = document.querySelectorAll('#chartTabs button[data-bs-toggle="tab"]');
    chartTabs.forEach(tab => {
        tab.addEventListener('shown.bs.tab', () => {
            if (window.allocationChartInstance) window.allocationChartInstance.resize();
            if (window.currencyChartInstance) window.currencyChartInstance.resize();
        });
    });
});
