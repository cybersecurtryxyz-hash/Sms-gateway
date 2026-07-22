# SMS Integrator backend - Flask + gunicorn
FROM python:3.11-slim

# Prevent Python from writing .pyc files / buffering stdout (cleaner Railway logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first so Docker can cache this layer
# whenever only application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend (app/, run.py, wsgi.py, etc.)
COPY . .

# Railway injects PORT at runtime; gunicorn reads it via the shell form CMD below.
# --workers 1 is intentional: the APScheduler job in app/scheduler.py and the
# in-memory Flask-Limiter store both assume a single process, so scaling
# workers/replicas would fire schedules multiple times and reset rate limits
# per-worker. Scale by resources (CPU/RAM), not worker count, unless the
# scheduler is moved to a dedicated worker process first.
CMD gunicorn wsgi:app --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 120
