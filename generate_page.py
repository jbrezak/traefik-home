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
    print("Error: Required dependencies not installed. Run: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


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


def build_service_url_map(docker_client: docker.DockerClient) -> Dict[str, List[str]]:
    """
    Build a map of service names to their URLs from Docker container labels.
    
    Args:
        docker_client: Docker client instance
        
    Returns:
        Dictionary mapping service names to list of URLs
    """
    service_urls = {}
    
    try:
        containers = docker_client.containers.list()
    except Exception as e:
        print(f"Warning: Could not list Docker containers: {e}", file=sys.stderr)
        return service_urls
    
    for container in containers:
        labels = container.labels
        
        # Find all Traefik HTTP routers
        for key, value in labels.items():
            if key.startswith("traefik.http.routers.") and key.endswith(".rule"):
                # Extract router name
                parts = key.split(".")
                if len(parts) >= 4:
                    router_name = parts[3]
                    
                    # Skip routers with "redirect" in the name (HTTP->HTTPS redirects)
                    if "redirect" in router_name.lower():
                        continue
                    
                    # Parse Host() or HostRegexp() rules
                    urls = parse_traefik_rule(value)
                    
                    # Get service name from compose project and service
                    service_name = labels.get("com.docker.compose.service", container.name)
                    
                    if urls and service_name:
                        if service_name not in service_urls:
                            service_urls[service_name] = []
                        service_urls[service_name].extend(urls)
    
    # Remove duplicates while preserving order
    for service_name in service_urls:
        seen = set()
        unique_urls = []
        for url in service_urls[service_name]:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        service_urls[service_name] = unique_urls
    
    return service_urls


def parse_traefik_rule(rule: str) -> List[str]:
    """
    Parse Traefik rule to extract hostnames.
    
    Args:
        rule: Traefik rule string (e.g., "Host(`example.com`) || Host(`www.example.com`)")
        
    Returns:
        List of URLs (with https:// prefix)
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
                # Build full URL (assume HTTPS)
                urls.append(f"https://{host}")
        
        # Extract HostRegexp() patterns
        elif "HostRegexp(" in part:
            start = part.find("HostRegexp(") + 11
            end = part.find(")", start)
            if end > start:
                host = part[start:end].strip("`").strip("'").strip('"')
                # For regexp, take as-is but may need cleanup
                host = host.replace("{", "").replace("}", "").split(",")[0].strip()
                urls.append(f"https://{host}")
    
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
    overrides: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Build final app list with all URLs and metadata.
    
    Args:
        service_urls: Map of service names to URLs
        overrides: Override configuration
        
    Returns:
        List of app dictionaries
    """
    apps = []
    
    # Process services from Docker
    for service_name, urls in service_urls.items():
        override = overrides.get(service_name, {})
        
        # Check if app should be hidden
        if override.get("Hide", False):
            continue
        
        # Check if enabled (default to True for Docker services)
        if not override.get("Enable", True):
            continue
        
        app = {
            "name": override.get("Name", service_name.replace("-", " ").title()),
            "urls": urls,  # Include ALL URLs, no filtering
            "icon": override.get("Icon", ""),
            "description": override.get("Description", ""),
            "category": override.get("Category", "Apps"),
            "badge": override.get("Badge", ""),
            "primary_url": urls[0] if urls else "",  # First URL as primary
        }
        apps.append(app)
    
    # Process override-only entries (apps not in Docker but defined in overrides)
    for service_name, override in overrides.items():
        if service_name not in service_urls:
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
                "primary_url": urls[0],
            }
            apps.append(app)
    
    # Sort by name
    apps.sort(key=lambda x: x["name"])
    
    return apps


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
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Connect to Docker
    try:
        docker_client = docker.from_env()
    except Exception as e:
        print(f"Error: Could not connect to Docker: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Build service URL map
    print("Building service URL map from Docker...")
    service_urls = build_service_url_map(docker_client)
    print(f"Found {len(service_urls)} services")
    
    # Load overrides
    print(f"Loading overrides from {args.overrides}...")
    overrides = load_overrides(args.overrides)
    print(f"Loaded {len(overrides)} overrides")
    
    # Build app list
    print("Building app list...")
    apps = build_app_list(service_urls, overrides)
    print(f"Generated {len(apps)} apps")
    
    # Create apps.json with generation timestamp
    apps_data = {
        "_generated": datetime.now(timezone.utc).isoformat(),
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
