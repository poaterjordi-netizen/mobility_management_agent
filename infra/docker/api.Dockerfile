FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system --gid 10001 mobility \
    && useradd --system --uid 10001 --gid mobility --home-dir /nonexistent mobility

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

USER 10001:10001
EXPOSE 8000

CMD ["mobility-agent-api"]
