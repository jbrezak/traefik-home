#!/bin/bash
# Parse Traefik dynamic config and output JSON for external apps

CONFIG_FILE="${TRAEFIK_DYNAMIC_CONFIG:-}"
HOME_CONTAINER_LABELS="${HOME_CONTAINER_LABELS:-}"

# Exit if no config file specified
if [ -z "$CONFIG_FILE" ] || [ ! -f "$CONFIG_FILE" ]; then
    echo "[]"
    exit 0
fi

# Debug: Show what we received
echo "DEBUG: Parsing config file: $CONFIG_FILE" >&2
echo "DEBUG: HOME_CONTAINER_LABELS length: ${#HOME_CONTAINER_LABELS}" >&2
echo "DEBUG: First 500 chars of labels:" >&2
echo "$HOME_CONTAINER_LABELS" | head -c 500 >&2
echo "" >&2
echo "DEBUG: ---" >&2

# Parse YAML and extract routers and services
parse_config() {
    local config_file="$1"
    
    # Check if yq is available
    if command -v yq >/dev/null 2>&1; then
        parse_with_yq "$config_file"
    else
        echo "ERROR: yq not found, cannot parse YAML config" >&2
        echo "[]"
    fi
}

# Parse using yq (YAML processor)
parse_with_yq() {
    local config_file="$1"
    local apps="[]"
    
    # Get all router names
    local routers=$(yq eval '.http.routers | keys | .[]' "$config_file" 2>/dev/null)
    
    if [ -z "$routers" ]; then
        echo "DEBUG: No routers found in config file" >&2
        echo "[]"
        return
    fi
    
    echo "DEBUG: Found routers: $routers" >&2
    
    for router in $routers; do
        echo "DEBUG: Processing router: $router" >&2
        
        # Get router details
        local rule=$(yq eval ".http.routers.$router.rule" "$config_file" 2>/dev/null)
        local entrypoints=$(yq eval ".http.routers.$router.entryPoints | join(\",\")" "$config_file" 2>/dev/null)
        local service=$(yq eval ".http.routers.$router.service" "$config_file" 2>/dev/null)
        
        echo "DEBUG:   Rule: $rule" >&2
        echo "DEBUG:   EntryPoints: $entrypoints" >&2
        echo "DEBUG:   Service: $service" >&2
        
        # Skip if no service defined
        if [ "$service" = "null" ] || [ -z "$service" ]; then
            echo "DEBUG:   Skipping - no service" >&2
            continue
        fi
        
        # Get service URL
        local url=$(yq eval ".http.services.$service.loadBalancer.servers[0].url" "$config_file" 2>/dev/null)
        
        # Skip if no URL
        if [ "$url" = "null" ] || [ -z "$url" ]; then
            echo "DEBUG:   Skipping - no URL" >&2
            continue
        fi
        
        echo "DEBUG:   Backend URL: $url" >&2
        
        # Extract host from rule - BusyBox-compatible
        local host=""
        
        # Use sed instead of grep -P
        host=$(echo "$rule" | sed -n 's/.*Host[[:space:]]*([[:space:]]*`\([^`]*\)`.*/\1/p' | head -1)
        
        if [ -z "$host" ]; then
            echo "DEBUG:   Skipping - could not extract host from rule: $rule" >&2
            continue
        fi
        
        echo "DEBUG:   Extracted host: $host" >&2
        
        # Extract path if exists - BusyBox-compatible
        local path=$(echo "$rule" | sed -n 's/.*Path\(Prefix\)\?[[:space:]]*([[:space:]]*`\([^`]*\)`.*/\2/p' | head -1)
        [ -z "$path" ] && path="/"
        [ -z "$path" ] && path="/"
        
        echo "DEBUG:   Extracted path: $path" >&2
        
        # Determine protocol from entrypoints
        local protocol="http"
        if echo "$entrypoints" | grep -qi "websecure\|https"; then
            protocol="https"
        fi
        
        echo "DEBUG:   Protocol: $protocol" >&2
        
        # Check for label overrides
        local enable=$(get_label_value "$router" "enable")
        local alias=$(get_label_value "$router" "alias")
        local icon=$(get_label_value "$router" "icon")
        local admin=$(get_label_value "$router" "admin")
        
        echo "DEBUG:   Labels - Enable='$enable', Alias='$alias', Icon='$icon', Admin='$admin'" >&2
        
        # Default enable to true if not set
        [ -z "$enable" ] && enable="true"
        
        # Skip if explicitly disabled
        if [ "$enable" = "false" ]; then
            echo "DEBUG:   Skipping - explicitly disabled" >&2
            continue
        fi
        
        # Build full URL
        local full_url="$protocol://$host$path"
        
        # Escape for JSON (only quotes and backslashes)
        alias=$(printf '%s' "$alias" | sed 's/\\/\\\\/g; s/"/\\"/g')
        icon=$(printf '%s' "$icon" | sed 's/\\/\\\\/g; s/"/\\"/g')
        full_url=$(printf '%s' "$full_url" | sed 's/\\/\\\\/g; s/"/\\"/g')
        router=$(printf '%s' "$router" | sed 's/\\/\\\\/g; s/"/\\"/g')
        
        # Build app object as a JSON string
        local app_json="{\"Name\":\"$router\",\"Alias\":\"$alias\",\"URL\":\"$full_url\",\"Icon\":\"$icon\",\"Admin\":\"$admin\",\"Enable\":\"$enable\",\"Running\":true,\"External\":true}"
        
        # Add to apps array
        if [ "$apps" = "[]" ]; then
            apps="[$app_json]"
        else
            # Remove closing ] and add new item
            apps="${apps%]}"
            apps="${apps},$app_json]"
        fi
        
        echo "DEBUG:   Added app successfully" >&2
    done
    
    # Output the final JSON to stdout
    echo "DEBUG: Final JSON output:" >&2
    echo "$apps" >&2
    echo "$apps"
}

# Get label value from home container - improved parsing
get_label_value() {
    local service="$1"
    local property="$2"
    
    # Parse labels from environment variable
    # Format: traefik-home.app.<service>.<property>=<value>
    local pattern="traefik-home.app.${service}.${property}="
    
    echo "DEBUG:     Searching for pattern: $pattern" >&2
    
    # Method 1: Direct grep with proper escaping
    local result=$(echo "$HOME_CONTAINER_LABELS" | grep -F "$pattern" | head -1)
    
    if [ -n "$result" ]; then
        # Extract value after the = sign, removing any trailing whitespace
        local value="${result#*=}"
        value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        echo "DEBUG:     Found value: '$value'" >&2
        echo "$value"
        return
    fi
    
    # Method 2: Try with case-insensitive search
    result=$(echo "$HOME_CONTAINER_LABELS" | grep -iF "$pattern" | head -1)
    
    if [ -n "$result" ]; then
        local value="${result#*=}"
        value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        echo "DEBUG:     Found value (case-insensitive): '$value'" >&2
        echo "$value"
        return
    fi
    
    # Method 3: Try line-by-line parsing
    while IFS= read -r line; do
        if [[ "$line" == *"$pattern"* ]]; then
            local value="${line#*=}"
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "DEBUG:     Found value (line-by-line): '$value'" >&2
            echo "$value"
            return
        fi
    done <<< "$HOME_CONTAINER_LABELS"
    
    echo "DEBUG:     No match found for $pattern" >&2
    echo ""
}

# Main execution
parse_config "$CONFIG_FILE"
