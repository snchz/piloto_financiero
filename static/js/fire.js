/**
 * Financial Independence (FIRE) Simulation Service
 * Proyección actuarial, simulador paramétrico, gráficos de acumulación e hitos
 */

let debounceFireTimer = null;
let lastFireData = null;

async function cargarFire(customParams = null) {
    try {
        const mironParam = window.modoMiron ? '&miron=1' : '';
        let url = '/api/fire?' + (mironParam ? mironParam.substring(1) : '');
        if (customParams) {
            url += (url.includes('?') ? '&' : '?') + customParams;
        }
        const data = await API.fetch(url);
        lastFireData = data;
        renderizarDatosFire(data);
    } catch (err) {
        console.error("Error cargando datos FIRE:", err);
    }
}
window.cargarFire = cargarFire;

function renderizarDatosFire(data) {
    if (!data) return;

    // KPIs
    const targetEl = document.getElementById('fire-kpi-target');
    if (targetEl) targetEl.textContent = UI.formatCurrency(data.fire_target, 'EUR');

    const targetSub = document.getElementById('fire-kpi-target-sub');
    if (targetSub) {
        targetSub.textContent = `Gastos: ${UI.formatCurrency(data.gastos_anuales, 'EUR')}/año · SWR: ${data.swr_pct}% (x${(100/data.swr_pct).toFixed(1)})`;
    }

    const capEl = document.getElementById('fire-kpi-capital');
    if (capEl) capEl.textContent = UI.formatCurrency(data.capital_actual, 'EUR');

    const progBadge = document.getElementById('fire-kpi-progreso-badge');
    if (progBadge) progBadge.textContent = `${data.progreso_pct.toFixed(1)}%`;

    const progBar = document.getElementById('fire-kpi-progress-bar');
    if (progBar) {
        progBar.style.width = `${Math.min(data.progreso_pct, 100)}%`;
    }

    const brechaEl = document.getElementById('fire-kpi-brecha');
    if (brechaEl) brechaEl.textContent = UI.formatCurrency(data.brecha_restante, 'EUR');

    const aportSub = document.getElementById('fire-kpi-aportacion-sub');
    if (aportSub) aportSub.textContent = `Aportando: ${UI.formatCurrency(data.aportacion_mensual, 'EUR')}/m`;

    // Escenario Conservador
    const consRateEl = document.getElementById('fire-kpi-cons-rate');
    if (consRateEl) consRateEl.textContent = `${data.escenario_conservador.tasa_anual_pct}% Real`;

    const consTiempoEl = document.getElementById('fire-kpi-cons-tiempo');
    if (consTiempoEl) {
        if (data.escenario_conservador.anos !== null) {
            consTiempoEl.textContent = `${data.escenario_conservador.anos} años, ${data.escenario_conservador.meses_resto} meses`;
        } else {
            consTiempoEl.textContent = 'Inalcanzable';
        }
    }

    const consFechaEl = document.getElementById('fire-kpi-cons-fecha');
    if (consFechaEl) consFechaEl.textContent = data.escenario_conservador.fecha;

    // Escenario TIR Real
    const tirRateEl = document.getElementById('fire-kpi-tir-rate');
    if (tirRateEl) tirRateEl.textContent = `${data.escenario_tir_real.tasa_anual_pct}% Real`;

    const tirTiempoEl = document.getElementById('fire-kpi-tir-tiempo');
    if (tirTiempoEl) {
        if (data.escenario_tir_real.anos !== null) {
            tirTiempoEl.textContent = `${data.escenario_tir_real.anos} años, ${data.escenario_tir_real.meses_resto} meses`;
        } else {
            tirTiempoEl.textContent = 'Inalcanzable';
        }
    }

    const tirFechaEl = document.getElementById('fire-kpi-tir-fecha');
    if (tirFechaEl) tirFechaEl.textContent = data.escenario_tir_real.fecha;

    // Actualizar inputs si no tienen el foco activo
    const inputGastos = document.getElementById('fire-input-gastos');
    if (inputGastos && document.activeElement !== inputGastos) {
        inputGastos.value = data.gastos_anuales;
    }
    const inputSwr = document.getElementById('fire-input-swr');
    if (inputSwr && document.activeElement !== inputSwr) {
        inputSwr.value = data.swr_pct;
    }
    const inputAport = document.getElementById('fire-input-aportacion');
    if (inputAport && document.activeElement !== inputAport) {
        inputAport.value = data.aportacion_mensual;
    }
    const inputTasaCons = document.getElementById('fire-input-tasa-cons');
    if (inputTasaCons && document.activeElement !== inputTasaCons) {
        inputTasaCons.value = data.escenario_conservador.tasa_anual_pct;
    }

    // Textos secundarios bajo los inputs
    const subGastos = document.getElementById('fire-sub-gastos-mes');
    if (subGastos) subGastos.textContent = `Equivale a ${UI.formatCurrency(data.gastos_mensuales, 'EUR')} / mes`;

    const subSwr = document.getElementById('fire-sub-swr-mult');
    if (subSwr) subSwr.textContent = `Multiplicador: x${(100/data.swr_pct).toFixed(1)} de gastos anuales`;

    const subAportHist = document.getElementById('fire-sub-aportacion-hist');
    if (subAportHist && data.config_guardada) {
        subAportHist.textContent = `Media histórica: ${UI.formatCurrency(data.config_guardada.aportacion_calculada, 'EUR')}/mes`;
    }

    // Renderizar Hitos
    const hitosList = document.getElementById('fire-hitos-list');
    if (hitosList && data.hitos) {
        const nombresHitos = {
            25: 'Coast FIRE (25%)',
            50: 'Halfway FIRE (50%)',
            75: 'Barista / Flamingo (75%)',
            100: 'Full FIRE (100%)'
        };
        hitosList.innerHTML = data.hitos.map(h => {
            const badgeClass = h.superado ? 'bg-success text-white' : 'bg-secondary bg-opacity-25 text-info';
            const icon = h.superado ? '✅' : '⏳';
            return `
                <div class="p-2 rounded-3 d-flex justify-content-between align-items-center" style="background: rgba(255, 255, 255, ${h.superado ? '0.04' : '0.02'}); border: 1px solid rgba(255, 255, 255, ${h.superado ? '0.12' : '0.05'});">
                    <div>
                        <div class="d-flex align-items-center gap-1 mb-1">
                            <span style="font-size: 0.8rem;">${icon}</span>
                            <strong class="text-white small" style="font-size: 0.78rem;">${nombresHitos[h.porcentaje] || (h.porcentaje + '%')}</strong>
                        </div>
                        <div class="text-secondary font-monospace" style="font-size: 0.7rem;">${UI.formatCurrency(h.capital_objetivo, 'EUR')}</div>
                    </div>
                    <div class="text-end">
                        <span class="badge ${badgeClass} font-monospace mb-1" style="font-size: 0.65rem;">${h.superado ? 'CONSEGUIDO' : h.fecha_tir}</span>
                        <div class="text-secondary" style="font-size: 0.65rem;">Cons: ${h.superado ? 'Superado' : h.fecha_cons}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Renderizar Gráfico
    renderizarGraficoFire(data.chart);
}

function renderizarGraficoFire(chartData) {
    if (!chartData || !chartData.labels) return;
    const ctx = document.getElementById('fireChart');
    if (!ctx) return;

    if (window.fireChartInstance) {
        window.fireChartInstance.destroy();
    }

    window.fireChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [
                {
                    label: 'Meta FIRE',
                    data: chartData.target,
                    borderColor: '#f59e0b',
                    borderWidth: 2,
                    borderDash: [6, 6],
                    pointRadius: 0,
                    fill: false
                },
                {
                    label: 'Tu TIR Real',
                    data: chartData.tir_real,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    borderWidth: 2.5,
                    pointRadius: 1,
                    fill: true,
                    tension: 0.25
                },
                {
                    label: 'Conservador (4% real)',
                    data: chartData.conservador,
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.05)',
                    borderWidth: 2,
                    pointRadius: 1,
                    fill: false,
                    tension: 0.25
                },
                {
                    label: 'Solo Ahorro (0% real)',
                    data: chartData.ahorro,
                    borderColor: '#94a3b8',
                    borderWidth: 1.5,
                    borderDash: [3, 3],
                    pointRadius: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#94a3b8',
                        boxWidth: 12,
                        font: { size: 11 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${UI.formatCurrency(context.parsed.y, 'EUR')}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#64748b', font: { size: 10 } },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                },
                y: {
                    ticks: {
                        color: '#64748b',
                        font: { size: 10 },
                        callback: function(val) {
                            if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M €';
                            if (val >= 1000) return (val / 1000).toFixed(0) + 'k €';
                            return val + ' €';
                        }
                    },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                }
            }
        }
    });
}

window.simularFireDebounced = function() {
    clearTimeout(debounceFireTimer);
    debounceFireTimer = setTimeout(() => {
        const gastos = document.getElementById('fire-input-gastos')?.value;
        const swr = document.getElementById('fire-input-swr')?.value;
        const aport = document.getElementById('fire-input-aportacion')?.value;
        const tasaCons = document.getElementById('fire-input-tasa-cons')?.value;

        const params = new URLSearchParams();
        if (gastos) params.append('gastos', gastos);
        if (swr) params.append('swr', swr);
        if (aport) params.append('aportacion', aport);
        if (tasaCons) params.append('tasa_cons', tasaCons);

        cargarFire(params.toString());
    }, 250);
};

window.usarAportacionHistoricaFire = function() {
    if (lastFireData && lastFireData.config_guardada) {
        const hist = lastFireData.config_guardada.aportacion_calculada || 1000;
        const input = document.getElementById('fire-input-aportacion');
        if (input) {
            input.value = hist;
            window.simularFireDebounced();
        }
    }
};

window.guardarConfigFire = async function() {
    const gastos = parseFloat(document.getElementById('fire-input-gastos')?.value || 24000);
    const swr = parseFloat(document.getElementById('fire-input-swr')?.value || 4.0);
    const aport = parseFloat(document.getElementById('fire-input-aportacion')?.value || 0);
    const tasaCons = parseFloat(document.getElementById('fire-input-tasa-cons')?.value || 4.0);

    try {
        const mironParam = window.modoMiron ? '?miron=1' : '';
        await API.post(`/api/fire/config${mironParam}`, {
            gastos_anuales: gastos,
            swr_pct: swr,
            aportacion_mensual: aport,
            tasa_conservadora_pct: tasaCons
        });

        const toast = document.getElementById('fire-save-toast');
        if (toast) {
            toast.classList.remove('d-none');
            setTimeout(() => toast.classList.add('d-none'), 3000);
        }
        UI.showToast("Objetivo de Independencia Financiera guardado correctamente", "success");
    } catch (err) {
        UI.showToast("Error guardando objetivo FIRE: " + err.message, "error");
    }
};
