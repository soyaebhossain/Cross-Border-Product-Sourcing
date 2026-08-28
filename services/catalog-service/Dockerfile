FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY services/catalog-service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY services/catalog-service/alembic.ini ./
COPY services/catalog-service/migrations ./migrations
COPY services/catalog-service/docker-entrypoint.sh ./
RUN sed -i 's/\r$//' ./docker-entrypoint.sh \
    && chmod +x ./docker-entrypoint.sh

COPY services/catalog-service/app ./app
COPY apps/web-next/data/public-catalog.snapshot.json ./app/seed_data/public-catalog.snapshot.json
COPY services/catalog-service/media ./media
COPY services/catalog-service/scripts ./scripts
COPY datasets/ml-starter-v1 ./datasets/ml-starter-v1

RUN useradd --create-home --uid 10001 sourceai \
    && chown -R sourceai:sourceai /app

USER sourceai
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
