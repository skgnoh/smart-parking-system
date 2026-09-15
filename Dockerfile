# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Tell our app to store the database in the /app/data directory (which we will mount)
ENV DATA_DIR=/app/data

# Install system dependencies (e.g. for Pillow or SQLite if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the API port
EXPOSE 8000

# Use uvicorn directly for production-like running (disabling auto-reload for stability)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
