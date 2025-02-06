# Use Python 3.12
FROM python:3.12-slim

# Install system dependencies for crawl4ai
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory
COPY backend /app/backend/

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV FLASK_APP=backend.app:app
ENV FLASK_DEBUG=0

# Expose port
EXPOSE 8080

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "120", "backend.app:app"]
