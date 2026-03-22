# Progressusbot / automatorio-agent API + агенты (generate, validate_edit).
# Сборка из корня репозитория:
#   docker build -t progressusbot-api .
# Запуск:
#   docker run --env-file .env -p 8088:8088 progressusbot-api

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    openssh-client \
    ca-certificates \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY agents ./agents

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir .

# Chromium для Playwright (скриншоты / браузер в validate и generate).
RUN playwright install-deps chromium \
    && playwright install chromium

EXPOSE 8088

# local: графы в процессе | langgraph: прокси на отдельный LangGraph API
ENV PROGRESSUSBOT_BACKEND=local

CMD ["uvicorn", "agents.progressusbot_api.app:app", "--host", "0.0.0.0", "--port", "8088"]
