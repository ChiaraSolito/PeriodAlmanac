# PeriodAlmanac: one image for both the web app and the Telegram bot.
# Multi-arch base image: works on the Oracle Ampere (arm64) VM and on x86 PCs.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Rome \
    MPLCONFIGDIR=/tmp/matplotlib

# System time zone data, so log timestamps use Europe/Rome.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Same uid as the default "ubuntu" user on the server, so files in ./data stay readable on the host.
RUN useradd --create-home --uid 1000 app

COPY app ./app
COPY scripts ./scripts

USER app
EXPOSE 8000

# Default command runs the web app; the bot service overrides it in docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
