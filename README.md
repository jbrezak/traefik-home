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
- (Optional) Traefik dynamic configuration for external apps

### Installation

1. **Clone or create your setup directory:**
```bash
mkdir -p traefik-home/app traefik-home/sample
cd traefik-home
```

2. **Create required files:**
   - `docker-compose.yml`
   - `Dockerfile`
   - `app/docker-entrypoint.sh`
   - `app/parse-external-apps.sh`
   - `app/home.tmpl`
   - `sample/custom.css` (optional - for reference)
   - `sample/rules.yml` (optional - for external apps)

3. **Make scripts executable:**
```bash
chmod +x app/docker-entrypoint.sh app/parse-external-apps.sh
```

4. **Configure your environment:**
   - Update domains in `docker-compose.yml`
   - Set your Authentik logout URL
   - (Optional) Copy and customize `sample/custom.css` then mount it

5. **Build and deploy:**
```bash
docker-compose build
docker-compose up -d
```

## Docker Compose Configuration

```yaml
version: '3.8'

services:
  traefik-home:
    build:
      context: .
      dockerfile: Dockerfile.custom
    container_name: traefik-home
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./custom.css:/usr/share/nginx/html/custom.css:ro
      - ./home.tmpl:/app/home.tmpl:ro
      
    environment:
      # Custom CSS file
      - CUSTOM_CSS_URL=/custom.css
      
      # Custom page title (optional)
      - PAGE_TITLE=My Services
      
      # Custom background image (optional)
      - CUSTOM_BACKGROUND_URL=
      
      # Authentik logout URL
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
      
      # Authentik forward auth middleware
      - "traefik.http.routers.traefik-home.middlewares=authentik@docker"
      
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
| `TRAEFIK_DYNAMIC_CONFIG` | Path to Traefik dynamic config YAML | _(none)_ |
| `SHOW_FOOTER` | Show footer with version info | `true` |
| `SHOW_STATUS_DOT` | Show container status indicators | `true` |
| `OPEN_IN_NEW_TAB` | Open service links in new tab | `false` |

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

Traefik-Home can display services defined in Traefik's dynamic configuration files, not just Docker containers.

### Setup

1. **Mount your Traefik dynamic config:**
```yaml
volumes:
  - /etc/traefik/dynamic:/etc/traefik/dynamic:ro
```

2. **Set environment variable:**
```yaml
environment:
  - TRAEFIK_DYNAMIC_CONFIG=/etc/traefik/dynamic/rules.yml
```

3. **Define services in Traefik config:**
```yaml
# /etc/traefik/dynamic/rules.yml
http:
  routers:
    omv:
      entryPoints:
        - websecure
      rule: "Host(`omv.example.com`)"
      service: omv
    
    rclone:
      entryPoints:
        - web
      rule: "Host(`rclone.example.com`)"
      service: rclone

  services:
    omv:
      loadBalancer:
        servers:
          - url: "http://192.168.0.20:8085"
    
    rclone:
      loadBalancer:
        servers:
          - url: "http://192.168.0.20:5572"
```

### Customize External Apps

Add labels to the traefik-home container to override external app properties:

```yaml
traefik-home:
  labels:
    # ... other labels ...
    
    # Configure OpenMediaVault
    - "traefik-home.app.omv.enable=true"
    - "traefik-home.app.omv.alias=OpenMediaVault"
    - "traefik-home.app.omv.icon=https://www.openmediavault.org/favicon.ico"
    
    # Configure Rclone (admin only)
    - "traefik-home.app.rclone.enable=true"
    - "traefik-home.app.rclone.alias=Rclone WebUI"
    - "traefik-home.app.rclone.icon=https://rclone.org/img/logo_on_light__horizontal_color.svg"
    - "traefik-home.app.rclone.admin=true"
    
    # Disable an external app
    - "traefik-home.app.router.enable=false"
```

**Note:** The template extracts these labels and passes them to the parser automatically - no environment variables needed!

### How It Works

1. **Parser script** reads the Traefik dynamic YAML file
2. **Extracts routers** and their associated services
3. **Builds URLs** from router rules and service backends
4. **Applies label overrides** from traefik-home container
5. **Renders cards** alongside Docker-based services

### External App Flow

```
Traefik Dynamic Config (rules.yml)
         ↓
parse-external-apps.sh (parses YAML with yq)
         ↓
JSON array of external apps
         ↓
Injected into HTML via JavaScript
         ↓
Rendered alongside Docker containers
```

### Notes

- External apps are marked internally as `External: true`
- They always show as "running" (status dot green)
- Sorting applies to both Docker and external apps
- Admin filtering works the same way
- Service name in labels must match router name in config
- Requires `yq` tool (included in Docker image)

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

### User Button Not Appearing

1. Verify Authentik headers are being sent:
```bash
curl -H "X-authentik-username: Test User" http://localhost/api/user-info
```

2. Check Traefik middleware is attached
3. Verify browser console for errors

### Admin Section Not Showing

1. Confirm `X-authentik-is-admin: true` header is sent
2. Check Authentik user has admin/superuser status
3. Verify service has `traefik-home.admin=true` label

### Container Unhealthy

```bash
# Check nginx status
docker exec traefik-home ps aux | grep nginx

# Test health endpoint
docker exec traefik-home curl -f http://localhost/health

# View logs
docker logs traefik-home
```

### External Apps Not Showing

1. Verify dynamic config file exists and is mounted
2. Check `TRAEFIK_DYNAMIC_CONFIG` environment variable is set correctly
3. Ensure YAML is valid: `yq eval . /etc/traefik/dynamic/rules.yml`
4. Check logs for parsing errors: `docker logs traefik-home | grep "external app"`
5. Verify router names match between config and labels

### Template Errors

If you see template parsing errors:
1. Ensure `home.tmpl` uses correct syntax: `{{$.Env.VARIABLE}}`
2. Check docker-gen is running: `docker logs traefik-home | grep docker-gen`
3. Verify all environment variables are set

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

## Architecture

```
User Request
    ↓
Traefik (Forward Auth)
    ↓
Authentik (Validates Session)
    ↓ (Returns Headers)
Traefik → Traefik-Home
    ↓
Nginx (Serves Page + API Endpoint)
    ↓
JavaScript (Fetches User Info)
    ↓
Displays Services + Admin Section (if admin)
```

## File Structure

```
traefik-home/
├── docker-compose.yml          # Main configuration
├── Dockerfile                  # Custom Docker image
├── app/
│   ├── docker-entrypoint.sh    # Auto-configures nginx
│   ├── parse-external-apps.sh  # Parses Traefik dynamic config
│   └── home.tmpl               # Page template
├── sample/
│   ├── custom.css              # Example styling (copy to customize)
│   └── rules.yml               # Example Traefik external services
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
  - TRAEFIK_DYNAMIC_CONFIG=/etc/traefik/dynamic/rules.yml
  - SHOW_FOOTER=true
  - SHOW_STATUS_DOT=true
  - OPEN_IN_NEW_TAB=false
```

### File Locations

```
Build-time (copied into image):
  - Dockerfile:      ./Dockerfile
  - Entrypoint:      ./app/docker-entrypoint.sh → /app/docker-entrypoint.sh
  - Parser:          ./app/parse-external-apps.sh → /app/parse-external-apps.sh
  - Template:        ./app/home.tmpl → /app/home.tmpl
  - Sample CSS:      ./sample/custom.css (reference only)
  - Sample Rules:    ./sample/rules.yml (reference only)

Runtime (mounted or auto-generated):
  - Custom CSS:      ./custom.css → /usr/share/nginx/html/custom.css (if mounted)
  - Traefik Rules:   /etc/traefik/dynamic/rules.yml (host) → /etc/traefik/dynamic/rules.yml (container)
  - Nginx Config:    /etc/nginx/conf.d/default.conf (auto-generated)
  - HTML Output:     /usr/share/nginx/html/index.html
  - Health Check:    http://localhost/health
  - User API:        http://localhost/api/user-info
```

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| User button not showing | Check Authentik headers in `/api/user-info` |
| External apps missing | Verify `TRAEFIK_DYNAMIC_CONFIG` path and YAML syntax |
| Admin section hidden | Ensure `X-authentik-is-admin: true` header is sent |
| Template errors | Check syntax: `{{$.Env.VARIABLE}}` not `{{getenv}}` |
| Container unhealthy | Test: `curl http://localhost/health` |
| Services not appearing | Check `traefik.enable=true` label |

---

**Made with ❤️ for the homelab community**