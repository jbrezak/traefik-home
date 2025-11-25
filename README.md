# Traefik Home with Authentik Integration

![preview](/doc/preview.jpg)

This is an enhanced version of [traefik-home](https://github.com/santimar/traefik-home) with added Authentik authentication, custom styling, and admin features.

## 🆚 What's Different from Original

| Feature | Original | This Version |
|---------|----------|--------------|
| Authentication | None | ✅ Authentik integration with user profiles |
| Styling | Basic Bootstrap | ✅ Modern frosted glass with Authentik theme |
| Dark Mode | Manual CSS | ✅ Automatic system-based dark mode |
| Admin Section | No | ✅ Collapsible admin-only tools |
| External Apps | Docker only | ✅ Support for non-Docker services |
| Custom Backgrounds | No | ✅ Environment-based backgrounds |
| Health Checks | No | ✅ Built-in Docker health monitoring |
| Configuration | Manual | ✅ Auto-generated nginx config |
| User Management | No | ✅ Per-user access control |

---

This tool creates a homepage for quickly accessing services hosted via the [Traefik reverse proxy](https://traefik.io/traefik/). This version is for Traefik V2 and V3 (for V1, see [here](https://github.com/lobre/traefik-home)).

Domains are automatically retrieved by reading Traefik labels. Only HTTP(S) routers are supported.

## ✨ New Features

- 🔐 **Authentik Integration** - User authentication with profile button and logout
- 🎨 **Custom Styling** - Authentik-inspired frosted glass design with dark mode support
- 🌓 **Auto Dark Mode** - Follows system dark mode preference
- 🔧 **Admin Section** - Collapsible admin-only tools section
- 🌐 **External Apps Support** - Show non-Docker apps from Traefik dynamic config
- 🖼️ **Custom Backgrounds** - Support for custom background images
- 📝 **Custom Page Title** - Configurable browser title
- 💚 **Health Checks** - Built-in Docker health monitoring
- 🔄 **Auto-configured** - Nginx configuration generated automatically

> [!IMPORTANT]  
> This tool assumes your Traefik endpoints are named `web` (HTTP) and `websecure` (HTTPS) in your [static configuration](https://doc.traefik.io/traefik/getting-started/configuration-overview/#the-static-configuration).
> 
> ```yaml
> entryPoints:
>   web:
>     address: ":80"
>   websecure:
>     address: ":443"
> ```

## Why This Tool

Traefik automatically configures itself by reading Docker Compose labels, allowing access to services via specified hostnames. While Traefik provides a dashboard, you still need to remember all hostnames. This tool creates a home page listing all services for easy access.

It uses [docker-gen](https://github.com/jwilder/docker-gen) to monitor Docker configuration changes and render a webpage served by nginx. Changes are reflected immediately.

## Quick Start

### Prerequisites

- Traefik v2 or v3 configured with Docker
- Authentik (optional, for authentication features)
- Docker and Docker Compose
- Python 3.11+ (for local development/testing)

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/jbrezak/traefik-home.git
cd traefik-home
```

2. **Build and deploy:**
```bash
docker-compose build
docker-compose up -d
```

That's it! The Python-based generator will automatically:
- Read Docker container labels to discover services
- Generate `apps.json` with full URL lists for each app
- Create the client-side HTML that selects the appropriate URL based on your current hostname
- Monitor Docker for changes and regenerate automatically

3. **Configure your environment (optional):**
   - Update domains in `docker-compose.yml`
   - Set environment variables (see [Configuration](#configuration) section)
   - Add container labels for advanced options
   - Mount custom CSS file if desired

## Docker Compose Configuration

```yaml
version: '3.8'

services:
  traefik-home:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: traefik-home
    volumes:
      # Docker socket for reading container labels
      - /var/run/docker.sock:/var/run/docker.sock:ro
      
      # Optional: Mount custom CSS
      - ./custom.css:/usr/share/nginx/html/custom.css:ro
      
      # Optional: Mount overrides for custom app metadata
      # - ./overrides.json:/config/overrides.json:ro
      
    environment:
      # Custom CSS file
      - CUSTOM_CSS_URL=/custom.css
      
      # Custom page title (optional)
      - PAGE_TITLE=My Services
      
      # Custom background image (optional)
      - CUSTOM_BACKGROUND_URL=
      
      # Authentik logout URL (optional)
      - AUTHENTIK_LOGOUT_URL=https://auth.example.com/flows/-/default/invalidation/
      
      # Display options
      - SHOW_FOOTER=true
      - SHOW_STATUS_DOT=true
      - OPEN_IN_NEW_TAB=false
      
    labels:
      # Traefik configuration
      - "traefik.enable=true"
      - "traefik.http.routers.traefik-home.rule=Host(`home.example.com`)"
      - "traefik.http.routers.traefik-home.entrypoints=websecure"
      - "traefik.http.routers.traefik-home.tls=true"
      - "traefik.http.services.traefik-home.loadbalancer.server.port=80"
      
      # Authentik forward auth middleware (optional)
      - "traefik.http.routers.traefik-home.middlewares=authentik@docker"
      
      # Container-specific configuration (optional)
      # - "traefik-home.show-footer=true"
      # - "traefik-home.show-status-dot=true"
      # - "traefik-home.sort-by=name"
      # - "traefik-home.open-link-in-new-tab=false"
      
    restart: unless-stopped
    networks:
      - traefik

networks:
  traefik:
    external: true
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CUSTOM_CSS_URL` | Path to custom CSS file | `/custom.css` |
| `PAGE_TITLE` | Browser page title | `Traefik Home` |
| `CUSTOM_BACKGROUND_URL` | URL or path to background image | _(none)_ |
| `AUTHENTIK_LOGOUT_URL` | Authentik logout endpoint | _(required for logout)_ |
| ~~`TRAEFIK_DYNAMIC_CONFIG`~~ | ~~Path to Traefik dynamic config YAML~~ | **OBSOLETE** |
| `SHOW_FOOTER` | Show footer with version info | `true` |
| `SHOW_STATUS_DOT` | Show container status indicators | `true` |
| `OPEN_IN_NEW_TAB` | Open service links in new tab | `false` |

> [!NOTE]
> `TRAEFIK_DYNAMIC_CONFIG` is obsolete. The new Python implementation reads all service information directly from Docker container labels, eliminating the need for external YAML configuration files.

## Container Labels Configuration

### Traefik-Home Container Labels

Configure the traefik-home container itself:

| Label | Description | Default |
|-------|-------------|---------|
| `traefik-home.show-footer` | Show footer on homepage | `true` |
| `traefik-home.show-status-dot` | Show status dots | `true` |
| `traefik-home.sort-by` | Sort order: `default` or `name` | `default` |
| `traefik-home.open-link-in-new-tab` | Open links in new tab | `false` |

### Service Container Labels

Configure individual services displayed on the homepage:

| Label | Description |
|-------|-------------|
| `traefik.enable=true` | **Required** - Enable service on homepage |
| `traefik.http.routers.<service>.rule` | Domain and path for the service |
| `traefik.http.routers.<service>.entrypoints` | Must be `web` or `websecure` |
| `traefik-home.icon=<url>` | Icon URL for the service |
| `traefik-home.alias=<name>` | Display name (instead of container name) |
| `traefik-home.hide=true` | Hide from homepage |
| `traefik-home.admin=true` | **New!** Show only to admin users |

### External App Labels (on traefik-home container)

Override or configure external apps from Traefik dynamic config:

| Label | Description |
|-------|-------------|
| `traefik-home.app.<service>.enable=true/false` | Enable/disable external app |
| `traefik-home.app.<service>.alias=<name>` | Display name for app |
| `traefik-home.app.<service>.icon=<url>` | Icon URL for app |
| `traefik-home.app.<service>.admin=true` | Mark as admin-only app |

### Example Service Configuration

**Regular Service:**
```yaml
whoami:
  image: traefik/whoami:latest
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.whoami.rule=Host(`whoami.example.com`)"
    - "traefik.http.routers.whoami.entrypoints=websecure"
    - "traefik.http.services.whoami.loadbalancer.server.port=80"
    - "traefik-home.icon=https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/traefik.png"
    - "traefik-home.alias=Who Am I"
```

**Admin-Only Service:**
```yaml
portainer:
  image: portainer/portainer-ce:latest
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.portainer.rule=Host(`portainer.example.com`)"
    - "traefik.http.routers.portainer.entrypoints=websecure"
    - "traefik-home.icon=https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/portainer.png"
    - "traefik-home.alias=Container Management"
    - "traefik-home.admin=true"  # Only admins will see this
```

## Authentik Configuration

### 1. Create Forward Auth Provider

In Authentik:
1. Go to **Applications** → **Providers** → **Create**
2. Select **Forward auth (single application)**
3. Name: `Traefik Forward Auth`
4. External host: `https://home.example.com`
5. Under **Advanced protocol settings**, enable:
   - Send HTTP-Basic Authentication
   - Send user attributes

### 2. Configure Response Headers

Add these headers in your Authentik provider or middleware:

```yaml
authResponseHeaders:
  - X-authentik-username
  - X-authentik-email
  - X-authentik-name
  - X-authentik-is-admin  # For admin section
```

### 3. Traefik Middleware

Create an Authentik middleware in Traefik:

```yaml
http:
  middlewares:
    authentik:
      forwardAuth:
        address: http://authentik:9000/outpost.goauthentik.io/auth/traefik
        trustForwardHeader: true
        authResponseHeaders:
          - X-authentik-username
          - X-authentik-email
          - X-authentik-name
          - X-authentik-is-admin
```

### 4. Get Logout URL

For Authentik Forward Auth (Proxy Provider), use the invalidation flow:
```
https://auth.example.com/flows/-/default/invalidation/
```

Or if using a custom flow:
```
https://auth.example.com/flows/<flow-slug>/invalidation/
```

This URL clears the Authentik session and redirects the user appropriately.

## External Apps (Non-Docker Services)

The Python-based generator supports adding external (non-Docker) apps via an `overrides.json` configuration file. This replaces the old YAML-based approach.

### Setup

1. **Create an overrides.json file:**
```json
{
  "openmediavault": {
    "Name": "OpenMediaVault",
    "Icon": "🗄️",
    "Description": "Network Attached Storage",
    "Category": "Infrastructure",
    "Badge": "NAS",
    "URLs": ["https://omv.example.com", "http://192.168.0.20:8085"],
    "Enable": true
  },
  "rclone": {
    "Name": "Rclone WebUI",
    "Icon": "☁️",
    "Description": "Cloud Storage Management",
    "Category": "Tools",
    "URLs": ["https://rclone.example.com"],
    "Enable": true
  }
}
```

2. **Mount the overrides file in docker-compose.yml:**
```yaml
services:
  traefik-home:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./overrides.json:/config/overrides.json:ro
```

3. **The generator automatically includes override entries** in the generated apps.json

### Override Configuration Options

| Field | Description | Required |
|-------|-------------|----------|
| `Name` | Display name for the app | Yes |
| `URLs` | Array of URLs for the app | Yes |
| `Icon` | Emoji or URL for app icon | No |
| `Description` | App description text | No |
| `Category` | Category for grouping | No (default: "Apps") |
| `Badge` | Badge text (e.g., "BETA", "NEW") | No |
| `Enable` | Show/hide the app | No (default: true) |
| `Hide` | Alternative to `Enable: false` | No |
| `Disable` | Disable app entry | No |

### Modifying Docker Apps

You can also use overrides.json to customize Docker-discovered apps:

```json
{
  "portainer": {
    "Name": "Portainer",
    "Icon": "🐳",
    "Category": "Admin",
    "Badge": "ADMIN",
    "Description": "Docker Management UI"
  }
}
```

The service name must match the Docker Compose service name.

### How It Works

```
Docker Containers (Labels) + overrides.json
          ↓
Python Generator (app/generate_page.py)
          ├─ Reads Docker labels
          ├─ Loads overrides.json
          ├─ Merges configuration
          └─ Generates apps.json
               ↓
Client-Side JavaScript
          ├─ Loads apps.json
          ├─ Selects preferred URL
          └─ Renders all apps
```

### Notes

- Override-only entries (not in Docker) are included if `Enable` is not explicitly `false`
- Docker-discovered apps can have their metadata overridden
- Multiple URLs per app are supported
- The client-side JS selects the best URL based on current hostname
- All apps use the same rendering and filtering logic

### Example Complete Setup

See the `Complete Docker Compose with External Apps` artifact for a full working example including:
- OpenMediaVault NAS
- Rclone WebUI
- pfSense firewall (admin-only)
- Proxmox VE (admin-only)
- Home Assistant
- Router admin page

## Features

### User Authentication

- **User Button**: Shows user initials in top-right corner
- **Dropdown Menu**: Displays username and logout option
- **Auto-detection**: Appears only when authenticated
- **Logout**: Redirects to Authentik logout endpoint

### Admin Section

- **Conditional Display**: Only visible to admin users
- **Collapsible**: Click to expand/collapse admin tools
- **Separate Services**: Admin-only apps don't appear in main list
- **Visual Indicator**: Red color scheme and "ADMIN ONLY" badge

### Dark Mode

- **System Detection**: Automatically follows OS dark mode setting
- **No Configuration**: Works out of the box
- **Instant Switching**: Updates when system preference changes
- **Custom Styling**: Both light and dark themes included

### Custom Styling

The included `custom.css` provides:
- Frosted glass effects (blur, transparency)
- Gradient backgrounds
- Smooth animations and transitions
- Hover effects
- Modern card-based design

### Health Monitoring

Built-in health check ensures the container is functioning:

```bash
# Check health status
docker ps

# View detailed health info
docker inspect traefik-home --format='{{json .State.Health}}' | jq

# Manual health check
curl http://localhost/health
```

## Customization

### Custom Background

**Option 1: External URL**
```yaml
environment:
  - CUSTOM_BACKGROUND_URL=https://images.unsplash.com/photo-1557683316-973673baf926?w=1920
```

**Option 2: Local File**
```yaml
volumes:
  - ./my-background.jpg:/usr/share/nginx/html/backgrounds/bg.jpg:ro
environment:
  - CUSTOM_BACKGROUND_URL=/backgrounds/bg.jpg
```

### Custom Page Title

```yaml
environment:
  - PAGE_TITLE=My Homelab Dashboard
```

### Modify Styling

Edit `custom.css` to customize:
- Colors and gradients
- Blur effects
- Card styles
- Spacing and layouts

### Self-Hosted Icons

Mount icons to nginx:

```yaml
volumes:
  - ./icons:/usr/share/nginx/html/icons:ro
```

Then reference in service labels:
```yaml
- "traefik-home.icon=http://home.example.com/icons/my-icon.png"
```

## Troubleshooting

### Services Not Appearing

1. **Check Docker labels:**
```bash
# Inspect container labels
docker inspect <container-name> | grep traefik

# View generator logs
docker logs traefik-home | grep "Found.*services"
```

2. **Verify Traefik router rules:**
   - Must have `traefik.enable=true`
   - Must have `traefik.http.routers.<name>.rule` with Host()
   - Router name should not contain "redirect"

3. **Test generator manually:**
```bash
docker exec traefik-home python3 /app/generate_page.py --output-dir /tmp/test
docker exec traefik-home cat /tmp/test/apps.json
```

### External Apps Not Showing

1. **Verify overrides.json is mounted and valid:**
```bash
docker exec traefik-home cat /config/overrides.json
docker exec traefik-home python3 -c "import json; print(json.load(open('/config/overrides.json')))"
```

2. **Check logs for parsing errors:**
```bash
docker logs traefik-home | grep -i "override\|error"
```

3. **Ensure `Enable` is true or not set to false**

### Configuration Not Applied

1. **Verify environment variables:**
```bash
docker exec traefik-home env | grep -E "PAGE_TITLE|CUSTOM_CSS|SHOW_"
```

2. **Check apps.json config section:**
```bash
docker exec traefik-home cat /usr/share/nginx/html/apps.json | grep -A10 '"config"'
```

3. **Check browser console for JavaScript errors:**
   - Open Developer Tools → Console
   - Look for errors loading apps.json

### Container Issues

```bash
# Check container status
docker ps -a | grep traefik-home

# View full logs
docker logs traefik-home

# Test Python generator
docker exec traefik-home python3 /app/generate_page.py --help

# Check docker-gen process
docker exec traefik-home ps aux | grep docker-gen
```

### Generation Errors

If apps.json is not being updated:

1. **Check Docker socket access:**
```bash
docker exec traefik-home ls -l /var/run/docker.sock
```

2. **Manually trigger generation:**
```bash
docker exec traefik-home python3 /app/generate_page.py
```

3. **Check file permissions:**
```bash
docker exec traefik-home ls -l /usr/share/nginx/html/
```

## Multiple Domains/Paths

Traefik allows complex rules like:
```
Host(`example.org`) && PathPrefix(`/path`) || Host(`domain.com`)
```

**Note**: Traefik-Home uses only the **first** `Host` and `Path/PathPrefix` found.

For predictable results, structure rules like:
```
Host(`domain.com`) && PathPrefix(`/path`) || Host(`example.org`) && PathPrefix(`/`)
```

## Updates

To update:

```bash
# Rebuild the custom image
docker-compose build --no-cache

# Restart the container
docker-compose up -d traefik-home
```

For major updates, check the changelog and update all files (template, CSS, entrypoint).

## Testing and Development

### Running Tests

The project includes comprehensive pytest test suite covering:
- Atomic write functionality
- Traefik rule parsing
- URL map building from Docker labels
- App list generation
- CLI integration

**Run tests locally:**

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app.generate_page --cov-report=html
```

All 35 tests must pass before merging changes.

### Local Development

**Generate page locally without Docker:**

```bash
# Run the generator (requires Docker socket access)
python3 app/generate_page.py --output-dir ./output --overrides ./overrides.json

# View generated files
cat ./output/apps.json
cat ./output/index.html
```

**Test with custom configuration:**

Create an `overrides.json` file:
```json
{
  "myapp": {
    "Name": "My Custom App",
    "Icon": "🚀",
    "Description": "Custom application",
    "Category": "Tools",
    "Badge": "NEW",
    "Hide": false,
    "Disable": false
  }
}
```

**Build Docker image:**

```bash
# Build production image
docker build -t traefik-home:latest .

# Build with specific Python version
docker build --build-arg PYTHON_VERSION=3.11 -t traefik-home:dev .

# Test the image
docker run -v /var/run/docker.sock:/var/run/docker.sock:ro traefik-home:latest
```

### Continuous Integration

GitHub Actions automatically runs tests on:
- Push to master branch
- Pull requests to master branch

See `.github/workflows/pytest.yml` for CI configuration.

## Architecture

```
Docker Containers (with Traefik labels)
    ↓
Python Generator (app/generate_page.py)
    ├─ Reads Docker socket
    ├─ Parses Traefik router rules
    ├─ Reads environment variables & container labels
    └─ Generates apps.json + HTML
        ↓
Client-Side JavaScript
    ├─ Fetches apps.json
    ├─ Selects preferred URL (based on window.location.hostname)
    ├─ Applies configuration (theme, layout, behavior)
    └─ Renders dynamic UI
        ↓
User sees homepage with all services
```

**Key Components:**
- **Python Generator**: Reads Docker labels and generates static files
- **docker-gen**: Monitors Docker changes and triggers regeneration
- **Client-Side JS**: Selects appropriate URL and applies config at runtime
- **Nginx**: Serves static files (apps.json and HTML)
- **Traefik**: Routes traffic and optionally handles authentication

## File Structure

```
traefik-home/
├── docker-compose.yml          # Docker Compose configuration
├── Dockerfile                  # Production Docker image (Python-based)
├── requirements.txt            # Python dependencies
├── app/
│   ├── generate_page.py        # Main Python generator
│   ├── entrypoint.sh           # Container entrypoint
│   └── templates/
│       ├── home-client.tmpl    # Client-side HTML template
│       ├── trigger.tmpl        # docker-gen trigger template
│       └── home.tmpl           # Compatibility placeholder
├── tests/
│   ├── test_generate_page.py  # Unit tests for generator
│   ├── test_cli_integration.py # Integration tests
│   └── test_atomic_write.py    # Atomic write tests
├── .github/
│   └── workflows/
│       └── pytest.yml          # CI/CD workflow
├── sample/
│   ├── custom.css              # Example custom styling
│   └── original.css            # Original styling reference
└── README.md                   # This file
```

## Credits

Based on [santimar/traefik-home](https://github.com/santimar/traefik-home), originally forked from [lobre/traefik-home](https://github.com/lobre/traefik-home).

Enhanced with:
- Authentik integration
- Admin section
- External apps support (non-Docker services)
- Custom styling
- Dark mode support
- Health checks
- Auto-configuration

## License

Same as the original traefik-home project.

## Support

For issues related to:
- **Original traefik-home**: [santimar/traefik-home](https://github.com/santimar/traefik-home)
- **Authentik**: [goauthentik.io](https://goauthentik.io/docs/)
- **Traefik**: [doc.traefik.io](https://doc.traefik.io/)
- **This enhanced version**: Check the documentation in this repository

---

## Quick Reference

### Common Commands

```bash
# Build and start
docker-compose build && docker-compose up -d

# View logs
docker logs -f traefik-home

# Check health
docker inspect traefik-home --format='{{.State.Health.Status}}'

# Restart
docker-compose restart traefik-home

# Rebuild after changes
docker-compose build --no-cache traefik-home
docker-compose up -d traefik-home
```

### Label Quick Reference

**Docker Services:**
```yaml
labels:
  - "traefik.enable=true"                                    # Required
  - "traefik.http.routers.service.rule=Host(`example.com`)" # Required
  - "traefik-home.icon=https://url/to/icon"                 # Optional
  - "traefik-home.alias=Friendly Name"                      # Optional
  - "traefik-home.admin=true"                               # Admin-only
  - "traefik-home.hide=true"                                # Hide from list
```

**External Apps (on traefik-home container):**
```yaml
labels:
  - "traefik-home.app.service.enable=true"
  - "traefik-home.app.service.alias=Display Name"
  - "traefik-home.app.service.icon=https://url/to/icon"
  - "traefik-home.app.service.admin=true"
```

### Environment Variables Quick Reference

```yaml
environment:
  - PAGE_TITLE=My Dashboard
  - CUSTOM_CSS_URL=/custom.css
  - CUSTOM_BACKGROUND_URL=https://example.com/bg.jpg
  - AUTHENTIK_LOGOUT_URL=https://auth.example.com/flows/-/default/invalidation/
  - SHOW_FOOTER=true
  - SHOW_STATUS_DOT=true
  - OPEN_IN_NEW_TAB=false
```

### File Locations

```
Build-time (copied into image):
  - Dockerfile:      ./Dockerfile
  - Generator:       ./app/generate_page.py → /app/generate_page.py
  - Entrypoint:      ./app/entrypoint.sh → /app/entrypoint.sh
  - Templates:       ./app/templates/ → /app/templates/
  - Requirements:    ./requirements.txt
  - Tests:           ./tests/ (not included in image)

Runtime (mounted or auto-generated):
  - Docker Socket:   /var/run/docker.sock (read-only)
  - Custom CSS:      ./custom.css → /usr/share/nginx/html/custom.css (optional)
  - Overrides:       ./overrides.json → /config/overrides.json (optional)
  - Apps JSON:       /usr/share/nginx/html/apps.json (auto-generated)
  - HTML Output:     /usr/share/nginx/html/index.html (auto-generated)
  - Health Check:    http://localhost/health
```

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Services not appearing | Check `traefik.enable=true` label and Traefik router configuration |
| External apps missing | Verify `overrides.json` is mounted and has valid JSON |
| Configuration not applied | Check environment variables and container labels |
| apps.json not updating | Verify Docker socket access and check logs |
| Container unhealthy | Check Python generator and docker-gen processes |
| Client-side errors | Open browser console to see JavaScript errors |

---

**Made with ❤️ for the homelab community**