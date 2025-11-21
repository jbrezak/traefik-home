#!/bin/bash
set -e

echo "Starting Traefik Home entrypoint..."

# Run initial page generation
echo "Running initial page generation..."
python3 /app/generate_page.py

# Check if traefik_watcher.py exists and start it in background if present
if [ -f /app/traefik_watcher.py ]; then
    echo "Starting traefik_watcher.py in background..."
    python3 /app/traefik_watcher.py &
fi

# Check if docker-gen is available
if command -v docker-gen >/dev/null 2>&1; then
    echo "Starting docker-gen in watch mode..."
    # Use docker-gen to watch for container changes and trigger regeneration
    exec docker-gen -watch -notify "python3 /app/generate_page.py" /app/templates/trigger.tmpl /tmp/trigger.out
else
    echo "Warning: docker-gen not found, falling back to periodic regeneration"
    # Fallback to periodic regeneration every 60 seconds
    while true; do
        sleep 60
        echo "Running periodic page regeneration..."
        python3 /app/generate_page.py || echo "Generation failed, will retry..."
    done
fi
