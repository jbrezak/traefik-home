#!/bin/bash
# Logging library for traefik-home

# Check if debug mode is enabled
is_debug_enabled() {
    [ "${DEBUG:-false}" = "true" ]
}

# Log debug messages
debug() {
    if is_debug_enabled; then
        echo "DEBUG: $*" >&2
    fi
}

# Log info messages
info() {
    echo "INFO: $*" >&2
}

# Log warning messages
warn() {
    echo "WARN: $*" >&2
}

# Log error messages
error() {
    echo "ERROR: $*" >&2
}
