/**
 * Equity Screener (Williams %R & Net Target Gain)
 * Escaneo en segundo plano, cálculo en vivo de orden limitada y filtros Value Investing
 */

let screenerRawSignals = [];
let screenerPollTimer = null;
let screenerMarketFilter = 'ALL';

// Estado de Filtros Value Investing
let screenerFilterGem = false;
let screenerFilterGraham = false;
let screenerFilterBuffett = false;
let screenerFilterDeuda = false;

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

        // 2. Contadores de Filtros Value
        actualizarContadoresValue(data);

        // 3. Renderizar tabla
        renderizarTablaScreener();

        // 4. Si el servidor sigue escaneando, reanudar polling
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

function actualizarContadoresValue(data) {
    const totalGems = data.total_gems ?? screenerRawSignals.filter(s => s.is_value_gem).length;
    const totalGraham = data.total_graham ?? screenerRawSignals.filter(s => s.passes_graham).length;
    const totalBuffett = data.total_buffett ?? screenerRawSignals.filter(s => s.passes_buffett).length;
    const totalDeuda = data.total_deuda ?? screenerRawSignals.filter(s => s.passes_deuda).length;

    const bGem = document.getElementById('badge-count-gem');
    if (bGem) bGem.textContent = totalGems;

    const bGraham = document.getElementById('badge-count-graham');
    if (bGraham) bGraham.textContent = totalGraham;

    const bBuffett = document.getElementById('badge-count-buffett');
    if (bBuffett) bBuffett.textContent = totalBuffett;

    const bDeuda = document.getElementById('badge-count-deuda');
    if (bDeuda) bDeuda.textContent = totalDeuda;

    const gemsBadge = document.getElementById('screener-table-gems-badge');
    if (gemsBadge) {
        if (totalGems > 0) {
            gemsBadge.textContent = `💎 ${totalGems} Joya${totalGems === 1 ? '' : 's'} Value`;
            gemsBadge.classList.remove('d-none');
        } else {
            gemsBadge.classList.add('d-none');
        }
    }
}

function toggleFiltroValue(filtro) {
    if (filtro === 'gem') {
        screenerFilterGem = !screenerFilterGem;
        if (screenerFilterGem) {
            screenerFilterGraham = false;
            screenerFilterBuffett = false;
            screenerFilterDeuda = false;
        }
    } else if (filtro === 'graham') {
        screenerFilterGraham = !screenerFilterGraham;
        screenerFilterGem = false;
    } else if (filtro === 'buffett') {
        screenerFilterBuffett = !screenerFilterBuffett;
        screenerFilterGem = false;
    } else if (filtro === 'deuda') {
        screenerFilterDeuda = !screenerFilterDeuda;
        screenerFilterGem = false;
    }
    actualizarEstilosBotonesFiltro();
    renderizarTablaScreener();
}
window.toggleFiltroValue = toggleFiltroValue;

function limpiarFiltrosValue() {
    screenerFilterGem = false;
    screenerFilterGraham = false;
    screenerFilterBuffett = false;
    screenerFilterDeuda = false;
    actualizarEstilosBotonesFiltro();
    renderizarTablaScreener();
}
window.limpiarFiltrosValue = limpiarFiltrosValue;

function actualizarEstilosBotonesFiltro() {
    const btnGem = document.getElementById('btn-filtro-gem');
    const btnGraham = document.getElementById('btn-filtro-graham');
    const btnBuffett = document.getElementById('btn-filtro-buffett');
    const btnDeuda = document.getElementById('btn-filtro-deuda');

    if (btnGem) btnGem.classList.toggle('active-gem', screenerFilterGem);
    if (btnGraham) btnGraham.classList.toggle('active', screenerFilterGraham);
    if (btnBuffett) btnBuffett.classList.toggle('active', screenerFilterBuffett);
    if (btnDeuda) btnDeuda.classList.toggle('active', screenerFilterDeuda);
}

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

    // Filtrar por umbral, mercado y filtros Value Investing
    const filtradas = screenerRawSignals.filter(s => {
        if (s.williams_r > umbral) return false;
        if (screenerMarketFilter === 'SP500' && !s.market.includes('S&P')) return false;
        if (screenerMarketFilter === 'MC' && !s.market.includes('.MC')) return false;

        if (screenerFilterGem && !s.is_value_gem) return false;
        if (screenerFilterGraham && !s.passes_graham) return false;
        if (screenerFilterBuffett && !s.passes_buffett) return false;
        if (screenerFilterDeuda && !s.passes_deuda) return false;

        return true;
    });

    if (countBadge) countBadge.textContent = `${filtradas.length} señal${filtradas.length === 1 ? '' : 'es'}`;

    if (filtradas.length === 0) {
        let msgFiltros = [];
        if (screenerFilterGem) msgFiltros.push("💎 Joyas Value");
        if (screenerFilterGraham) msgFiltros.push("🏛️ Graham");
        if (screenerFilterBuffett) msgFiltros.push("👔 Buffett");
        if (screenerFilterDeuda) msgFiltros.push("🛡️ Deuda");
        const extraMsg = msgFiltros.length > 0 ? ` con filtros activos [${msgFiltros.join(', ')}]` : '';

        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-5 text-secondary">
                    <div class="mb-2 fs-4">👌</div>
                    <div>No hay activos bajo el umbral de sobreventa (${umbral})${extraMsg}.</div>
                    <div class="small text-secondary mt-1">
                        ${msgFiltros.length > 0 ? '<a href="javascript:void(0)" class="text-primary text-decoration-none" onclick="limpiarFiltrosValue()">Restablecer filtros Value</a> o ' : ''}eleva el umbral en el deslizador.
                    </div>
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
        const gaugePct = Math.min(Math.max(100 + s.williams_r, 0), 100);

        const curr = s.currency || (s.ticker.endsWith('.MC') ? 'EUR' : 'USD');
        const isSpanish = s.ticker.endsWith('.MC');
        const mktBadge = isSpanish 
            ? '<span class="badge bg-secondary bg-opacity-25 text-warning font-monospace" style="font-size:0.68rem;">🇪🇸 Continuo</span>'
            : '<span class="badge bg-primary bg-opacity-20 text-primary font-monospace" style="font-size:0.68rem;">🇺🇸 S&P 500</span>';

        const { targetPrice, grossPct } = calcularPrecioTargetLocal(s.close_price, cin, cout, targetGain);

        // --- Renderizar Badges Value Investing ---
        const gemBadgeHtml = s.is_value_gem 
            ? '<span class="badge badge-gem font-monospace py-1 px-2" style="font-size:0.68rem;" title="💎 Joya Value: Supera los 3 filtros simultáneamente (Graham + Buffett + Deuda)">💎 Joya Value</span>'
            : '';

        // Graham: PER < 15 y P/B < 1.5
        const peStr = s.trailing_pe !== null && s.trailing_pe !== undefined ? s.trailing_pe.toFixed(1) : 'N/D';
        const pbStr = s.price_to_book !== null && s.price_to_book !== undefined ? s.price_to_book.toFixed(2) : 'N/D';
        const grahamBadge = s.passes_graham
            ? `<span class="badge bg-success bg-opacity-20 text-success border border-success border-opacity-40 font-monospace" style="font-size:0.68rem;" title="Graham Superado: PER ${peStr} (<15) · P/B ${pbStr} (<1.5)">🏛️ PER ${peStr} · P/B ${pbStr}</span>`
            : `<span class="badge bg-dark border border-secondary border-opacity-25 text-secondary font-monospace opacity-75" style="font-size:0.68rem;" title="Graham: PER ${peStr} · P/B ${pbStr}">🏛️ PER ${peStr}</span>`;

        // Buffett: ROE > 10% (0.10) y EPS > 0
        const roeStr = s.return_on_equity !== null && s.return_on_equity !== undefined ? `${(s.return_on_equity * 100).toFixed(1)}%` : 'N/D';
        const epsStr = s.trailing_eps !== null && s.trailing_eps !== undefined ? s.trailing_eps.toFixed(2) : 'N/D';
        const buffettBadge = s.passes_buffett
            ? `<span class="badge bg-success bg-opacity-20 text-success border border-success border-opacity-40 font-monospace" style="font-size:0.68rem;" title="Buffett Superado: ROE ${roeStr} (>10%) · BPA ${epsStr} (>0)">👔 ROE ${roeStr}</span>`
            : `<span class="badge bg-dark border border-secondary border-opacity-25 text-secondary font-monospace opacity-75" style="font-size:0.68rem;" title="Buffett: ROE ${roeStr} · BPA ${epsStr}">👔 ROE ${roeStr}</span>`;

        // Deuda: Debt/Equity < 100
        const deStr = s.debt_to_equity !== null && s.debt_to_equity !== undefined ? s.debt_to_equity.toFixed(1) : 'N/D';
        const deudaBadge = s.passes_deuda
            ? `<span class="badge bg-success bg-opacity-20 text-success border border-success border-opacity-40 font-monospace" style="font-size:0.68rem;" title="Deuda Saludable: D/E ${deStr} (<100)">🛡️ D/E ${deStr}</span>`
            : `<span class="badge ${s.debt_to_equity !== null ? 'bg-danger bg-opacity-15 text-danger border border-danger border-opacity-30' : 'bg-dark border border-secondary border-opacity-25 text-secondary'} font-monospace opacity-75" style="font-size:0.68rem;" title="D/E: ${deStr} ${s.debt_to_equity === null ? '(Bancos o no reportado)' : '(Excede 100)'}">🛡️ D/E ${deStr}</span>`;

        return `
            <tr>
                <td class="ps-4">
                    <div class="fw-bold text-white fs-6 d-flex align-items-center gap-2">
                        <span>${s.ticker}</span>
                        ${mktBadge}
                        ${gemBadgeHtml}
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
                <td class="text-center px-2">
                    <div class="d-flex flex-wrap gap-1 justify-content-center align-items-center">
                        ${grahamBadge}
                        ${buffettBadge}
                        ${deudaBadge}
                    </div>
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
                    <div class="mt-1">
                        <button type="button" 
                                class="btn btn-sm btn-outline-success py-1 px-2 d-inline-flex align-items-center gap-1 font-monospace" 
                                style="font-size: 0.7rem; border-color: rgba(16, 185, 129, 0.35);"
                                onclick="crearAlertaOrdenLimitada('${s.ticker}', ${targetPrice}, ${targetGain}, this)" 
                                title="Añadir alerta a Monitores con precio objetivo ${targetPrice.toFixed(2)} ${curr}">
                            <span>🔔 Añadir Alerta</span>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    tbody.innerHTML = html;
}

// --- Crear Alerta desde Orden Limitada del Screener ---
async function crearAlertaOrdenLimitada(ticker, targetPrice, targetGain = 5.0, btn = null) {
    if (!ticker || !targetPrice || targetPrice <= 0) {
        UI.showToast("Precio objetivo no válido", "error");
        return;
    }

    const originalHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }

    try {
        const payload = {
            ticker: ticker,
            target: parseFloat(targetPrice.toFixed(2)),
            target_pct: parseFloat(targetGain.toFixed(1)) || 0
        };

        const res = await API.post('/api/add', payload);
        if (res && res.ok) {
            UI.showToast(`🔔 Alerta guardada para ${ticker} a ${targetPrice.toFixed(2)}`, "success");
            if (btn) {
                btn.className = "btn btn-sm btn-success py-1 px-2 d-inline-flex align-items-center gap-1 font-monospace text-white";
                btn.innerHTML = '<span>✓ Alerta Creada</span>';
                btn.disabled = true;
            }
            if (typeof window.cargarOperaciones === 'function') {
                window.cargarOperaciones();
            }
        } else {
            UI.showToast(res.error || "No se pudo crear la alerta", "error");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        }
    } catch (err) {
        console.error("Error creando alerta:", err);
        UI.showToast("Error creando alerta: " + (err.message || err), "error");
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }
}
window.crearAlertaOrdenLimitada = crearAlertaOrdenLimitada;


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

// --- Sentimiento de Mercado & Posicionamiento Institucional (Metodología Cava) ---
let _sentimentLoading = false;

async function cargarSentimientoMercado(forzar = false) {
    if (_sentimentLoading) return;
    _sentimentLoading = true;

    const spinner = document.getElementById('sentiment-spinner');
    const label = document.getElementById('sentiment-refresh-label');
    const statusBadge = document.getElementById('sentiment-status-badge');

    if (spinner) spinner.classList.remove('d-none');
    if (label) label.textContent = 'Actualizando...';

    try {
        const url = `/api/sentimiento${forzar ? '?refresh=1' : ''}`;
        const data = await API.fetch(url);

        // 1. VIX
        const vix = data.vix || {};
        const vixPriceEl = document.getElementById('sentiment-vix-price');
        const vixChangeEl = document.getElementById('sentiment-vix-change');
        const vixBadgeEl = document.getElementById('sentiment-vix-badge');
        if (vixPriceEl) vixPriceEl.textContent = vix.current_price ? vix.current_price.toFixed(2) : '--';
        if (vixChangeEl) {
            const chg = vix.change || 0;
            const pct = vix.pct_change || 0;
            const sign = chg >= 0 ? '+' : '';
            vixChangeEl.textContent = `${sign}${chg.toFixed(2)} (${sign}${pct.toFixed(2)}%)`;
            vixChangeEl.className = `small font-monospace ${chg > 0 ? 'text-danger' : 'text-success'}`;
        }
        if (vixBadgeEl) {
            vixBadgeEl.textContent = vix.regimen || '--';
            vixBadgeEl.className = `badge bg-${vix.color || 'secondary'} font-monospace`;
        }

        // 2. CNN Fear & Greed
        const fg = data.fear_and_greed || {};
        const fgScoreEl = document.getElementById('sentiment-fg-score');
        const fgBadgeEl = document.getElementById('sentiment-fg-badge');
        const fgBarEl = document.getElementById('sentiment-fg-bar');
        const fgPrevEl = document.getElementById('sentiment-fg-prev');

        if (fgScoreEl) fgScoreEl.textContent = fg.score !== undefined ? fg.score.toFixed(1) : '--';
        if (fgBadgeEl) {
            fgBadgeEl.textContent = fg.rating_es || fg.rating || '--';
            fgBadgeEl.className = `badge bg-${fg.color || 'secondary'} font-monospace`;
        }
        if (fgBarEl) {
            const score = fg.score || 50;
            fgBarEl.style.width = `${Math.min(Math.max(score, 5), 100)}%`;
            fgBarEl.className = `progress-bar bg-${fg.color || 'info'}`;
        }
        if (fgPrevEl) {
            fgPrevEl.textContent = `Prev: ${fg.previous_close !== undefined ? fg.previous_close.toFixed(0) : '--'}`;
        }

        // 3. Ratio Put/Call
        const pc = data.put_call || {};
        const pcrVolEl = document.getElementById('sentiment-pcr-vol');
        const pcr10dEl = document.getElementById('sentiment-pcr-10d');
        const pcrOiEl = document.getElementById('sentiment-pcr-oi');
        const pcrBadgeEl = document.getElementById('sentiment-pcr-badge');

        const pcrVol = pc.pcr_volume || 0;
        if (pcrVolEl) pcrVolEl.textContent = pcrVol.toFixed(2);
        if (pcr10dEl) {
            pcr10dEl.textContent = pc.pcr_10d_ma ? `MA10: ${pc.pcr_10d_ma.toFixed(2)}` : 'MA10: --';
        }
        if (pcrOiEl) {
            pcrOiEl.textContent = pc.pcr_oi ? `OI: ${pc.pcr_oi.toFixed(2)}` : 'OI: --';
        }
        if (pcrBadgeEl) {
            let pcrLabel = 'Neutral';
            let pcrColor = 'secondary';
            const valToCheck = pc.pcr_10d_ma || pcrVol;
            if (valToCheck >= 1.05) {
                pcrLabel = 'Pánico (>1.05)';
                pcrColor = 'danger';
            } else if (valToCheck <= 0.65) {
                pcrLabel = 'Complacencia (<0.65)';
                pcrColor = 'warning';
            }
            pcrBadgeEl.textContent = pcrLabel;
            pcrBadgeEl.className = `badge bg-${pcrColor} font-monospace`;
        }

        // 4. Dealers Gamma & Muros
        const gex = data.gamma_exposure || {};
        const walls = data.walls || {};
        const spxPriceEl = document.getElementById('sentiment-spx-price');
        const zeroGammaEl = document.getElementById('sentiment-zero-gamma');
        const gammaBadgeEl = document.getElementById('sentiment-gamma-badge');
        const putWallEl = document.getElementById('sentiment-put-wall');
        const callWallEl = document.getElementById('sentiment-call-wall');

        if (spxPriceEl) {
            const spx = data.spx_price || (data.spy_price ? data.spy_price * 10 : 0);
            spxPriceEl.textContent = `SPX: ${spx ? Math.round(spx) : '--'}`;
        }
        if (zeroGammaEl) {
            zeroGammaEl.textContent = `γ=0: ${gex.zero_gamma_spx ? Math.round(gex.zero_gamma_spx) : '--'}`;
        }
        if (gammaBadgeEl) {
            const isPos = gex.is_positive_gamma;
            gammaBadgeEl.textContent = isPos ? 'Gamma +' : 'Gamma -';
            gammaBadgeEl.className = `badge ${isPos ? 'bg-primary' : 'bg-warning text-dark'} font-monospace`;
            gammaBadgeEl.title = gex.regimen_desc || '';
        }
        if (putWallEl) {
            putWallEl.textContent = `Put Wall: ${walls.put_wall_spx ? Math.round(walls.put_wall_spx) : '--'}`;
        }
        if (callWallEl) {
            callWallEl.textContent = `Call Wall: ${walls.call_wall_spx ? Math.round(walls.call_wall_spx) : '--'}`;
        }

        // 5. Veredicto Hero Directo para Dummies
        const diag = data.diagnostico || {};
        const heroBadge = document.getElementById('sentiment-hero-badge');
        if (heroBadge) {
            heroBadge.textContent = diag.hay_panico || diag.estado || 'Neutral';
            heroBadge.className = `badge ${diag.hay_panico_badge || diag.badge_class || 'bg-secondary'} font-monospace`;
        }

        const simpleTitle = document.getElementById('sentiment-simple-title');
        if (simpleTitle) {
            simpleTitle.textContent = diag.titular_simple || diag.estado || 'MERCADO EQUILIBRADO';
        }

        const simpleMsg = document.getElementById('sentiment-simple-msg');
        if (simpleMsg) {
            simpleMsg.textContent = diag.mensaje_simple || diag.resumen || '';
        }

        const simpleAdvice = document.getElementById('sentiment-simple-advice');
        if (simpleAdvice) {
            simpleAdvice.textContent = diag.consejo_simple || 'Operar con normalidad.';
        }

        const simplePill = document.getElementById('sentiment-simple-pill');
        if (simplePill) {
            simplePill.className = `badge ${diag.hay_panico_badge || 'bg-success'} font-monospace`;
        }

        // Divergencia explicada (si unos dicen miedo y otros calma)
        const divBox = document.getElementById('sentiment-divergencia-box');
        if (divBox) {
            if (diag.explicacion_divergencia && diag.explicacion_divergencia.includes('💡')) {
                divBox.textContent = diag.explicacion_divergencia;
                divBox.classList.remove('d-none');
            } else {
                divBox.classList.add('d-none');
            }
        }

        // Termómetro Global 0-100
        const scoreGlobalEl = document.getElementById('sentiment-score-global');
        const globalBar = document.getElementById('sentiment-global-bar');
        const heroBox = document.getElementById('sentiment-veredicto-hero');

        const score = diag.score_global !== undefined ? diag.score_global : 50;
        if (scoreGlobalEl) scoreGlobalEl.textContent = score.toFixed(0);

        if (globalBar) {
            globalBar.style.width = `${Math.min(Math.max(score, 5), 100)}%`;
            if (score <= 30) {
                globalBar.className = 'progress-bar bg-danger';
            } else if (score <= 45) {
                globalBar.className = 'progress-bar bg-warning';
            } else if (score <= 75) {
                globalBar.className = 'progress-bar bg-success';
            } else {
                globalBar.className = 'progress-bar bg-info';
            }
        }

        if (heroBox) {
            if (score <= 30) {
                heroBox.style.background = 'rgba(244, 63, 94, 0.1)';
                heroBox.style.borderColor = 'rgba(244, 63, 94, 0.3)';
                heroBox.style.borderLeftColor = '#f43f5e';
            } else if (score <= 45) {
                heroBox.style.background = 'rgba(245, 158, 11, 0.1)';
                heroBox.style.borderColor = 'rgba(245, 158, 11, 0.3)';
                heroBox.style.borderLeftColor = '#f59e0b';
            } else if (score <= 75) {
                heroBox.style.background = 'rgba(16, 185, 129, 0.1)';
                heroBox.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                heroBox.style.borderLeftColor = '#10b981';
            } else {
                heroBox.style.background = 'rgba(99, 102, 241, 0.1)';
                heroBox.style.borderColor = 'rgba(99, 102, 241, 0.3)';
                heroBox.style.borderLeftColor = '#6366f1';
            }
        }

        // 6. Información de Caché
        const cacheInfo = document.getElementById('sentiment-cache-info');
        if (cacheInfo) {
            if (data.from_cache) {
                const mins = Math.floor((data.cache_age_seconds || 0) / 60);
                cacheInfo.textContent = `Caché: hace ${mins}m`;
            } else {
                cacheInfo.textContent = 'En vivo';
            }
        }

    } catch (err) {
        console.error("Error cargando sentimiento de mercado:", err);
        if (statusBadge) {
            statusBadge.textContent = 'Error';
            statusBadge.className = 'badge bg-danger font-monospace';
        }
    } finally {
        _sentimentLoading = false;
        if (spinner) spinner.classList.add('d-none');
        if (label) label.textContent = '🔄 Refrescar';
    }
}
window.cargarSentimientoMercado = cargarSentimientoMercado;

// Auto-carga al abrir la pestaña Screener
document.addEventListener('DOMContentLoaded', () => {
    const screenerTabBtn = document.getElementById('screener-tab');
    if (screenerTabBtn) {
        screenerTabBtn.addEventListener('shown.bs.tab', () => {
            cargarScreener();
            cargarSentimientoMercado();
        });
    }
});

