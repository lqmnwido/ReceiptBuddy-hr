FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc git && \
    rm -rf /var/lib/apt/lists/*

# Copy local common library (avoids dependency on GitHub repo for schema changes)
COPY common/ /app/common/

COPY services/hr/ /app/services/hr/

RUN pip install --no-cache-dir -r /app/services/hr/requirements.txt && \
    pip install -e /app/common

ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["uvicorn", "services.hr.app.main:app", "--host", "0.0.0.0", "--port", "8003"]
