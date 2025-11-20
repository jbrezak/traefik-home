FROM ghcr.io/santimar/traefik-home:latest

# Install bash and required tools
RUN apk add --no-cache bash curl jq yq inotify-tools

# Copy app files
COPY app/docker-entrypoint.sh /app/docker-entrypoint.sh
COPY app/parse-external-apps.sh /app/parse-external-apps.sh
COPY app/logging.sh /app/lib/logging.sh
RUN chmod +x /app/*.sh

# Copy custom template generator
COPY app/home.tmpl /app/home.tmpl

# Health check - verify nginx is responding
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Use custom entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
