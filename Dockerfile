FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY app.py .
COPY version.txt .
# ARG para invalidar caché con cada cambio
ARG BUILD_VERSION=1.0.8
LABEL version=${BUILD_VERSION}
EXPOSE 5000
CMD ["python", "-u", "app.py"]
