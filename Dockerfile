# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY task_aversion_app/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY task_aversion_app/ .

# Create data directory (for CSV files)
RUN mkdir -p data

# Expose the port NiceGUI runs on
EXPOSE 8080

# Set environment variable to allow external connections
ENV NICEGUI_HOST=0.0.0.0

# Run the application
CMD ["python", "app.py"]

