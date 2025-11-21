#!/bin/bash
set -e

echo "Starting Traefik Home entrypoint..."

# Configure nginx
echo "Configuring nginx..."
cat > /etc/nginx/sites-available/default << 'EOF'
server {
    listen 80;
    server_name _;
    
    root /usr/share/nginx/html;
    index index.html;
    
    # Main page location
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # Serve static files
    location ~* \.(css|js|json|jpg|jpeg|png|gif|ico|svg|woff|woff2|ttf|eot)$ {
        add_header Cache-Control "public, max-age=3600";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

# Test nginx configuration
echo "Testing nginx configuration..."
nginx -t

# Start nginx in the background
echo "Starting nginx..."
nginx

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
