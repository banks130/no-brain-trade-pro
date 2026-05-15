FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and force install despite externally managed environment
RUN pip install --no-cache-dir --upgrade pip setuptools wheel --break-system-packages

# Copy requirements first
COPY requirements.txt .

# Install with the break-system-packages flag
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application
COPY . .

# Create __init__.py files
RUN find . -type d -exec touch {}/__init__.py \;

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8080

EXPOSE 8080

CMD ["python", "main.py"]
