# 📈 Piloto Financiero

## Descripción del Proyecto

Piloto Financiero es una aplicación web de monitorización en tiempo real de activos financieros que permite configurar alertas de precios personalizadas. Desarrollada para inversores y traders que necesitan seguimiento continuo de sus posiciones, la aplicación resuelve el problema de la monitorización manual de mercados financieros al automatizar la vigilancia de precios objetivo, enviando notificaciones instantáneas cuando se alcanzan los umbrales definidos.

La aplicación combina una interfaz web intuitiva con procesamiento backend robusto, utilizando tecnologías modernas para garantizar actualizaciones en tiempo real y persistencia de datos.

## ✨ Características Principales

- **Interfaz en Tiempo Real**: Utiliza Server-Sent Events (SSE) para actualizaciones automáticas de precios sin necesidad de recargar la página
- **Panel de Configuración Dinámica**: Modal integrado que permite gestionar todas las configuraciones desde la interfaz web
- **Alertas de Telegram**: Notificaciones automáticas enviadas a través de bots de Telegram cuando se alcanzan precios objetivo
- **Persistencia en SQLite**: Base de datos local que almacena monitores, alertas y configuraciones de forma persistente
- **Comprobación de Horarios de Mercado**: Respeta los horarios de apertura y cierre de mercados para evitar actualizaciones innecesarias
- **Búsqueda Inteligente**: Soporte para tickers estándar (AAPL, BTC-USD) e identificadores ISIN internacionales
- **Interfaz Responsive**: Diseño moderno con Bootstrap que se adapta a dispositivos móviles y de escritorio
- **Panel de Debug**: Herramientas de desarrollo integradas para monitoreo de logs del sistema

## 🛠️ Stack Tecnológico

### Backend
- **Flask**: Framework web Python ligero y extensible para el servidor principal
- **SQLite**: Base de datos embebida para persistencia local de datos
- **yfinance**: Biblioteca para obtención de datos financieros en tiempo real desde Yahoo Finance
- **Requests**: Cliente HTTP con configuración de reintentos y timeouts para comunicaciones robustas

### Frontend
- **HTML5/CSS3**: Estructura semántica y estilos personalizados
- **Bootstrap 5**: Framework CSS con tema oscuro personalizado para interfaz moderna
- **JavaScript (Vanilla)**: Interacciones dinámicas y manejo de Server-Sent Events
- **Server-Sent Events (SSE)**: Protocolo para actualizaciones en tiempo real desde el servidor

### Despliegue
- **Docker**: Contenedorización completa de la aplicación
- **Docker Compose**: Orquestación de servicios con configuración de healthchecks
- **Python 3.11**: Entorno de ejecución optimizado en imagen slim

## 🚀 Instalación y Despliegue

### Prerrequisitos
- Docker y Docker Compose instalados en el sistema
- Puerto 5000 disponible para la aplicación web

### Despliegue con Docker Compose

1. **Clonar o descargar** los archivos del proyecto en un directorio local

2. **Ejecutar el despliegue**:
   ```bash
   docker compose up -d
   ```

3. **Acceder a la aplicación**:
   - Abrir un navegador web
   - Navegar a `http://localhost:5000`
   - La interfaz web estará disponible inmediatamente

### Verificación del Despliegue

Para confirmar que la aplicación está funcionando correctamente:

```bash
# Verificar que el contenedor está ejecutándose
docker compose ps

# Ver logs de la aplicación
docker compose logs -f piloto-financiero

# Ejecutar healthcheck manual
curl http://localhost:5000/api/data
```

### Despliegue Local (Desarrollo)

Para ejecutar la aplicación fuera de Docker durante el desarrollo:

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la aplicación
python app.py
```

## ⚙️ Configuración

Toda la configuración de Piloto Financiero se gestiona cómodamente desde la interfaz web a través del modal de configuración (accesible con el botón ⚙️ en la esquina superior derecha).

### Configuraciones Disponibles

- **Telegram Bot Token**: Token del bot de Telegram para envío de alertas
- **Telegram Chat ID**: Identificador del chat donde recibir las notificaciones
- **Intervalo de Refresco**: Tiempo en minutos entre verificaciones de precios (mínimo 1 minuto)
- **Respetar Horario de Mercado**: Activa/desactiva la comprobación de horarios de apertura de mercados
- **Modo Debug**: Habilita el panel de logs del sistema para desarrollo y troubleshooting

### Configuración de Telegram

1. Crear un bot con [@BotFather](https://t.me/botfather) en Telegram
2. Obtener el token del bot
3. Iniciar conversación con el bot y enviar un mensaje
4. Usar la API de Telegram para obtener el Chat ID:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
5. Configurar ambos valores en el modal de configuración

## 📋 Política de Versiones

Piloto Financiero sigue el estándar de Versionado Semántico (Semantic Versioning) para mantener la consistencia y predictibilidad en las actualizaciones. La versión se controla a través del archivo `version.txt` y se inyecta en el contenedor Docker mediante el argumento `BUILD_VERSION` en `compose.yaml`.

### Formato de Versión
```
MAJOR.MINOR.PATCH
```

### Criterios de Incremento

#### **MAJOR** (Incremento del primer número: X.0.0)
Cambios incompatibles que requieren intervención del usuario:
- Modificaciones en la estructura de la base de datos que requieren migración manual
- Cambios en la API REST que rompen compatibilidad con versiones anteriores
- Eliminación de características principales o cambios en funcionalidades críticas
- Actualizaciones que requieren configuración adicional del usuario

#### **MINOR** (Incremento del segundo número: 1.X.0)
Nuevas funcionalidades compatibles hacia atrás:
- Adición de nuevas características o endpoints sin romper compatibilidad
- Mejoras en la interfaz de usuario que no afectan la funcionalidad existente
- Nuevas opciones de configuración opcionales
- Extensiones en el soporte de activos o mercados
- Mejoras en el rendimiento o estabilidad que no cambian el comportamiento esperado

#### **PATCH** (Incremento del tercer número: 1.0.X)
Correcciones y mejoras menores:
- Corrección de bugs y errores en la lógica de negocio
- Mejoras en la estabilidad y manejo de errores
- Actualizaciones de dependencias de seguridad
- Pequeñas mejoras en la interfaz de usuario
- Optimizaciones de rendimiento menores
- Correcciones en la documentación o mensajes de error

### Gestión de Versiones

1. **Actualización de versión**: Modificar el contenido del archivo `version.txt` con la nueva versión
2. **Sincronización Docker**: Actualizar el argumento `BUILD_VERSION` en `compose.yaml` para que coincida
3. **Reconstrucción**: Ejecutar `docker compose up -d --build` para aplicar los cambios
4. **Verificación**: Confirmar que la nueva versión se muestra en la interfaz web

### Ejemplos de Versionado

- `1.0.8` → `1.0.9`: Corrección de un bug en el manejo de ISINs
- `1.0.9` → `1.1.0`: Adición de soporte para nuevos mercados bursátiles
- `1.1.0` → `2.0.0`: Migración a nueva estructura de base de datos incompatible
3. **Reconstruye localmente** para probar:
   ```bash
   docker-compose up -d --build --force-recreate
   ```
4. **Haz commit y push** a GitHub:
   ```bash
   git add .
   git commit -m "Descripción del cambio"
   git push origin main
   ```

### En el servidor (Jarvis)

Para actualizar el servidor con los últimos cambios desde GitHub:

⚠️ **Importante**: Dockge puede modificar `compose.yaml` localmente, lo que bloquea `git pull`. Por eso el comando incluye `git reset --hard`.

```bash
cd /opt/stacks/piloto_financiero && \
sudo git reset --hard origin/main && \
sudo git pull && \
sudo docker compose up -d --build --force-recreate
```

**Desglose del comando:**
- `git reset --hard origin/main` - Descarta cambios locales y se alinea con GitHub
- `git pull` - Obtiene los últimos cambios
- `docker compose up -d --build --force-recreate` - Reconstruye y reinicia con nuevos cambios

## 📦 Versioning

La versión se muestra en la esquina superior derecha de la interfaz. Esto te ayuda a verificar que estés viendo la última versión después de un despliegue.

**Sistema de versiones**: Mantén sincronizados:
- `version.txt` - Versión mostrada en la interfaz
- `compose.yaml` - `BUILD_VERSION` en args

## � Búsqueda Inteligente de Activos

La aplicación es inteligente para encontrar activos:

- **Tickers directos**: `AAPL`, `BTC-USD`, `MSFT`
- **ISINs**: `ES0105065009`, `FR0000121014`, etc.
- **Búsqueda automática**: Si un ISIN falla, automáticamente busca el ticker correspondiente

**Ejemplos de ISINs que funcionan:**
- `ES0105065009` - Telefónica (España)
- `DE0005933931` - Siemens (Alemania)
- `FR0000121014` - LVMH (Francia) - ¡Ahora soportado!

```
piloto_financiero/
├── app.py                 # Aplicación principal (Flask)
├── compose.yaml           # Configuración Docker Compose
├── Dockerfile             # Configuración de imagen Docker
├── requirements.txt       # Dependencias Python
├── version.txt           # Versión actual
└── README.md             # Este archivo
```

## 🛠️ Tecnologías

- **Backend**: Flask (Python)
- **Finance**: yfinance
- **Frontend**: Bootstrap 5
- **Containerización**: Docker & Docker Compose
- **Orquestación**: Dockge

## 🔧 Configuración

### Variables de Entorno

La aplicación soporta las siguientes variables de entorno en `compose.yaml`:

```yaml
environment:
  - PYTHONUNBUFFERED=1  # No buffear salida de Python para ver logs en tiempo real
  - TZ=Europe/Madrid  # Zona horaria (ajustar si es diferente)
```

**Nota**: Los logs están deshabilitados por defecto para no afectar el rendimiento en producción.

### Panel de Debug

Cuando el modo debug está habilitado en la configuración (⚙️ → "Modo Debug"), aparece un botón 🐛 en la esquina inferior derecha. Al hacer clic:

- **Muestra logs en tiempo real** de todas las operaciones de búsqueda
- **Colores por nivel**: INFO (azul), WARNING (amarillo), ERROR (rojo)
- **Botón de limpiar** para resetear los logs
- **Máximo 100 entradas** para evitar sobrecarga de memoria

**Ejemplo de logs:**
```
[14:23:15] INFO: Intentando obtener precio para: AAPL
[14:23:15] INFO: ✓ Precio obtenido via fast_info: 175.43
[14:23:16] INFO: Añadiendo monitor para AAPL con objetivo 180.0
[14:23:16] INFO: ✓ Monitor añadido exitosamente: AAPL
```

## 🔧 API Endpoints

### `GET /`
Retorna la interfaz web principal.

### `GET /api/data`
Retorna monitores y alertas actuales.
```json
{
  "monitores": {...},
  "alertas": [...],
  "version": "1.0.0"
}
```

### `POST /api/add`
Agrega un nuevo monitor.
```json
{
  "ticker": "AAPL",
  "target": 150.50
}
```

### `DELETE /api/delete/<id>`
Elimina un monitor específico.

## 📝 Notas de Desarrollo

- El monitoreo en background se ejecuta cada 15 segundos
- Los precios se validan desde múltiples fuentes (fast_info, history, info)
- Los ISINs se detectan automáticamente por formato (2 letras + 9 dígitos)

## 🐛 Troubleshooting

**¿La versión no actualiza?**
- Verifica que `version.txt` y `BUILD_VERSION` en `compose.yaml` sean idénticos
- Ejecuta con `--force-recreate` para forzar reconstrucción

**¿No se obtiene el precio de un ticker?**
- Verifica que el ticker sea válido en Yahoo Finance
- Algunos activos requieren formato específico (ej: `BTC-USD` no `BTC`)

**¿El servidor no actualiza después de git push?**
- Ejecuta el comando completo con `git reset --hard` para sincronizar

## 📄 Licencia

MIT License

## 👨‍💻 Autor

Desarrollado como piloto financiero para monitoreo de activos.

---

**Última actualización**: 8 de mayo de 2026 - v1.0.2
**Cambios**: Panel de debug con logs detallados para troubleshooting
