FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DOCKER_GEN_VERSION=0.12.0

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install docker-gen
RUN curl -Lo /tmp/docker-gen.tar.gz \
    https://github.com/nginx-proxy/docker-gen/releases/download/${DOCKER_GEN_VERSION}/docker-gen-linux-amd64-${DOCKER_GEN_VERSION}.tar.gz && \
    tar -C /usr/local/bin -xvzf /tmp/docker-gen.tar.gz && \
    rm /tmp/docker-gen.tar.gz && \
    chmod +x /usr/local/bin/docker-gen

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/generate_page.py /app/
COPY app/entrypoint.sh /app/
COPY app/templates/ /app/templates/

# Make scripts executable
RUN chmod +x /app/generate_page.py /app/entrypoint.sh

# Create output directory
RUN mkdir -p /usr/share/nginx/html

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
