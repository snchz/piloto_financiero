# Reglas para Agentes IA en Piloto Financiero

Este archivo guía a cualquier agente de IA para trabajar en este repositorio con el **máximo ahorro de tokens**, sabiendo con exactitud dónde mirar sin exploraciones redundantes.

---

## ⚡ Protocolo de Ahorro de Tokens
1. **No leer archivos completos**: Consulta exclusivamente los rangos de líneas indicados abajo con slices (`StartLine`/`EndLine`, máximo 100 líneas) o `grep_search`.
2. **Entorno de ejecución de tests**: El host Linux no tiene instaladas las dependencias de ciencia de datos. Todo comando de prueba o script debe correrse montado en Docker:
   ```bash
   docker run --rm -v /opt/stacks/piloto_financiero:/app -v /home/leif/docker/configs/piloto_financiero:/app/data ghcr.io/snchz/piloto_financiero:latest python -c "..."
   ```
3. **Persistencia SQLite**: La base de datos de producción reside en `/home/leif/docker/configs/piloto_financiero/piloto.db`. Nunca escribir datos simulados o multiplicados en ella.

---

## 🗺️ Mapa Rápido de Código y Líneas

| Archivo | Rango de Líneas | Responsabilidad / Función |
| :--- | :--- | :--- |
| [`app.py`](file:///opt/stacks/piloto_financiero/app.py) | `L399-L616` | `calcular_datos_cartera(include_real_estate, multiplier)` — Filtro de inmuebles, modo mirón x3, agregación y métricas. |
| [`app.py`](file:///opt/stacks/piloto_financiero/app.py) | `L618-L788` | `GET /api/operaciones` — TIR global, histórico diario y benchmark VWCE. |
| [`app.py`](file:///opt/stacks/piloto_financiero/app.py) | `L791-L875` | `GET /api/rebalanceo`, `/tags`, `/map-asset` — Cash-flow rebalancing y categorías. |
| [`app.py`](file:///opt/stacks/piloto_financiero/app.py) | `L883-L985` | `GET /api/fire`, `POST /api/fire/config` — Independencia Financiera (FIRE): proyecciones y simulador. |
| [`app.py`](file:///opt/stacks/piloto_financiero/app.py) | `L987-L1100` | Mutaciones transaccionales (`/add`, `edit/<id>`, `delete/<id>`). |
| [`app.py`](file:///opt/stacks/piloto_financiero/app.py) | `L1160-L1280` | CSV streaming import/export de operaciones. |
| [`ine_api.py`](file:///opt/stacks/piloto_financiero/ine_api.py) | `L1-L190` | Integración API INE: series IPV (inmuebles) e IPC General (`IPC290751`). |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L20-L95` | `xirr(cash_flows)` y `calcular_tir_real(flujos_caja, ipc_map)` — TIR nominal y real anualizada. |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L97-L240` | `calcular_fifo(ops)` — Motor FIFO, comisiones, impuestos, multidivisa y amortización. |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L242-L355` | `calcular_historico_cartera(...)` — Evolución temporal capital vs valor. |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L357-L445` | `simular_benchmark_cartera(...)` — Simulación contra VWCE.DE. |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L447-L580` | `calcular_metricas_avanzadas(...)` — Sharpe, Volatilidad, Max Drawdown, TWR nominal y TWR real (IPC). |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L582-L750` | `calcular_rebalanceo(...)` — Algoritmo de cash-flow rebalancing. |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L765-L910` | `calcular_datos_fire(...)` — Proyección temporal, escenarios conservador vs TIR Real e hitos FIRE. |
| [`db.py`](file:///opt/stacks/piloto_financiero/db.py) | `L9-L14` | `get_db()` — Conector SQLite WAL con timeout 30s. |
| [`db.py`](file:///opt/stacks/piloto_financiero/db.py) | `L200-L320` | CRUD de transacciones `operaciones` y configuración FIRE (`save_fire_config`). |
| [`db.py`](file:///opt/stacks/piloto_financiero/db.py) | `L360-L440` | Mapeos de categorías `portfolio_tags` y `asset_tags`. |
| [`templates/index.html`](file:///opt/stacks/piloto_financiero/templates/index.html) | `L1-L50` | Layout central y contenedor de componentes Jinja2. |
| [`templates/components/header.html`](file:///opt/stacks/piloto_financiero/templates/components/header.html) | `L1-L70` | Cabecera: Modo Mirón (`👁️`), Conmutador Vista Esencial/Completa y selector Inmuebles. |
| [`templates/components/tab_resumen.html`](file:///opt/stacks/piloto_financiero/templates/components/tab_resumen.html) | `L1-L175` | Bento Grid KPIs, Gráfico Evolución con Benchmark y donas de distribución. |
| [`templates/components/tab_fire.html`](file:///opt/stacks/piloto_financiero/templates/components/tab_fire.html) | `L1-L165` | Panel FIRE: KPIs de progreso, simulador interactivo, Chart.js y tabla de hitos. |
| [`templates/components/modal_operacion.html`](file:///opt/stacks/piloto_financiero/templates/components/modal_operacion.html) | `L1-L170` | Modal de Operación (`opModal`) con datalist predictivo para tickers. |
| [`static/css/styles.css`](file:///opt/stacks/piloto_financiero/static/css/styles.css) | `L1-L325` | Estilos visuales dark-glassmorphism, tipografía JetBrains Mono y reglas de Modo Esencial. |
| [`static/js/api.js`](file:///opt/stacks/piloto_financiero/static/js/api.js) | `L1-L30` | Helper cliente HTTP centralizado (`API.fetch` y `API.post`). |
| [`static/js/ui.js`](file:///opt/stacks/piloto_financiero/static/js/ui.js) | `L1-L260` | Formateo de divisas, toasts, modales de configuración y `toggleVistaEsencial()`. |
| [`static/js/portfolio.js`](file:///opt/stacks/piloto_financiero/static/js/portfolio.js) | `L1-L430` | `cargarOperaciones()`, `toggleModoMiron()`, curva de patrimonio y gráficos de asignación. |
| [`static/js/operations.js`](file:///opt/stacks/piloto_financiero/static/js/operations.js) | `L1-L375` | CRUD de operaciones, modal interactivo, relleno predictivo de tickers y filtros. |
| [`static/js/rebalance.js`](file:///opt/stacks/piloto_financiero/static/js/rebalance.js) | `L1-L250` | `cargarRebalanceo()`, sugerencias de aportación y gestión de etiquetas/estrategias. |
| [`screener_service.py`](file:///opt/stacks/piloto_financiero/screener_service.py) | `L1-L530` | Motor Screener: Scraper S&P 500, cálculo Williams %R (14), precio target neto y filtros Value (Graham, Buffett, Deuda). |
| [`templates/components/tab_screener.html`](file:///opt/stacks/piloto_financiero/templates/components/tab_screener.html) | `L1-L285` | Pestaña Radar W%R: Bento KPIs, sliders dinámicos, filtros Value multicriterio, tabla de señales y modal .MC. |
| [`static/js/screener.js`](file:///opt/stacks/piloto_financiero/static/js/screener.js) | `L1-L445` | Cliente Screener: `cargarScreener()`, filtrado Value en vivo, Joyas Value, polling y precio target. |
| [`static/js/main.js`](file:///opt/stacks/piloto_financiero/static/js/main.js) | `L1-L55` | Bootstrapper de la aplicación y redimensionamiento reactivo de gráficos Chart.js. |


---

## 🔄 Protocolo de Automejora (Self-Improving Loop)
1. **Consulta inicial obligatoria**: Leer [`/home/leif/.gemini/config/skills/piloto-financiero-expert/lessons_learned.md`](file:///home/leif/.gemini/config/skills/piloto-financiero-expert/lessons_learned.md) antes de intervenir.
2. **Registro de aprendizajes**: Cualquier bug resuelto, incompatibilidad o gotcha debe documentarse inmediatamente en dicho archivo con formato conciso (causa raíz y solución).
3. **Mantenimiento del mapa**: Si se añade una función o endpoint nuevo, actualizar este mapa y [`SKILL.md`](file:///home/leif/.gemini/config/skills/piloto-financiero-expert/SKILL.md).
