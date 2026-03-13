FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN pip install playwright && \
    playwright install chromium && \
    playwright install-deps

WORKDIR /app

# Copy requirements
COPY api/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application (api folder)
COPY api/ .

# Copy frontend build files to app/dist
COPY app/dist /app/app/dist

# Create downloads directory
RUN mkdir -p /app/downloads

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
