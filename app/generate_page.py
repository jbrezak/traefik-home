#!/usr/bin/env python3
"""Generate home page with app list from Docker labels and Traefik config."""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import docker
    import requests
except ImportError:
    # Allow import to succeed during testing when modules are mocked
    # Check if we're in a test environment or if modules are already mocked
    if ('pytest' not in sys.modules and 
        'unittest' not in sys.modules and
        'docker' not in sys.modules and
        'requests' not in sys.modules):
        print("Error: Required dependencies not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)
    # Import mocked modules if they exist, or create placeholders
    import docker  # type: ignore
    import requests  # type: ignore


def atomic_write(filepath: str, content: str, mode: int = 0o644) -> None:
    """
    Write content to file atomically using a temp file and rename.
    
    Args:
        filepath: Target file path
        content: Content to write
        mode: File permissions (default: 0o644)
    """
    filepath_obj = Path(filepath)
    # Create temp file in same directory to ensure same filesystem
    fd, temp_path = tempfile.mkstemp(
        dir=filepath_obj.parent,
        prefix=f".{filepath_obj.name}.",
        suffix=".tmp"
    )
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.chmod(temp_path, mode)
        # Atomic rename
        os.rename(temp_path, filepath)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def discover_traefik_api() -> Optional[str]:
    """
    Discover the Traefik API endpoint using multiple heuristics.
    
    Returns:
        Traefik API base URL or None if not found
    """
    # Try environment variable first
    env_url = os.getenv("TRAEFIK_API_URL")
    if env_url:
        if test_traefik_endpoint(env_url):
            print(f"Using Traefik API from env: {env_url}")
            return env_url.rstrip("/")
    
    # Try common container DNS names
    for host in ["traefik", "traefik-proxy", "reverse-proxy"]:
        for port in [8080, 8081]:
            candidate = f"http://{host}:{port}"
            if test_traefik_endpoint(candidate):
                print(f"Discovered Traefik API at: {candidate}")
                return candidate
    
    # Try localhost
    for port in [8080, 8081]:
        candidate = f"http://localhost:{port}"
        if test_traefik_endpoint(candidate):
            print(f"Discovered Traefik API at: {candidate}")
            return candidate
    
    return None


def test_traefik_endpoint(base_url: str, timeout: float = 2.0) -> bool:
    """Test if a Traefik API endpoint is accessible."""
    if not base_url:
        return False
    base_url = base_url.rstrip("/")
    try:
        resp = requests.get(f"{base_url}/api/http/routers", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        pass
    try:
        resp = requests.get(f"{base_url}/api/routers", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        pass
    return False


def fetch_traefik_routers(traefik_api: Optional[str]) -> Dict[str, List[str]]:
    """
    Fetch routers from Traefik API and build URL map.
    
    This discovers routers from file provider, kubernetes, consul, etc.
    that are not visible via Docker container labels.
    
    Args:
        traefik_api: Traefik API base URL
        
    Returns:
        Dictionary mapping service/router names to URLs
    """
    service_urls = {}
    
    if not traefik_api:
        return service_urls
    
    routers = None
    try:
        resp = requests.get(f"{traefik_api.rstrip('/')}/api/http/routers", timeout=5)
        resp.raise_for_status()
        routers = resp.json()
    except Exception as e:
        print(f"Warning: Could not fetch Traefik routers: {e}", file=sys.stderr)
        try:
            resp = requests.get(f"{traefik_api.rstrip('/')}/api/routers", timeout=5)
            resp.raise_for_status()
            routers = resp.json()
        except Exception as e2:
            print(f"Warning: Fallback routers endpoint also failed: {e2}", file=sys.stderr)
            return service_urls
    
    if not routers:
        return service_urls
    
    # Handle both list and dict response formats
    router_items = []
    if isinstance(routers, dict):
        router_items = list(routers.items())
    elif isinstance(routers, list):
        for item in routers:
            if not isinstance(item, dict):
                continue
            rname = item.get("name") or item.get("router") or ""
            router_items.append((rname, item))
    
    for rname, rdata in router_items:
        try:
            if not isinstance(rdata, dict):
                continue
            
            # Get entrypoints and rule
            entrypoints = rdata.get("entryPoints") or rdata.get("entrypoints") or []
            rule = rdata.get("rule") or rdata.get("Rule") or ""
            service = rdata.get("service") or rdata.get("Service") or ""
            
            if not rule:
                continue
            
            # Determine protocol from entrypoints
            protocol = "http"
            if entrypoints:
                for ep in entrypoints:
                    ep_lower = str(ep).lower()
                    if "secure" in ep_lower or "https" in ep_lower or "websecure" in ep_lower:
                        protocol = "https"
                        break
            
            # Parse Host() rules to get URLs
            urls = parse_traefik_rule(rule, protocol=protocol)
            
            if not urls:
                continue
            
            # Get service name without provider suffix
            svc_norm = service.split("@")[0] if isinstance(service, str) else str(service)
            
            # Skip internal router artifacts
            if svc_norm.lower() == "router" or (isinstance(rname, str) and rname.lower() == "router"):
                continue
            
            # Store under service name
            if svc_norm:
                if svc_norm not in service_urls:
                    service_urls[svc_norm] = []
                service_urls[svc_norm].extend(urls)
            
            # Also store under full router name (e.g., "omv@file")
            if rname:
                if rname not in service_urls:
                    service_urls[rname] = []
                service_urls[rname].extend(urls)
                
                # Store under router base name as well (e.g., "omv" from "omv@file")
                rname_base = rname.split("@")[0] if "@" in rname else rname
                if rname_base and rname_base != svc_norm:
                    if rname_base not in service_urls:
                        service_urls[rname_base] = []
                    service_urls[rname_base].extend(urls)
        except Exception as e:
            print(f"Warning: Error parsing router {rname}: {e}", file=sys.stderr)
    
    # Remove duplicates
    for key in service_urls:
        service_urls[key] = list(dict.fromkeys(service_urls[key]))
    
    return service_urls


def build_service_url_map(docker_client: docker.DockerClient, traefik_api: Optional[str] = None) -> tuple[Dict[str, List[str]], Dict[str, Dict[str, Any]]]:
    """
    Build a map of service names to their URLs and metadata from Docker container labels
    AND from Traefik API (for file provider, kubernetes, etc.).
    
    Args:
        docker_client: Docker client instance
        traefik_api: Optional Traefik API base URL
        
    Returns:
        Tuple of (service_urls dict, service_metadata dict)
    """
    service_urls = {}
    service_metadata = {}
    
    # First, fetch routers from Traefik API (includes file provider, etc.)
    if traefik_api:
        print(f"Fetching routers from Traefik API: {traefik_api}")
        traefik_urls = fetch_traefik_routers(traefik_api)
        print(f"Found {len(traefik_urls)} services from Traefik API")
        service_urls.update(traefik_urls)
    
    # Then, get additional info from Docker containers
    try:
        containers = docker_client.containers.list()
    except Exception as e:
        print(f"Warning: Could not list Docker containers: {e}", file=sys.stderr)
        return service_urls, service_metadata
    
    for container in containers:
        labels = container.labels
        
        # Skip the traefik-home container itself
        service_name = labels.get("com.docker.compose.service", container.name)
        if service_name == "traefik-home":
            continue
        
        # Extract traefik-home specific metadata
        # Check if container has ANY traefik-home labels
        has_traefik_home_labels = any(k.startswith("traefik-home.") for k in labels.keys())
        
        icon = labels.get("traefik-home.icon", "")
        alias = labels.get("traefik-home.alias", "")
        hide = labels.get("traefik-home.hide", "").lower() == "true"
        is_admin = labels.get("traefik-home.admin", "").lower() == "true"
        enable = labels.get("traefik-home.enable", "").lower()
        
        # Only store metadata if the container has traefik-home labels
        # This is used to determine which apps to include in the final list
        if has_traefik_home_labels and service_name not in service_metadata:
            service_metadata[service_name] = {
                "icon": icon,
                "alias": alias,
                "hide": hide,
                "is_admin": is_admin,
                "enable": enable if enable else "true"  # Default to true if not specified
            }
        
        # Find all Traefik HTTP routers from Docker labels
        for key, value in labels.items():
            if key.startswith("traefik.http.routers.") and key.endswith(".rule"):
                # Extract router name
                parts = key.split(".")
                if len(parts) >= 4:
                    router_name = parts[3]
                    
                    # Skip routers with "redirect" in the name (HTTP->HTTPS redirects)
                    if "redirect" in router_name.lower():
                        continue
                    
                    # Determine protocol from entrypoint or assume http
                    protocol = "http"
                    entrypoint_key = f"traefik.http.routers.{router_name}.entrypoints"
                    if entrypoint_key in labels:
                        entrypoints = labels[entrypoint_key].lower()
                        if "websecure" in entrypoints or "https" in entrypoints:
                            protocol = "https"
                    
                    # Parse Host() or HostRegexp() rules
                    urls = parse_traefik_rule(value, protocol=protocol)
                    
                    if urls and service_name:
                        # Store under service name
                        if service_name not in service_urls:
                            service_urls[service_name] = []
                        service_urls[service_name].extend(urls)
                        
                        # Also store under router name for external app matching
                        # (e.g., "omv@docker" if service is "omv")
                        router_key = f"{router_name}@docker"
                        if router_key not in service_urls:
                            service_urls[router_key] = []
                        service_urls[router_key].extend(urls)
    
    # Remove duplicates while preserving order
    for service_name in service_urls:
        seen = set()
        unique_urls = []
        for url in service_urls[service_name]:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        service_urls[service_name] = unique_urls
    
    return service_urls, service_metadata


def parse_traefik_rule(rule: str, protocol: str = "http") -> List[str]:
    """
    Parse Traefik rule to extract hostnames.
    
    Args:
        rule: Traefik rule string (e.g., "Host(`example.com`) || Host(`www.example.com`)")
        protocol: Protocol to use (http or https)
        
    Returns:
        List of URLs with specified protocol
    """
    urls = []
    
    # Split by OR operators
    parts = rule.replace("||", "|").split("|")
    
    for part in parts:
        part = part.strip()
        
        # Extract Host() patterns
        if "Host(" in part:
            # Find content between Host( and )
            start = part.find("Host(") + 5
            end = part.find(")", start)
            if end > start:
                host = part[start:end].strip("`").strip("'").strip('"')
                # Build full URL with specified protocol
                urls.append(f"{protocol}://{host}")
        
        # Extract HostRegexp() patterns
        elif "HostRegexp(" in part:
            start = part.find("HostRegexp(") + 11
            end = part.find(")", start)
            if end > start:
                host = part[start:end].strip("`").strip("'").strip('"')
                # For regexp, take as-is but may need cleanup
                host = host.replace("{", "").replace("}", "").split(",")[0].strip()
                urls.append(f"{protocol}://{host}")
    
    return urls


def load_overrides(override_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load app overrides from JSON file.
    
    Args:
        override_file: Path to override JSON file
        
    Returns:
        Dictionary of overrides
    """
    if not override_file or not os.path.exists(override_file):
        return {}
    
    try:
        with open(override_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load overrides from {override_file}: {e}", file=sys.stderr)
        return {}


def build_app_list(
    service_urls: Dict[str, List[str]],
    service_metadata: Dict[str, Dict[str, Any]],
    overrides: Dict[str, Any],
    external_apps: Dict[str, Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Build final app list with all URLs and metadata.
    
    Only includes apps that have:
    1. traefik-home.* labels on their Docker container (service_metadata), OR
    2. traefik-home.app.<name>.* labels on the traefik-home container (external_apps)
    
    Apps discovered from Traefik API are ONLY used for URL resolution, not for
    automatic inclusion. They must be explicitly enabled via traefik-home labels.
    
    Args:
        service_urls: Map of service names to URLs
        service_metadata: Map of service names to metadata from Docker labels
        overrides: Override configuration
        external_apps: External apps from traefik-home.app.<name> labels
        
    Returns:
        List of app dictionaries
    """
    if external_apps is None:
        external_apps = {}
    
    apps = []
    
    # Process services from Docker that have traefik-home.* labels
    # Only include services that have metadata (meaning they have traefik-home labels)
    for service_name, urls in service_urls.items():
        # Skip router keys (these are just for external app matching)
        if service_name.endswith("@docker") or service_name.endswith("@file"):
            continue
        
        # Skip if this service name is defined as an external app
        # (external apps are processed in the next loop with their full config)
        if service_name in external_apps:
            continue
        
        # IMPORTANT: Only include services that have traefik-home metadata
        # Services discovered from Traefik API without traefik-home labels are skipped
        metadata = service_metadata.get(service_name, {})
        if not metadata:
            # No traefik-home labels on this container, skip it
            continue
        
        override = overrides.get(service_name, {})
        
        # Check if app should be hidden (from Docker label or override)
        if metadata.get("hide", False) or override.get("Hide", False):
            continue
        
        # Check if enabled (default to True for Docker services)
        if not override.get("Enable", True):
            continue
        
        # Determine category based on admin flag
        is_admin = metadata.get("is_admin", False)
        default_category = "Admin" if is_admin else "Apps"
        
        # Get icon from Docker label first, then override
        icon = metadata.get("icon", "") or override.get("Icon", "")
        
        # Get alias from Docker label first, then override
        alias = metadata.get("alias", "")
        display_name = override.get("Name", alias if alias else service_name.replace("-", " ").title())
        
        app = {
            "name": display_name,
            "urls": urls,  # Include ALL URLs, no filtering
            "icon": icon,
            "description": override.get("Description", ""),
            "category": override.get("Category", default_category),
            "badge": override.get("Badge", ""),
        }
        apps.append(app)
    
    # Process external apps from traefik-home.app.<name> labels
    for app_name, app_config in external_apps.items():
        # Skip if not enabled
        if not app_config.get("enabled", False):
            continue
        
        # Determine URLs for external app using flexible matching heuristics
        urls = set()
        
        # Try to find matching Traefik router(s) using multiple patterns
        for svc_key, url_list in service_urls.items():
            if not svc_key:
                continue
            # Flexible matching: exact match, containment in either direction, or hyphenated variants
            if (app_name == svc_key or 
                app_name in svc_key or 
                svc_key in app_name or 
                svc_key.startswith(app_name + "-") or 
                app_name.startswith(svc_key + "-")):
                urls.update(url_list)
                print(f"Info: External app '{app_name}' matched Traefik service '{svc_key}'")
        
        # Convert to sorted list
        urls = sorted(list(urls))
        
        # Add any manually specified URLs from .url labels (these are additive)
        if "urls" in app_config:
            urls.extend(app_config["urls"])
            urls = sorted(list(set(urls)))  # Remove duplicates and sort
        
        # Skip if no URLs found anywhere
        if not urls:
            print(f"Warning: External app '{app_name}' has no matching Traefik router and no .url labels. Skipping.")
            continue
        
        # Determine category
        is_admin = app_config.get("is_admin", False)
        default_category = "Admin" if is_admin else "Apps"
        
        app = {
            "name": app_config.get("alias", app_name.replace("-", " ").title()),
            "urls": urls,
            "icon": app_config.get("icon", ""),
            "description": app_config.get("description", ""),
            "category": app_config.get("category", default_category),
            "badge": "",
        }
        apps.append(app)
    
    # Process override-only entries (apps not in Docker but defined in overrides)
    for service_name, override in overrides.items():
        if service_name not in service_urls and service_name not in external_apps:
            # This is an override-only entry
            if override.get("Hide", False):
                continue
            
            # Must explicitly enable override-only entries
            if not override.get("Enable", False):
                continue
            
            # Build URLs from override
            urls = []
            if "Url" in override:
                urls.append(override["Url"])
            elif "URLs" in override:
                urls.extend(override["URLs"])
            
            if not urls:
                continue
            
            app = {
                "name": override.get("Name", service_name.replace("-", " ").title()),
                "urls": urls,
                "icon": override.get("Icon", ""),
                "description": override.get("Description", ""),
                "category": override.get("Category", "Apps"),
                "badge": override.get("Badge", ""),
            }
            apps.append(app)
    
    # Sort by name
    apps.sort(key=lambda x: x["name"])
    
    return apps


def get_external_apps_from_labels(docker_client: docker.DockerClient) -> Dict[str, Dict[str, Any]]:
    """
    Get external apps defined via traefik-home.app.<name> labels on the traefik-home container.
    
    Args:
        docker_client: Docker client instance
        
    Returns:
        Dictionary mapping app names to their configuration
    """
    external_apps = {}
    
    try:
        current_container_id = os.getenv("HOSTNAME")
        if current_container_id:
            try:
                container = docker_client.containers.get(current_container_id)
                labels = container.labels
                
                # Parse traefik-home.app.<name>.<attribute> labels
                for key, value in labels.items():
                    if key.startswith("traefik-home.app."):
                        parts = key.split(".")
                        if len(parts) >= 4:
                            app_name = parts[2]
                            attribute = parts[3]
                            
                            if app_name not in external_apps:
                                external_apps[app_name] = {}
                            
                            # Map attribute names
                            if attribute == "enable":
                                external_apps[app_name]["enabled"] = value.lower() == "true"
                            elif attribute == "alias":
                                external_apps[app_name]["alias"] = value
                            elif attribute == "icon":
                                external_apps[app_name]["icon"] = value
                            elif attribute == "url":
                                # Support multiple .url labels - store as list
                                if "urls" not in external_apps[app_name]:
                                    external_apps[app_name]["urls"] = []
                                external_apps[app_name]["urls"].append(value)
                            elif attribute == "admin":
                                external_apps[app_name]["is_admin"] = value.lower() == "true"
                            elif attribute == "category":
                                external_apps[app_name]["category"] = value
                            elif attribute == "description":
                                external_apps[app_name]["description"] = value
                                
            except docker.errors.NotFound:
                pass
    except Exception as e:
        print(f"Warning: Could not read traefik-home container labels: {e}", file=sys.stderr)
    
    return external_apps


def get_config_from_env_and_labels(docker_client: docker.DockerClient) -> Dict[str, Any]:
    """
    Get configuration from environment variables and traefik-home container labels.
    
    Args:
        docker_client: Docker client instance
        
    Returns:
        Dictionary with configuration values
    """
    config = {
        "page_title": os.getenv("PAGE_TITLE", "Traefik Home"),
        "custom_css_url": os.getenv("CUSTOM_CSS_URL", "/custom.css"),
        "custom_background_url": os.getenv("CUSTOM_BACKGROUND_URL", ""),
        "authentik_logout_url": os.getenv("AUTHENTIK_LOGOUT_URL", ""),
        "show_footer": os.getenv("SHOW_FOOTER", "true").lower() == "true",
        "show_status_dot": os.getenv("SHOW_STATUS_DOT", "true").lower() == "true",
        "open_in_new_tab": os.getenv("OPEN_IN_NEW_TAB", "false").lower() == "true",
        "sort_by": "default"
    }
    
    # Try to get traefik-home container labels
    try:
        current_container_id = os.getenv("HOSTNAME")
        if current_container_id:
            try:
                container = docker_client.containers.get(current_container_id)
                labels = container.labels
                
                # Override with container labels if present
                if "traefik-home.show-footer" in labels:
                    config["show_footer"] = labels["traefik-home.show-footer"].lower() == "true"
                if "traefik-home.show-status-dot" in labels:
                    config["show_status_dot"] = labels["traefik-home.show-status-dot"].lower() == "true"
                if "traefik-home.sort-by" in labels:
                    config["sort_by"] = labels["traefik-home.sort-by"]
                if "traefik-home.open-link-in-new-tab" in labels:
                    config["open_in_new_tab"] = labels["traefik-home.open-link-in-new-tab"].lower() == "true"
            except docker.errors.NotFound:
                pass
    except Exception as e:
        print(f"Warning: Could not read container labels: {e}", file=sys.stderr)
    
    return config


def load_template(template_path: str) -> Optional[str]:
    """
    Load template from file if it exists.
    
    Args:
        template_path: Path to template file
        
    Returns:
        Template content or None if not found
    """
    if os.path.exists(template_path):
        try:
            with open(template_path, 'r') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not load template from {template_path}: {e}", file=sys.stderr)
    return None


def get_default_client_html() -> str:
    """
    Get default client-side HTML template.
    
    Returns:
        HTML template string
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Traefik Home</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 2rem;
            font-size: 2.5rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .apps-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-top: 2rem;
        }
        .app-card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }
        .app-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.15);
        }
        .app-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .app-icon {
            font-size: 2rem;
        }
        .app-name {
            font-size: 1.25rem;
            font-weight: 600;
            color: #333;
            flex: 1;
        }
        .app-badge {
            background: #667eea;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .app-description {
            color: #666;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }
        .app-urls {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #eee;
        }
        .app-url {
            display: block;
            color: #667eea;
            text-decoration: none;
            font-size: 0.85rem;
            padding: 0.25rem 0;
            word-break: break-all;
        }
        .app-url:hover {
            text-decoration: underline;
        }
        .app-url.primary {
            font-weight: 600;
            font-size: 0.95rem;
        }
        .category-section {
            margin-bottom: 3rem;
        }
        .category-title {
            color: white;
            font-size: 1.5rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid rgba(255,255,255,0.3);
        }
        .error-message {
            background: #fee;
            color: #c33;
            padding: 1rem;
            border-radius: 8px;
            margin: 2rem 0;
            text-align: center;
        }
        .loading {
            color: white;
            text-align: center;
            font-size: 1.2rem;
            margin-top: 3rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 Traefik Home</h1>
        <div id="loading" class="loading">Loading apps...</div>
        <div id="error" class="error-message" style="display: none;"></div>
        <div id="apps-container"></div>
    </div>

    <script>
        // Escape HTML to prevent XSS
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Select preferred URL based on current hostname
        function selectPreferredUrl(urls) {
            if (!urls || urls.length === 0) return null;
            if (urls.length === 1) return urls[0];

            const currentHost = window.location.hostname;
            
            // Try to find URL with matching hostname
            for (const url of urls) {
                try {
                    const urlObj = new URL(url);
                    if (urlObj.hostname === currentHost || 
                        urlObj.hostname.endsWith('.' + currentHost) ||
                        currentHost.endsWith('.' + urlObj.hostname)) {
                        return url;
                    }
                } catch (e) {
                    console.warn('Invalid URL:', url, e);
                }
            }
            
            // Default to first URL
            return urls[0];
        }

        // Render apps
        function renderApps(apps) {
            const container = document.getElementById('apps-container');
            container.innerHTML = '';

            // Group by category
            const categories = {};
            apps.forEach(app => {
                const category = app.category || 'Apps';
                if (!categories[category]) {
                    categories[category] = [];
                }
                categories[category].push(app);
            });

            // Render each category
            Object.keys(categories).sort().forEach(category => {
                const section = document.createElement('div');
                section.className = 'category-section';

                const title = document.createElement('h2');
                title.className = 'category-title';
                title.textContent = category;
                section.appendChild(title);

                const grid = document.createElement('div');
                grid.className = 'apps-grid';

                categories[category].forEach(app => {
                    const card = document.createElement('div');
                    card.className = 'app-card';

                    // Select preferred URL
                    const preferredUrl = selectPreferredUrl(app.urls);
                    
                    if (preferredUrl) {
                        card.onclick = () => window.location.href = preferredUrl;
                    }

                    const header = document.createElement('div');
                    header.className = 'app-header';

                    if (app.icon) {
                        const icon = document.createElement('span');
                        icon.className = 'app-icon';
                        icon.textContent = app.icon;
                        header.appendChild(icon);
                    }

                    const name = document.createElement('div');
                    name.className = 'app-name';
                    name.textContent = app.name;
                    header.appendChild(name);

                    if (app.badge) {
                        const badge = document.createElement('span');
                        badge.className = 'app-badge';
                        badge.textContent = app.badge;
                        header.appendChild(badge);
                    }

                    card.appendChild(header);

                    if (app.description) {
                        const desc = document.createElement('div');
                        desc.className = 'app-description';
                        desc.textContent = app.description;
                        card.appendChild(desc);
                    }

                    // Show all URLs
                    if (app.urls && app.urls.length > 0) {
                        const urlsDiv = document.createElement('div');
                        urlsDiv.className = 'app-urls';

                        app.urls.forEach((url, idx) => {
                            const urlLink = document.createElement('a');
                            urlLink.className = 'app-url';
                            if (url === preferredUrl) {
                                urlLink.className += ' primary';
                            }
                            urlLink.href = url;
                            urlLink.textContent = url;
                            urlLink.onclick = (e) => e.stopPropagation();
                            urlsDiv.appendChild(urlLink);
                        });

                        card.appendChild(urlsDiv);
                    }

                    grid.appendChild(card);
                });

                section.appendChild(grid);
                container.appendChild(section);
            });
        }

        // Load apps
        fetch('/apps.json')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to load apps.json');
                }
                return response.json();
            })
            .then(data => {
                document.getElementById('loading').style.display = 'none';
                if (data.apps && data.apps.length > 0) {
                    renderApps(data.apps);
                } else {
                    document.getElementById('error').textContent = 'No apps found';
                    document.getElementById('error').style.display = 'block';
                }
            })
            .catch(error => {
                console.error('Error loading apps:', error);
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').textContent = 'Error loading apps: ' + error.message;
                document.getElementById('error').style.display = 'block';
            });
    </script>
</body>
</html>"""


def main():
    """Main entry point for the generator."""
    parser = argparse.ArgumentParser(description="Generate Traefik home page")
    parser.add_argument(
        "--output-dir",
        default="/usr/share/nginx/html",
        help="Output directory for generated files (default: /usr/share/nginx/html)"
    )
    parser.add_argument(
        "--overrides",
        default="/config/overrides.json",
        help="Path to overrides JSON file (default: /config/overrides.json)"
    )
    parser.add_argument(
        "--template",
        default="/app/templates/home-client.tmpl",
        help="Path to client HTML template (default: /app/templates/home-client.tmpl)"
    )
    parser.add_argument(
        "--traefik-api",
        default=None,
        help="Traefik API URL (default: auto-discover or TRAEFIK_API_URL env)"
    )
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Connect to Docker
    try:
        docker_client = docker.from_env()
    except Exception as e:
        print(f"Error: Could not connect to Docker: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Discover Traefik API endpoint
    traefik_api = args.traefik_api or discover_traefik_api()
    if traefik_api:
        print(f"Using Traefik API: {traefik_api}")
    else:
        print("Warning: Could not discover Traefik API - external apps from file provider may not be found")
    
    # Build service URL map (from Docker labels AND Traefik API)
    print("Building service URL map from Docker and Traefik API...")
    service_urls, service_metadata = build_service_url_map(docker_client, traefik_api)
    print(f"Found {len(service_urls)} services")
    
    # Get external apps from traefik-home container labels
    print("Reading external apps from traefik-home container labels...")
    external_apps = get_external_apps_from_labels(docker_client)
    print(f"Found {len(external_apps)} external apps")
    
    # Get configuration from environment and labels
    print("Reading configuration from environment and labels...")
    config = get_config_from_env_and_labels(docker_client)
    
    # Load overrides
    print(f"Loading overrides from {args.overrides}...")
    overrides = load_overrides(args.overrides)
    print(f"Loaded {len(overrides)} overrides")
    
    # Build app list
    print("Building app list...")
    apps = build_app_list(service_urls, service_metadata, overrides, external_apps)
    print(f"Generated {len(apps)} apps")
    
    # Debug output: print all apps found
    print("\n=== Apps List ===")
    for app in apps:
        first_url = app['urls'][0] if app['urls'] else 'no URL'
        print(f"  - {app['name']}: {first_url} (icon: {'yes' if app['icon'] else 'no'}, category: {app['category']})")
    print("=================\n")
    
    # Create apps.json with generation timestamp and config
    apps_data = {
        "_generated": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "apps": apps
    }
    
    # Write apps.json atomically
    apps_json_path = os.path.join(args.output_dir, "apps.json")
    print(f"Writing {apps_json_path}...")
    atomic_write(apps_json_path, json.dumps(apps_data, indent=2))
    
    # Load or use default client HTML template
    template_content = load_template(args.template)
    if template_content is None:
        print(f"Template not found at {args.template}, using default embedded template")
        template_content = get_default_client_html()
    else:
        print(f"Loaded template from {args.template}")
    
    # Write client HTML atomically
    html_path = os.path.join(args.output_dir, "home.html")
    print(f"Writing {html_path}...")
    atomic_write(html_path, template_content)
    
    # Also write to index.html for default serving
    index_path = os.path.join(args.output_dir, "index.html")
    print(f"Writing {index_path}...")
    atomic_write(index_path, template_content)
    
    print("Generation complete!")


if __name__ == "__main__":
    main()
