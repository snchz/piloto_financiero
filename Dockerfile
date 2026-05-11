FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && \
    apt-get install --no-install-recommends -y curl && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py db.py finance_api.py monitor_worker.py notifications.py portfolio_math.py version.txt ./
COPY templates templates
RUN mkdir -p data
# ARG para invalidar caché con cada cambio
ARG BUILD_VERSION=1.0.8
LABEL version=${BUILD_VERSION}
EXPOSE 5000
CMD ["python", "-u", "app.py"]
