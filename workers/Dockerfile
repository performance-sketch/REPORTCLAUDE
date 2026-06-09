FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY workers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY connectors/ ./connectors/
COPY workers/ ./workers/
COPY apps/api/app/config.py ./apps/api/app/config.py
COPY apps/api/app/database.py ./apps/api/app/database.py
COPY apps/api/app/models/ ./apps/api/app/models/
COPY apps/api/app/services/ ./apps/api/app/services/
COPY apps/api/app/schemas/ ./apps/api/app/schemas/

RUN touch apps/__init__.py apps/api/__init__.py apps/api/app/__init__.py

ENV PYTHONPATH=/app

CMD ["python", "-m", "workers.transform_worker"]
