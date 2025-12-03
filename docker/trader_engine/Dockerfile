FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG APP_USER=appuser
ARG APP_UID=1000
ARG APP_GID=1000

RUN groupadd -g ${APP_GID} ${APP_USER} \
    && useradd -m -u ${APP_UID} -g ${APP_GID} -s /sbin/nologin ${APP_USER}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy core trader engine files
COPY main.py /app/main.py
COPY src/ /app/src/
COPY telegram/ /app/telegram/
COPY run_mathematricks_trader.py /app/run_mathematricks_trader.py
COPY signal_sender.py /app/signal_sender.py

# Create logs directory and set permissions
RUN mkdir -p /app/logs \
    && chmod -R 777 /app/logs

RUN chown -R ${APP_USER}:${APP_USER} /app

USER ${APP_USER}

WORKDIR /app

CMD ["python", "main.py"]
