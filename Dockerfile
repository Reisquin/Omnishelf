FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY bundle-parts/ /tmp/bundle-parts/
RUN cat /tmp/bundle-parts/part-*.b64 | base64 -d | tar -xz -C /app \
 && rm -rf /tmp/bundle-parts \
 && pip install --no-cache-dir -r /app/backend/requirements.txt
EXPOSE 8000
CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
