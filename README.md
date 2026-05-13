# 📈 Piloto Financiero

## Descripción del Proyecto

Piloto Financiero es una aplicación web de monitorización en tiempo real de activos financieros y gestión de cartera. Desarrollada para inversores y traders que necesitan seguimiento continuo de sus posiciones, la aplicación resuelve el problema de la monitorización manual automatizando la vigilancia de precios objetivo y manteniendo un registro de las inversiones, la rentabilidad, y la evolución global de tu patrimonio.

La aplicación combina una interfaz web intuitiva, fluida (responsive) y "dummy-friendly" con procesamiento backend robusto, utilizando tecnologías modernas para garantizar actualizaciones en tiempo real y persistencia de datos.

## ✨ Características Principales

- **Interfaz en Tiempo Real**: Utiliza Server-Sent Events (SSE) para actualizaciones automáticas de precios sin necesidad de recargar la página.
- **Gestión de Cartera Completa**: 
  - Registro de operaciones (compras, ventas, aportaciones a fondos).
  - Cálculo automático del precio medio de compra (coste medio).
  - Seguimiento del Beneficio / Pérdida latente (sin vender) y consolidado (realizado).
  - Cálculo de la Rentabilidad Anualizada (TIR - XIRR) global de tu cartera.
- **Actividad Reciente y Noticias**: Feed centralizado que recopila alertas disparadas, movimientos diarios, e integra las últimas **noticias de Yahoo Finance** relacionadas con tus activos.
- **Diseño Responsivo y Limpio**: Interfaz organizada en pestañas ("Actividad Reciente", "Monitores y Alertas", "Operaciones y Cartera") totalmente adaptada a dispositivos móviles, tablets y monitores grandes. Terminología simplificada para todo tipo de usuarios.
- **Panel de Configuración Dinámica**: Modal integrado que permite gestionar el Token y Chat ID de Telegram, el intervalo de refresco y **los días de retención del feed de Actividad Reciente**.
- **Alertas de Telegram**: Notificaciones automáticas enviadas a través de bots de Telegram cuando se alcanzan precios objetivo.
- **Persistencia en SQLite**: Base de datos local que almacena monitores, alertas, operaciones de cartera y configuraciones de forma persistente.
- **Búsqueda Inteligente**: Soporte para tickers estándar (AAPL, BTC-USD) e identificadores ISIN internacionales.

## 🛠️ Stack Tecnológico

### Backend
- **Flask**: Framework web Python ligero y extensible para el servidor principal.
- **SQLite**: Base de datos embebida para persistencia local de datos.
- **yfinance**: Biblioteca para obtención de datos financieros en tiempo real y **noticias** desde Yahoo Finance.
- **pyxirr**: Cálculo preciso de la Tasa Interna de Retorno (TIR / XIRR) para el seguimiento de la cartera.

### Frontend
- **HTML5/CSS3**: Estructura semántica y estilos personalizados.
- **Bootstrap 5**: Framework CSS con tema oscuro personalizado para interfaz moderna y "mobile-first".
- **JavaScript (Vanilla)**: Interacciones dinámicas y manejo de Server-Sent Events.

### Despliegue
- **Docker**: Contenedorización completa de la aplicación.
- **Docker Compose**: Orquestación de servicios.
- **Python 3.11**: Entorno de ejecución optimizado en imagen slim.

## 🚀 Instalación y Despliegue

### Prerrequisitos
- Docker y Docker Compose instalados en el sistema.
- Puerto 5000 disponible para la aplicación web.

### Despliegue con Docker Compose

1. **Clonar o descargar** los archivos del proyecto en un directorio local.

2. **Ejecutar el despliegue**:
   ```bash
   docker compose up -d
   ```

3. **Acceder a la aplicación**:
   - Abrir un navegador web.
   - Navegar a `http://localhost:5000`.

### Despliegue Local (Desarrollo sin Docker)

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la aplicación
python app.py
```

## ⚙️ Configuración

Toda la configuración se gestiona cómodamente desde la interfaz web a través del modal de configuración (botón ⚙️ en la esquina superior derecha).

### Configuraciones Disponibles

- **Telegram Bot Token**: Token del bot de Telegram para envío de alertas.
- **Telegram Chat ID**: Identificador del chat donde recibir las notificaciones.
- **Intervalo de Refresco**: Tiempo en minutos entre verificaciones de precios.
- **Días de retención de Actividad Reciente**: Configura cuántos días de historial deseas conservar en tu pestaña de Actividad Reciente antes de purgarse.
- **Respetar Horario de Mercado**: Evita consultar precios los fines de semana o cuando las bolsas están cerradas.
- **Modo Debug**: Habilita el panel de logs inferior para desarrollo y troubleshooting.

## 🔄 Flujo de Trabajo en el Servidor

Para actualizar el servidor con los últimos cambios desde GitHub y reconstruir la aplicación limpiamente, utiliza el siguiente comando:

```bash
cd /opt/stacks/piloto_financiero && \
sudo git reset --hard origin/main && \
sudo git pull && \
sudo docker compose up -d --build --force-recreate
```

**Desglose del comando:**
- `git reset --hard origin/main`: Descarta posibles cambios locales que bloqueen la sincronización.
- `git pull`: Obtiene la última versión del repositorio.
- `docker compose up -d --build --force-recreate`: Reconstruye la imagen de Python desde cero aplicando los nuevos cambios en el código y reinicia el servicio.

## 📊 Búsqueda Inteligente de Activos

La aplicación encuentra y estandariza activos de forma automática:
- **Tickers directos**: `AAPL`, `BTC-USD`, `MSFT`.
- **ISINs**: `ES0105065009`, `FR0000121014`, etc.
- Si proporcionas un ISIN de un fondo europeo, el sistema buscará su ticker correspondiente en Yahoo Finance para ofrecerte su valoración (NAV) de forma automática.

## 📄 Licencia

MIT License
