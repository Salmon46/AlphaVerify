# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for compilation of some libs like numpy/pandas/matplotlib)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for cache
COPY requirements.txt .

# Install Dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy Backend Code
COPY . .

# Expose Port
EXPOSE 8000

# Run Command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
