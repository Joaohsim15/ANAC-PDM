# Build a partir da raiz do repositorio, para levar schemas/features.json junto:
#   docker build -f api/Dockerfile -t anac-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# so as dependencias do pyproject; o codigo roda direto de /app
COPY api/pyproject.toml ./
RUN python -c "import tomllib; print('\\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

COPY schemas/features.json ./schemas/features.json
COPY api/app ./app

RUN useradd --uid 10001 --no-create-home appuser
USER appuser

# --factory: o app so e criado quando as variaveis do endpoint existem
CMD exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT} --workers 1
