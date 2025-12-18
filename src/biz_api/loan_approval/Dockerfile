# Use official Python image as base
FROM python:3.11-slim

# Prevent debconf warnings
ENV DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files first (for layer caching)
COPY pyproject.toml ./

# Create virtual environment and install dependencies with prerelease support
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -e . --prerelease=allow --upgrade

# Copy application code
COPY *.py ./
COPY logging_config.py ./

# Expose port
EXPOSE 8070

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8070/mcp').read()"

# Start the app with Python using the virtual environment
CMD [".venv/bin/python", "main.py"]
