FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY frontend/ /app/frontend/
COPY admin/ /app/admin/

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 10000

CMD ["sh", "-c", "alembic upgrade head && python seed.py && exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --threads 2 --timeout 120 wsgi:app"]
