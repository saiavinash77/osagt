# Application image — runs the agent code itself
# (The sandbox image in Dockerfile.sandbox is separate and used at runtime)

FROM python:3.11-slim

# Install git (needed for cloning/pushing) and curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create log directory
RUN mkdir -p logs

# Non-root user for security
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

# Default: web server. Override in docker-compose for scheduler.
CMD ["python", "web_server.py"]
