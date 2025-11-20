#!/bin/bash
set -e

# Source logging library
source /app/lib/logging.sh

info "Starting Traefik-Home with Authentik integration..."
debug "Debug mode is enabled"

# Create custom nginx configuration if it doesn't exist
if [ ! -f /etc/nginx/conf.d/default.conf.original ]; then
    info "Backing up original nginx config..."
    cp /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.original
fi

info "Generating custom nginx configuration..."
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

info "Nginx configuration generated successfully"

# Test nginx configuration
info "Testing nginx configuration..."
nginx -t

# Check if docker-gen exists and get the original entrypoint
if [ -f /usr/local/bin/docker-gen ]; then
    info "Starting docker-gen..."
    
    # Start the original docker-gen in the background with watch mode
    docker-gen -watch -notify "nginx -s reload" /app/home.tmpl /usr/share/nginx/html/index.html.base &
    DOCKERGEN_PID=$!
    info "docker-gen started with PID: $DOCKERGEN_PID"
    
    # Function to create HTML wrapper with external apps
    create_html_wrapper() {
        info "Creating HTML wrapper..."
        
        # Read base HTML
        if [ ! -f /usr/share/nginx/html/index.html.base ]; then
            warn "WARNING: Base HTML file not found yet" >&2
            return
        fi
        
        # First, let's see what's actually in the file
        debug "Checking for script tag in base HTML..."
        if grep -q '<script type="application/json" id="external-app-labels">' /usr/share/nginx/html/index.html.base; then
            debug "Script tag found!"
        else
            debug "WARNING - Script tag NOT found in base HTML!"
            debug "Searching for any script tags..."
            grep -n '<script' /usr/share/nginx/html/index.html.base | head -5 >&2
        fi
        
        # Extract labels from the HTML template's script tag
        # The sed command removes the opening and closing script tags
        HOME_CONTAINER_LABELS=$(sed -n '/<script type="application\/json" id="external-app-labels">/,/<\/script>/p' /usr/share/nginx/html/index.html.base | sed '1d;$d' | sed '/^[[:space:]]*$/d')
        
        # Debug: Show what we extracted
        debug "Extracted label count: $(echo "$HOME_CONTAINER_LABELS" | grep -v '^[[:space:]]*$' | wc -l)"
        debug "First 10 lines of labels:" >&2
        if is_debug_enabled; then
            echo "$HOME_CONTAINER_LABELS" | grep -v '^[[:space:]]*$' | head -10 >&2
        fi
        debug "Full labels content:"
        debug "$HOME_CONTAINER_LABELS"
        debug "---"
        
        # Parse external apps if dynamic config exists
        EXTERNAL_APPS_JSON="[]"
        if [ -n "$TRAEFIK_DYNAMIC_CONFIG" ] && [ -f "$TRAEFIK_DYNAMIC_CONFIG" ]; then
            info "Parsing external apps from: $TRAEFIK_DYNAMIC_CONFIG"
            
            # Export for parser script
            export HOME_CONTAINER_LABELS
            export TRAEFIK_DYNAMIC_CONFIG
            
            # Parse external apps
            # Separate debug output (stderr) from JSON output (stdout)
            PARSE_OUTPUT=$(/app/parse-external-apps.sh 2>&1)
            
            # Extract JSON (everything that's valid JSON, usually the last line)
            EXTERNAL_APPS_JSON=$(echo "$PARSE_OUTPUT" | grep '^\[' | tail -1)

            # Show debug output
            if is_debug_enabled; then
                echo "$PARSE_OUTPUT" | grep "^DEBUG:" >&2
            fi
            
            # Validate JSON
            if echo "$EXTERNAL_APPS_JSON" | jq empty 2>/dev/null; then
                APP_COUNT=$(echo "$EXTERNAL_APPS_JSON" | jq 'length')
                info "Successfully parsed $APP_COUNT external app(s)"
            else
                error "Invalid JSON from parser, using empty array"
                EXTERNAL_APPS_JSON="[]"
            fi
        else
            warn "No Traefik dynamic config specified or file not found"
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
        
        info "HTML wrapper created successfully"
    }
    
    # Wait for initial file generation
    info "Waiting for docker-gen to create initial file..."
    for i in {1..30}; do
        if [ -f /usr/share/nginx/html/index.html.base ]; then
            info "Base HTML file found after ${i} seconds"
            break
        fi
        sleep 1
    done
    
    # Initial creation
    if [ -f /usr/share/nginx/html/index.html.base ]; then
        create_html_wrapper
    else
        error "Base HTML file not created after 30 seconds"
        # Create a minimal fallback
        echo "<html><body><h1>Traefik Home - Waiting for services...</h1></body></html>" > /usr/share/nginx/html/index.html
    fi
    
    # Watch for changes and re-inject
    info "Starting file watchers..."
    
    # Debounce tracking for regeneration
    LAST_REGEN=0
    
    # Function to regenerate with debouncing
    regenerate_if_needed() {
        local reason="$1"
        local now=$(date +%s)
        local diff=$((now - LAST_REGEN))
        
        # Only regenerate if at least 2 seconds have passed
        if [ $diff -ge 2 ]; then
            info "Detected change in $reason, regenerating..."
            create_html_wrapper
            LAST_REGEN=$now
        else
            debug "Skipping regeneration (debounce: ${diff}s < 2s)"
        fi
    }
    
    # Watch HTML base file changes (docker-gen)
    (
        while true; do
            if inotifywait -e modify /usr/share/nginx/html/index.html.base 2>/dev/null; then
                regenerate_if_needed "base HTML"
            fi
        done
    ) &
    HTML_WATCHER_PID=$!
    info "HTML watcher started with PID: $HTML_WATCHER_PID"

    # Cleanup function
    cleanup() {
        info "Cleaning up watchers..."
        [ -n "$HTML_WATCHER_PID" ] && kill $HTML_WATCHER_PID 2>/dev/null
        [ -n "$DOCKERGEN_PID" ] && kill $DOCKERGEN_PID 2>/dev/null
    }
    
    # Trap cleanup on exit
    trap cleanup EXIT INT TERM
    
else
    warn "docker-gen not found, running in static mode"
fi

# Start nginx in foreground
info "Starting nginx..."
exec nginx -g "daemon off;"
