# Use Python 3.14 slim image
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p raw/calgary raw/edmonton raw/toronto static templates

# Expose port
EXPOSE 5001

# Set environment variables
ENV FLASK_APP=scripts/web_app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# MongoDB connection (can be overridden via docker-compose or runtime)
ENV MONGO_URI=mongodb://root:fcHIctV8xDjncLMR0cwCzu6oDfHyhNqCPj2S@10.0.0.123:27023/?directConnection=true
ENV MONGO_DB=rentfaster
ENV MONGO_COLLECTION=listings_detailed

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5001/', timeout=5)" || exit 1

# Run the web application
CMD ["python", "scripts/web_app.py"]
