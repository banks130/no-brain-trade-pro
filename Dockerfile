FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir aiohttp aiodns speedups

# Install main requirements
RUN pip install --no-cache-dir \
    websockets \
    aiohttp \
    python-dotenv \
    sqlalchemy \
    asyncpg \
    aiosqlite \
    python-telegram-bot \
    fastapi \
    uvicorn \
    jinja2 \
    cryptography \
    httpx \
    pydantic \
    base58

COPY . .

RUN find . -type d -exec touch {}/__init__.py \;

ENV PYTHONPATH=/app
ENV PORT=8080

EXPOSE 8080

CMD ["python", "main.py"]
