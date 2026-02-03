# Optimasol all-in-one image (app + mosquitto broker)
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/optimasol \
    VIRTUAL_ENV=/opt/venv

WORKDIR ${APP_HOME}

# System deps
 RUN apt-get update && apt-get install -y --no-install-recommends \
    mosquitto \
    ca-certificates \
    git \
    tini \
 && rm -rf /var/lib/apt/lists/*

# Ensure broker data dir exists (mapped to volume)
RUN mkdir -p /var/lib/mosquitto

# Python venv
RUN python -m venv ${VIRTUAL_ENV} \
 && ${VIRTUAL_ENV}/bin/pip install --upgrade pip
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# App sources
COPY pyproject.toml README* ${APP_HOME}/
COPY src ${APP_HOME}/src
COPY web ${APP_HOME}/web
COPY client_sample_shell.json config.json logging.config.json ${APP_HOME}/

# Install app
RUN pip install .

# Mosquitto config
COPY docker/mosquitto.conf /etc/mosquitto/mosquitto.conf

# Entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/opt/optimasol/data", "/opt/optimasol/backups", "/var/lib/mosquitto"]

EXPOSE 8000 1883

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
