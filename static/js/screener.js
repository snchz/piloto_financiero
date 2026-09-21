/**
 * Equity Screener (Williams %R & Net Target Gain)
 * Escaneo en segundo plano, cálculo en vivo de orden limitada y gestión de universo
 */

let screenerRawSignals = [];
let screenerPollTimer = null;
let screenerMarketFilter = 'ALL';

async function cargarScreener() {
    const umbral = parseFloat(document.getElementById('screener-slider-umbral')?.value || -80);
    const target = parseFloat(document.getElementById('screener-input-target')?.value || 5.0);
    const cin = parseFloat(document.getElementById('screener-input-cin')?.value || 0.12);
    const cout = parseFloat(document.getElementById('screener-input-cout')?.value || 0.12);

    try {
        const url = `/api/screener?umbral_wr=${encodeURIComponent(umbral)}&comision_in=${encodeURIComponent(cin)}&comision_out=${encodeURIComponent(cout)}&target_gain=${encodeURIComponent(target)}&market=${encodeURIComponent(screenerMarketFilter)}`;
        const data = await API.fetch(url);

        screenerRawSignals = data.signals || [];

        // 1. KPIs
        const totalEl = document.getElementById('screener-kpi-total');
        if (totalEl) totalEl.textContent = data.total_scanned || '--';

        const signalsEl = document.getElementById('screener-kpi-signals');
        if (signalsEl) signalsEl.textContent = data.total_signals || 0;

        const signalsSub = document.getElementById('screener-kpi-signals-sub');
        if (signalsSub) signalsSub.textContent = `W%R ≤ ${umbral.toFixed(1)}`;

        const avgEl = document.getElementById('screener-kpi-avg-wr');
        if (avgEl) avgEl.textContent = data.avg_williams_r !== null ? data.avg_williams_r.toFixed(2) : '--';

        const lastScanEl = document.getElementById('screener-kpi-last-scan');
        if (lastScanEl) lastScanEl.textContent = data.last_scan_time || '--:--:--';

        // 2. Renderizar tabla
        renderizarTablaScreener();

        // 3. Si el servidor sigue escaneando, reanudar polling
        if (data.status && data.status.is_scanning) {
            mostrarProgresoEscaneo(data.status);
            iniciarPollingEstado();
        }

    } catch (err) {
        console.error("Error cargando screener:", err);
        UI.showToast("Error cargando datos del radar: " + (err.message || err), "error");
    }
}
window.cargarScreener = cargarScreener;

function actualizarFiltrosScreener() {
    const slider = document.getElementById('screener-slider-umbral');
    const lblUmbral = document.getElementById('lbl-val-umbral');
    if (slider && lblUmbral) {
        lblUmbral.textContent = `≤ ${slider.value}`;
    }

    const umbral = parseFloat(slider?.value || -80);
    const target = parseFloat(document.getElementById('screener-input-target')?.value || 5.0);
    const cin = parseFloat(document.getElementById('screener-input-cin')?.value || 0.12);
    const cout = parseFloat(document.getElementById('screener-input-cout')?.value || 0.12);

    // Recálculo dinámico en caliente en el cliente
    renderizarTablaScreener(umbral, target, cin, cout);
}
window.actualizarFiltrosScreener = actualizarFiltrosScreener;

function setMercadoFiltro(mkt, btn) {
    screenerMarketFilter = mkt;
    document.querySelectorAll('#nav-screener .time-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    renderizarTablaScreener();
}
window.setMercadoFiltro = setMercadoFiltro;

function calcularPrecioTargetLocal(close, cinPct, coutPct, targetGainPct) {
    const cIn = cinPct / 100.0;
    const cOut = coutPct / 100.0;
    const rTarget = targetGainPct / 100.0;

    const factor = ((1.0 + cIn) * (1.0 + rTarget)) / (1.0 - cOut);
    const targetPrice = close * factor;
    const grossPct = (factor - 1.0) * 100.0;
    return { targetPrice, grossPct };
}

function renderizarTablaScreener(customUmbral = null, customTarget = null, customCin = null, customCout = null) {
    const umbral = customUmbral !== null ? customUmbral : parseFloat(document.getElementById('screener-slider-umbral')?.value || -80);
    const targetGain = customTarget !== null ? customTarget : parseFloat(document.getElementById('screener-input-target')?.value || 5.0);
    const cin = customCin !== null ? customCin : parseFloat(document.getElementById('screener-input-cin')?.value || 0.12);
    const cout = customCout !== null ? customCout : parseFloat(document.getElementById('screener-input-cout')?.value || 0.12);

    const tbody = document.getElementById('screener-table-body');
    const countBadge = document.getElementById('screener-table-count');
    if (!tbody) return;

    // Filtrar por umbral y por mercado
    const filtradas = screenerRawSignals.filter(s => {
        if (s.williams_r > umbral) return false;
        if (screenerMarketFilter === 'SP500' && !s.market.includes('S&P')) return false;
        if (screenerMarketFilter === 'MC' && !s.market.includes('.MC')) return false;
        return true;
    });

    if (countBadge) countBadge.textContent = `${filtradas.length} señal${filtradas.length === 1 ? '' : 'es'}`;

    if (filtradas.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-5 text-secondary">
                    <div class="mb-2 fs-4">👌</div>
                    <div>No hay activos bajo el umbral de sobreventa (${umbral}) con los filtros actuales.</div>
                    <div class="small text-secondary mt-1">Prueba a elevar el umbral (ej. -75) o ejecuta un nuevo escaneo.</div>
                </td>
            </tr>
        `;
        return;
    }

    const html = filtradas.map(s => {
        const isExtremo = s.williams_r <= -90.0;
        const badgeColor = isExtremo ? 'bg-danger text-white' : 'bg-warning bg-opacity-25 text-warning border border-warning border-opacity-40';
        const badgeText = isExtremo ? 'Sobreventa Extrema' : 'Sobreventa';

        // Porcentaje visual del oscilador (-100 a 0)
        // Normalizamos: -100 es 0% (pegado al suelo), 0 es 100%
        const gaugePct = Math.min(Math.max(100 + s.williams_r, 0), 100);

        const curr = s.currency || (s.ticker.endsWith('.MC') ? 'EUR' : 'USD');
        const isSpanish = s.ticker.endsWith('.MC');
        const mktBadge = isSpanish 
            ? '<span class="badge bg-secondary bg-opacity-25 text-warning font-monospace" style="font-size:0.68rem;">🇪🇸 Continuo</span>'
            : '<span class="badge bg-primary bg-opacity-20 text-primary font-monospace" style="font-size:0.68rem;">🇺🇸 S&P 500</span>';

        const { targetPrice, grossPct } = calcularPrecioTargetLocal(s.close_price, cin, cout, targetGain);

        return `
            <tr>
                <td class="ps-4">
                    <div class="fw-bold text-white fs-6 d-flex align-items-center gap-2">
                        <span>${s.ticker}</span>
                        ${mktBadge}
                    </div>
                    <div class="text-secondary small text-truncate" style="max-width: 250px;" title="${s.name}">${s.name}</div>
                </td>
                <td class="text-center">
                    <span class="text-secondary font-monospace" style="font-size: 0.72rem;">${s.date}</span>
                </td>
                <td class="text-end font-monospace fs-6 fw-bold text-white">
                    ${UI.formatCurrency(s.close_price, curr)}
                </td>
                <td class="text-center px-3">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span class="badge ${badgeColor} font-monospace" style="font-size: 0.7rem;">${s.williams_r.toFixed(2)}</span>
                        <span class="text-secondary small font-monospace" style="font-size: 0.68rem;">${badgeText}</span>
                    </div>
                    <div class="progress" style="height: 5px; background: rgba(255,255,255,0.06); border-radius: 4px;">
                        <div class="progress-bar ${isExtremo ? 'bg-danger' : 'bg-warning'}" style="width: ${gaugePct}%; border-radius: 4px;"></div>
                    </div>
                </td>
                <td class="text-center font-monospace text-secondary small">
                    <span class="text-danger" title="Mínimo 14 sesiones">${UI.formatCurrency(s.low_14, curr)}</span>
                    <span class="opacity-50"> - </span>
                    <span class="text-info" title="Máximo 14 sesiones">${UI.formatCurrency(s.high_14, curr)}</span>
                </td>
                <td class="text-end pe-4">
                    <div class="d-inline-flex flex-column align-items-end p-2 rounded-2" style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25);">
                        <div class="font-monospace fs-6 fw-bold text-success">
                            🎯 ${UI.formatCurrency(targetPrice, curr)}
                        </div>
                        <div class="d-flex align-items-center gap-1 font-monospace" style="font-size: 0.68rem;">
                            <span class="text-success fw-bold">+${targetGain.toFixed(2)}% Neto</span>
                            <span class="text-secondary opacity-75">(+${grossPct.toFixed(2)}% bruto)</span>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    tbody.innerHTML = html;
}

// --- Gestión de Escaneo Asíncrono ---
async function iniciarEscaneoScreener() {
    const btn = document.getElementById('btn-scan-screener');
    const spinner = document.getElementById('spinner-scan');
    const label = document.getElementById('label-scan');

    if (btn) btn.disabled = true;
    if (spinner) spinner.classList.remove('d-none');
    if (label) label.textContent = 'Iniciando...';

    try {
        const res = await API.post('/api/screener/scan');
        if (res.ok) {
            UI.showToast("Escaneo en segundo plano iniciado para ~550 activos", "info");
            mostrarProgresoEscaneo(res.status);
            iniciarPollingEstado();
        } else {
            UI.showToast(res.error || "No se pudo iniciar el escaneo", "error");
            restaurarBotonEscaneo();
        }
    } catch (err) {
        UI.showToast("Error iniciando escaneo: " + (err.message || err), "error");
        restaurarBotonEscaneo();
    }
}
window.iniciarEscaneoScreener = iniciarEscaneoScreener;

function mostrarProgresoEscaneo(status) {
    const box = document.getElementById('screener-scan-progress-box');
    const bar = document.getElementById('screener-scan-bar');
    const pct = document.getElementById('screener-scan-pct');
    const msg = document.getElementById('screener-scan-message');

    if (box) box.classList.remove('d-none');
    if (bar) bar.style.width = `${status.progress || 0}%`;
    if (pct) pct.textContent = `${status.progress || 0}%`;
    if (msg) msg.textContent = status.message || 'Analizando mercado...';
}

function iniciarPollingEstado() {
    if (screenerPollTimer) clearInterval(screenerPollTimer);

    screenerPollTimer = setInterval(async () => {
        try {
            const status = await API.fetch('/api/screener/status');
            mostrarProgresoEscaneo(status);

            if (!status.is_scanning) {
                clearInterval(screenerPollTimer);
                screenerPollTimer = null;
                restaurarBotonEscaneo();
                
                UI.showToast("Escaneo del Screener finalizado con éxito", "success");
                
                // Ocultar caja de progreso tras 2 segundos
                setTimeout(() => {
                    const box = document.getElementById('screener-scan-progress-box');
                    if (box) box.classList.add('d-none');
                }, 2000);

                await cargarScreener();
            }
        } catch (e) {
            console.warn("Error consultando estado screener:", e);
        }
    }, 1500);
}

function restaurarBotonEscaneo() {
    const btn = document.getElementById('btn-scan-screener');
    const spinner = document.getElementById('spinner-scan');
    const label = document.getElementById('label-scan');

    if (btn) btn.disabled = false;
    if (spinner) spinner.classList.add('d-none');
    if (label) label.textContent = '🔄 Escanear Mercado';
}

// --- Modal de Configuración de Tickers Españoles ---
async function abrirModalTickersEspana() {
    try {
        const res = await API.fetch('/api/screener/tickers');
        const tickers = res.spanish_tickers || [];
        const textarea = document.getElementById('screener-tickers-textarea');
        if (textarea) {
            textarea.value = tickers.join(', ');
        }
        document.getElementById('screenerTickersModal').showModal();
    } catch (err) {
        UI.showToast("Error cargando tickers españoles: " + (err.message || err), "error");
    }
}
window.abrirModalTickersEspana = abrirModalTickersEspana;

async function guardarTickersEspana(e) {
    if (e) e.preventDefault();
    const textarea = document.getElementById('screener-tickers-textarea');
    if (!textarea) return;

    const raw = textarea.value;
    const parts = raw.split(/[\n,;]+/).map(p => p.trim().toUpperCase()).filter(p => p.length > 0);

    try {
        await API.post('/api/screener/tickers', { spanish_tickers: parts });
        UI.showToast("Lista de tickers españoles guardada", "success");
        document.getElementById('screenerTickersModal').close();
    } catch (err) {
        UI.showToast("Error guardando tickers: " + (err.message || err), "error");
    }
}
window.guardarTickersEspana = guardarTickersEspana;

function restaurarTickersEspanaDefault() {
    const textarea = document.getElementById('screener-tickers-textarea');
    if (textarea) {
        textarea.value = "SAN.MC, BBVA.MC, ITX.MC, IBE.MC, TEF.MC, REP.MC, CABK.MC, AMS.MC, FER.MC, GRF.MC, IAG.MC, ACS.MC, ENG.MC, ELE.MC, RED.MC, MAP.MC, COL.MC, MRL.MC, SAB.MC, BKT.MC, ANE.MC, ACX.MC, FDR.MC, ROVI.MC, SLR.MC, MEL.MC, IDR.MC, LOG.MC, UNI.MC, SCYR.MC, VIS.MC, CIE.MC, PHM.MC, GCT.MC, ALM.MC, CAF.MC, VID.MC, TLGO.MC, TRE.MC, DOM.MC, TUB.MC, TRG.MC, APPS.MC, GSJ.MC, AIR.MC, EDR.MC, GEST.MC, EBRO.MC, ENR.MC, NTX.MC";
    }
}
window.restaurarTickersEspanaDefault = restaurarTickersEspanaDefault;

// Auto-carga al abrir la pestaña Screener
document.addEventListener('DOMContentLoaded', () => {
    const screenerTabBtn = document.getElementById('screener-tab');
    if (screenerTabBtn) {
        screenerTabBtn.addEventListener('shown.bs.tab', () => {
            cargarScreener();
        });
    }
});
