#!/bin/bash
set -e

echo "Starting Traefik-Home with Authentik integration..."

# Create custom nginx configuration if it doesn't exist
if [ ! -f /etc/nginx/conf.d/default.conf.original ]; then
    echo "Backing up original nginx config..."
    cp /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.original
fi

echo "Generating custom nginx configuration..."
cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name _;
    
    root /usr/share/nginx/html;
    index index.html;
    
    # Main page location
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # API endpoint to expose Authentik headers as JSON
    location /api/user-info {
        default_type application/json;
        
        # Return user info from headers
        return 200 '{"username":"$http_x_authentik_username","email":"$http_x_authentik_email","name":"$http_x_authentik_name","isAdmin":"$http_x_authentik_is_admin"}';
        
        add_header Content-Type application/json;
        add_header Access-Control-Allow-Origin *;
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }
    
    # Serve custom CSS
    location /custom.css {
        add_header Content-Type text/css;
        add_header Cache-Control "public, max-age=3600";
    }
    
    # Serve background images if mounted
    location /backgrounds/ {
        add_header Cache-Control "public, max-age=86400";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

echo "Nginx configuration generated successfully"

# Test nginx configuration
echo "Testing nginx configuration..."
nginx -t

# Check if docker-gen exists and get the original entrypoint
if [ -f /usr/local/bin/docker-gen ]; then
    echo "Starting docker-gen..."
    
    # Start the original docker-gen in the background with watch mode
    docker-gen -watch -notify "nginx -s reload" /app/home.tmpl /usr/share/nginx/html/index.html.base &
    DOCKERGEN_PID=$!
    echo "docker-gen started with PID: $DOCKERGEN_PID"
    
    # Function to create HTML wrapper with external apps
    create_html_wrapper() {
        echo "Creating HTML wrapper..."
        
        # Read base HTML
        if [ ! -f /usr/share/nginx/html/index.html.base ]; then
            echo "WARNING: Base HTML file not found yet" >&2
            return
        fi
        
        # First, let's see what's actually in the file
        echo "DEBUG: Checking for script tag in base HTML..." >&2
        if grep -q '<script type="application/json" id="external-app-labels">' /usr/share/nginx/html/index.html.base; then
            echo "DEBUG: Script tag found!" >&2
        else
            echo "DEBUG: WARNING - Script tag NOT found in base HTML!" >&2
            echo "DEBUG: Searching for any script tags..." >&2
            grep -n '<script' /usr/share/nginx/html/index.html.base | head -5 >&2
        fi
        
        # Extract labels from the HTML template's script tag
        # The sed command removes the opening and closing script tags
        HOME_CONTAINER_LABELS=$(sed -n '/<script type="application\/json" id="external-app-labels">/,/<\/script>/p' /usr/share/nginx/html/index.html.base | sed '1d;$d' | sed '/^[[:space:]]*$/d')
        
        # Debug: Show what we extracted
        echo "DEBUG: Extracted label count: $(echo "$HOME_CONTAINER_LABELS" | grep -v '^[[:space:]]*$' | wc -l)" >&2
        echo "DEBUG: First 10 lines of labels:" >&2
        echo "$HOME_CONTAINER_LABELS" | grep -v '^[[:space:]]*$' | head -10 >&2
        echo "DEBUG: Full labels content:" >&2
        echo "$HOME_CONTAINER_LABELS" >&2
        echo "DEBUG: ---" >&2
        
        # Parse external apps if dynamic config exists
        EXTERNAL_APPS_JSON="[]"
        if [ -n "$TRAEFIK_DYNAMIC_CONFIG" ] && [ -f "$TRAEFIK_DYNAMIC_CONFIG" ]; then
            echo "Parsing external apps from: $TRAEFIK_DYNAMIC_CONFIG"
            
            # Export for parser script
            export HOME_CONTAINER_LABELS
            export TRAEFIK_DYNAMIC_CONFIG
            
            # Parse external apps
            # Separate debug output (stderr) from JSON output (stdout)
            PARSE_OUTPUT=$(/app/parse-external-apps.sh 2>&1)
            
            # Extract JSON (everything that's valid JSON, usually the last line)
            EXTERNAL_APPS_JSON=$(echo "$PARSE_OUTPUT" | grep '^\[' | tail -1)
            
            # Show debug output
            echo "$PARSE_OUTPUT" | grep "^DEBUG:" >&2
            
            # Validate JSON
            if echo "$EXTERNAL_APPS_JSON" | jq empty 2>/dev/null; then
                APP_COUNT=$(echo "$EXTERNAL_APPS_JSON" | jq 'length')
                echo "Successfully parsed $APP_COUNT external app(s)"
            else
                echo "ERROR: Invalid JSON from parser, using empty array" >&2
                EXTERNAL_APPS_JSON="[]"
            fi
        else
            echo "No Traefik dynamic config specified or file not found"
        fi
        
        # Inject external apps data before closing </head> tag
        awk -v json_data="$EXTERNAL_APPS_JSON" '
            /<\/head>/ {
                print "<script>window.EXTERNAL_APPS = " json_data ";</script>"
                print "</head>"
                next
            }
            { print }
        ' /usr/share/nginx/html/index.html.base > /usr/share/nginx/html/index.html
        
        echo "HTML wrapper created successfully"
    }
    
    # Wait for initial file generation
    echo "Waiting for docker-gen to create initial file..."
    for i in {1..30}; do
        if [ -f /usr/share/nginx/html/index.html.base ]; then
            echo "Base HTML file found after ${i} seconds"
            break
        fi
        sleep 1
    done
    
    # Initial creation
    if [ -f /usr/share/nginx/html/index.html.base ]; then
        create_html_wrapper
    else
        echo "ERROR: Base HTML file not created after 30 seconds" >&2
        # Create a minimal fallback
        echo "<html><body><h1>Traefik Home - Waiting for services...</h1></body></html>" > /usr/share/nginx/html/index.html
    fi
    
    # Watch for changes and re-inject
    echo "Starting file watcher..."
    while true; do
        if inotifywait -e modify /usr/share/nginx/html/index.html.base 2>/dev/null; then
            echo "Detected change in base HTML, regenerating..."
            create_html_wrapper
        fi
    done &
    WATCHER_PID=$!
    echo "File watcher started with PID: $WATCHER_PID"
else
    echo "WARNING: docker-gen not found, running in static mode"
fi

# Start nginx in foreground
echo "Starting nginx..."
exec nginx -g "daemon off;"
