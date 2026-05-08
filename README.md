# 📈 Piloto Financiero

Monitor de alertas de precios en tiempo real para activos financieros. Busca y monitorea tickers y ISINs directamente desde una interfaz web intuitiva.

## ✨ Características

- 🔍 **Búsqueda dual**: Busca por Ticker (AAPL, BTC-USD) o ISIN (ES0105065009)
- 📊 **Monitoreo en tiempo real**: Actualización cada 15 segundos
- 🔔 **Alertas automáticas**: Notificaciones cuando se alcanza el precio objetivo
- 📱 **Interfaz web responsive**: Accesible desde cualquier dispositivo
- 📦 **Versioning**: Seguimiento de versiones para detectar cambios

## 🚀 Inicio Rápido

### Requisitos
- Docker y Docker Compose
- Python 3.11+ (si ejecutas localmente)

### Instalación con Docker

```bash
docker-compose up -d --build
```

La aplicación estará disponible en `http://localhost:5000`

### Instalación local

```bash
pip install -r requirements.txt
python app.py
```

## 📋 Uso

1. Ingresa un **Ticker** (ej: `AAPL`, `BTC-USD`) o **ISIN** (ej: `ES0105065009`)
2. Define el **Precio Objetivo**
3. La aplicación monitoreará el precio automáticamente
4. Recibirás una **alerta** cuando se alcance el objetivo

## 🔄 Ciclo de Desarrollo y Despliegue

### En tu máquina local (VS Code)

Cada vez que hagas cambios en el código:

1. **Edita `app.py`** con tus cambios
2. **Actualiza la versión** en ambos archivos (mantenlos sincronizados):
   - `version.txt`: Cambia a la nueva versión (ej: `1.0.1`)
   - `compose.yaml`: Actualiza `BUILD_VERSION=1.0.1`
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

## 📁 Estructura del Proyecto

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

**Última actualización**: 8 de mayo de 2026
