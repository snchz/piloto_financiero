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
| [`app.py`](file:///opt/stacks/piloto_financiero/app.py) | `L890-L1007` | Mutaciones transaccionales (`/add`, `edit/<id>`, `delete/<id>`). |
| [`app.py`](file:///opt/stacks/piloto_financiero/app.py) | `L1067-L1189` | CSV streaming import/export de operaciones. |
| [`ine_api.py`](file:///opt/stacks/piloto_financiero/ine_api.py) | `L1-L190` | Integración API INE: series IPV (inmuebles) e IPC General (`IPC290751`). |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L20-L95` | `xirr(cash_flows)` y `calcular_tir_real(flujos_caja, ipc_map)` — TIR nominal y real anualizada. |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L97-L240` | `calcular_fifo(ops)` — Motor FIFO, comisiones, impuestos, multidivisa y amortización. |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L242-L355` | `calcular_historico_cartera(...)` — Evolución temporal capital vs valor. |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L357-L445` | `simular_benchmark_cartera(...)` — Simulación contra VWCE.DE. |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L447-L580` | `calcular_metricas_avanzadas(...)` — Sharpe, Volatilidad, Max Drawdown, TWR nominal y TWR real (IPC). |
| [`portfolio_math.py`](file:///opt/stacks/piloto_financiero/portfolio_math.py) | `L506-L682` | `calcular_rebalanceo(...)` — Algoritmo de cash-flow rebalancing. |
| [`db.py`](file:///opt/stacks/piloto_financiero/db.py) | `L9-L14` | `get_db()` — Conector SQLite WAL con timeout 30s. |
| [`db.py`](file:///opt/stacks/piloto_financiero/db.py) | `L200-L320` | CRUD de transacciones `operaciones`. |
| [`db.py`](file:///opt/stacks/piloto_financiero/db.py) | `L360-L440` | Mapeos de categorías `portfolio_tags` y `asset_tags`. |
| [`templates/index.html`](file:///opt/stacks/piloto_financiero/templates/index.html) | `L335-L355` | Cabecera: botón Modo Mirón (`btn-modo-miron`, `👁️`) y switch Inmuebles. |
| [`templates/index.html`](file:///opt/stacks/piloto_financiero/templates/index.html) | `L880-L1060` | Modal de Operación (`opModal`). |
| [`templates/index.html`](file:///opt/stacks/piloto_financiero/templates/index.html) | `L1620-L1690` | `abrirModalOperacion(opId)` — Inyección segura de campos (`raw_cantidad`). |
| [`templates/index.html`](file:///opt/stacks/piloto_financiero/templates/index.html) | `L2000-L2027` | `toggleModoMiron()` — Toggle visual y recarga reactiva con `&miron=1`. |
| [`templates/index.html`](file:///opt/stacks/piloto_financiero/templates/index.html) | `L2028-L2378` | `cargarOperaciones()` — Renderizado de tablas, Bento Grid y gráficos. |
| [`templates/index.html`](file:///opt/stacks/piloto_financiero/templates/index.html) | `L2405-L2530` | `cargarRebalanceo(aportacion)` — Grid de rebalanceo y barras de progreso. |

---

## 🔄 Protocolo de Automejora (Self-Improving Loop)
1. **Consulta inicial obligatoria**: Leer [`/home/leif/.gemini/config/skills/piloto-financiero-expert/lessons_learned.md`](file:///home/leif/.gemini/config/skills/piloto-financiero-expert/lessons_learned.md) antes de intervenir.
2. **Registro de aprendizajes**: Cualquier bug resuelto, incompatibilidad o gotcha debe documentarse inmediatamente en dicho archivo con formato conciso (causa raíz y solución).
3. **Mantenimiento del mapa**: Si se añade una función o endpoint nuevo, actualizar este mapa y [`SKILL.md`](file:///home/leif/.gemini/config/skills/piloto-financiero-expert/SKILL.md).
