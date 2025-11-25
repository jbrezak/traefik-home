#!/usr/bin/env python3
"""
traefik_home_apps_final.py

Same behavior as before, with an added verbose flag (--verbose / -v)
that prints diagnostic information to stderr about endpoint discovery,
Traefik queries, and why containers/services are included/excluded.

Usage:
  python traefik_home_apps_final.py [--api-url URL] [-v|--verbose]

Or in a container:
  docker run --rm \
    --name traefik-home-apps \
    --network proxy \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    -e TRAEFIK_API_URL="http://traefik:8080" \
    traefik-home-apps \
    --verbose

Dependencies:
  pip install docker requests
"""
from collections import defaultdict
import os
import re
import json
import sys
import traceback
import argparse

try:
    import docker
    import requests
except Exception:
    print("Missing dependencies. Please install: pip install docker requests", file=sys.stderr)
    raise

DEFAULT_TRAEFIK_API_PORT = 8080
LABEL_PREFIX_BASE = "traefik-home"
LABEL_PREFIX_APP = f"{LABEL_PREFIX_BASE}.app."
PER_CONTAINER_PREFIX = f"{LABEL_PREFIX_BASE}."
# support alias, icon, admin, enable, hide
APP_LABEL_RE = re.compile(r"^traefik-home\.app\.([^\.]+)\.(alias|icon|admin|enable|hide)$")
PER_CONTAINER_RE = re.compile(r"^traefik-home\.(alias|icon|admin|enable|hide)$")

HOST_RE = re.compile(r"Host\(\s*`([^`]+)`\s*\)")
HOSTREGEXP_RE = re.compile(r"HostRegexp\(\s*`([^`]+)`\s*\)")
PATHPREFIX_RE = re.compile(r"PathPrefix\(\s*`([^`]+)`\s*\)")
PATH_RE = re.compile(r"Path\(\s*`([^`]+)`\s*\)")

# Verbose control (set in main)
VERBOSE = False

def vprint(*args, **kwargs):
    """Verbose print to stderr when VERBOSE is True."""
    if VERBOSE:
        print(*args, file=sys.stderr, **kwargs)

# --- Traefik endpoint helpers ------------------------------------------------
def test_traefik_endpoint(base_url, timeout=2.0):
    if not base_url:
        return False
    base_url = base_url.rstrip("/")
    candidates = ["/api/http/routers", "/api/routers", "/api"]
    for p in candidates:
        try:
            url = f"{base_url}{p}"
            vprint(f"    testing {url} ...")
            resp = requests.get(url, timeout=timeout)
            vprint(f"      status: {getattr(resp, 'status_code', 'no-status')}")
            if resp.status_code == 200:
                return True
        except Exception as e:
            vprint(f"      error: {e}")
    return False

def find_traefik_container(docker_client):
    for c in docker_client.containers.list(all=True):
        try:
            name = c.name.lower()
            img = (c.image.tags[0] if c.image.tags else str(c.image)).lower()
        except Exception:
            name = ""
            img = ""
        if "traefik" in name or "traefik" in img:
            vprint(f"Found Traefik container: {c.name} ({c.id[:12]})")
            return c
    vprint("No Traefik container found by name/image heuristic")
    return None

def get_host_mapped_port(traefik_container, container_port=DEFAULT_TRAEFIK_API_PORT):
    try:
        ports = traefik_container.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
        mapping = ports.get(f"{container_port}/tcp")
        if mapping and isinstance(mapping, list) and mapping:
            host_port = mapping[0].get("HostPort")
            return host_port
    except Exception:
        pass
    return None

def get_traefik_internal_ip(traefik_container):
    try:
        nets = traefik_container.attrs.get("NetworkSettings", {}).get("Networks", {}) or {}
        for netname, nd in nets.items():
            ip = nd.get("IPAddress")
            if ip:
                return ip
    except Exception:
        pass
    return None

def discover_traefik_api(cli_api_url=None):
    """
    Discover a usable Traefik API endpoint using heuristics.
    Returns the working endpoint URL or None.

    Logging of attempts is performed via vprint.
    """
    tried = []

    # 1) explicit CLI override
    if cli_api_url:
        vprint(f"CLI API URL provided: {cli_api_url}")
        tried.append(("cli", cli_api_url))
        if test_traefik_endpoint(cli_api_url):
            vprint(f"Using CLI override: {cli_api_url}")
            return cli_api_url.rstrip("/")
        vprint(f"CLI override failed: {cli_api_url}")

    # 1b) env override
    env = os.environ.get("TRAEFIK_API_URL")
    if env:
        vprint(f"Env TRAEFIK_API_URL provided: {env}")
        tried.append(("env", env))
        if test_traefik_endpoint(env):
            vprint(f"Using TRAEFIK_API_URL env: {env}")
            return env.rstrip("/")
        vprint(f"Env override failed: {env}")

    # Docker client may not be available if socket not mounted
    try:
        client = docker.from_env()
    except Exception as e:
        vprint(f"docker.from_env() failed: {e}")
        client = None

    # 2) Try container DNS name (works when running in same Docker network)
    try_dns = f"http://traefik:{DEFAULT_TRAEFIK_API_PORT}"
    vprint(f"Trying container DNS: {try_dns}")
    tried.append(("dns", try_dns))
    if test_traefik_endpoint(try_dns):
        vprint(f"Using container DNS endpoint: {try_dns}")
        return try_dns

    # 3) If docker client available, inspect traefik container for host port / internal ip
    if client:
        traefik_c = find_traefik_container(client)
        if traefik_c:
            host_port = get_host_mapped_port(traefik_c, DEFAULT_TRAEFIK_API_PORT)
            if host_port:
                candidate = f"http://127.0.0.1:{host_port}"
                vprint(f"Trying host-mapped port endpoint: {candidate}")
                tried.append(("host_mapped", candidate))
                if test_traefik_endpoint(candidate):
                    vprint(f"Using host-mapped endpoint: {candidate}")
                    return candidate
                vprint(f"Host-mapped endpoint failed: {candidate}")

            ip = get_traefik_internal_ip(traefik_c)
            if ip:
                candidate = f"http://{ip}:{DEFAULT_TRAEFIK_API_PORT}"
                vprint(f"Trying traefik internal IP endpoint: {candidate}")
                tried.append(("internal_ip", candidate))
                if test_traefik_endpoint(candidate):
                    vprint(f"Using traefik internal IP endpoint: {candidate}")
                    return candidate
                vprint(f"Traefik internal IP endpoint failed: {candidate}")
        else:
            vprint("No traefik container to inspect for host mapping/internal IP")

    # 4) host.docker.internal (useful on Docker Desktop)
    try_hd = f"http://host.docker.internal:{DEFAULT_TRAEFIK_API_PORT}"
    vprint(f"Trying host.docker.internal: {try_hd}")
    tried.append(("host.docker.internal", try_hd))
    if test_traefik_endpoint(try_hd):
        vprint(f"Using host.docker.internal endpoint: {try_hd}")
        return try_hd
    vprint("host.docker.internal failed (or not available)")

    vprint("All discovery attempts exhausted. Tried endpoints:")
    for t in tried:
        vprint(f"  - {t[0]}: {t[1]}")
    return None

# --- Traefik parsing ---------------------------------------------------------
def parse_rule_to_urls(rule, entrypoints):
    urls = set()
    if not rule:
        return []
    hosts = HOST_RE.findall(rule) + HOSTREGEXP_RE.findall(rule)
    if not hosts:
        return []
    path_match = PATHPREFIX_RE.search(rule) or PATH_RE.search(rule)
    path = path_match.group(1) if path_match else "/"
    if not path.startswith("/"):
        path = "/" + path
    schemes = set()
    if entrypoints:
        for ep in entrypoints:
            ep_low = ep.lower()
            if "secure" in ep_low or "https" in ep_low or "websecure" in ep_low:
                schemes.add("https")
            else:
                schemes.add("http")
    if not schemes:
        schemes = {"http"}
    for host in hosts:
        for s in schemes:
            p = path if path.endswith("/") else path + "/"
            urls.add(f"{s}://{host}{p}")
    return sorted(urls)

def build_service_url_map(traefik_api):
    """Query Traefik API and return mapping service->set(urls). Handles both dict and list responses."""
    service_to_urls = defaultdict(set)
    if not traefik_api:
        vprint("No traefik_api provided to build_service_url_map")
        return service_to_urls

    routers = None
    try:
        vprint(f"Querying Traefik for routers: {traefik_api.rstrip('/')}/api/http/routers")
        resp = requests.get(f"{traefik_api.rstrip('/')}/api/http/routers", timeout=5)
        resp.raise_for_status()
        routers = resp.json()
    except Exception as e:
        vprint(f"Primary routers endpoint failed: {e}; trying fallback")
        try:
            resp = requests.get(f"{traefik_api.rstrip('/')}/api/routers", timeout=5)
            resp.raise_for_status()
            routers = resp.json()
        except Exception as e2:
            vprint(f"Fallback routers endpoint failed: {e2}; no routers will be used")
            routers = None

    if not routers:
        return service_to_urls

    vprint(f"Traefik returned routers of type: {type(routers).__name__}")

    router_items = []
    if isinstance(routers, dict):
        router_items = list(routers.items())
    elif isinstance(routers, list):
        for item in routers:
            if not isinstance(item, dict):
                continue
            rname = item.get("name") or item.get("router") or ""
            router_items.append((rname, item))
    else:
        vprint("Unknown routers format; skipping router parsing")
        return service_to_urls

    skipped_router_entries = 0
    for rname, rdata in router_items:
        try:
            entrypoints = (rdata.get("entryPoints") or rdata.get("entrypoints") or []) if isinstance(rdata, dict) else []
            rule = (rdata.get("rule") or rdata.get("Rule") or "") if isinstance(rdata, dict) else ""
            service = (rdata.get("service") or rdata.get("Service") or "") if isinstance(rdata, dict) else ""
            urls = parse_rule_to_urls(rule, entrypoints)
            svc_norm = service.split("@")[0] if isinstance(service, str) else str(service)
            # Skip internal Traefik "router" artifacts
            if isinstance(svc_norm, str) and svc_norm.lower() == "router":
                vprint(f"Skipping router/service named 'router' (svc_norm): rname={rname}")
                skipped_router_entries += 1
                continue
            if isinstance(rname, str) and rname.lower() == "router":
                vprint(f"Skipping router entry rname='router'")
                skipped_router_entries += 1
                continue
            if not svc_norm and rname:
                svc_norm = rname.split(".")[-1]
            for u in urls:
                if svc_norm and isinstance(svc_norm, str) and svc_norm.lower() == "router":
                    continue
                service_to_urls[svc_norm].add(u)
                if rname and not (isinstance(rname, str) and rname.lower() == "router"):
                    service_to_urls[rname].add(u)
        except Exception:
            traceback.print_exc(file=sys.stderr)

    vprint(f"Parsed services -> URLs (count: {len(service_to_urls)}), skipped router entries: {skipped_router_entries}")
    return service_to_urls

# --- Overrides extraction ---------------------------------------------------
def find_override_container(docker_client):
    """
    Prefer container named 'traefik-home'. Else any container that contains labels starting with 'traefik-home.app.'.
    """
    try:
        for c in docker_client.containers.list(all=True):
            if c.name == "traefik-home":
                vprint("Found override container by exact name 'traefik-home'")
                return c
    except Exception:
        pass
    try:
        for c in docker_client.containers.list(all=True):
            if "traefik-home" in c.name:
                vprint(f"Found override container by name contains 'traefik-home': {c.name}")
                return c
    except Exception:
        pass
    try:
        for c in docker_client.containers.list(all=True):
            labels = c.attrs.get("Config", {}).get("Labels", {}) or {}
            if any(k.startswith(LABEL_PREFIX_APP) for k in labels.keys()):
                vprint(f"Found override container by labels: {c.name}")
                return c
    except Exception:
        pass
    vprint("No override container found")
    return None

def extract_overrides_from_container(container):
    """
    Return dict of overrides:
      { svc_name: { 'alias':..., 'icon':..., 'admin':..., 'enable':..., 'hide':... }, ... }
    """
    overrides = defaultdict(dict)
    if not container:
        return overrides
    labels = container.attrs.get("Config", {}).get("Labels", {}) or {}
    for k, v in labels.items():
        m = APP_LABEL_RE.match(k)
        if m:
            svc = m.group(1)
            prop = m.group(2)
            overrides[svc][prop] = v
            vprint(f"Override found: service={svc} {prop}={v}")
    return overrides

# --- Build final app list ---------------------------------------------------
def collect_per_container_labels(labels):
    """Collect per-container traefik-home.* labels into dict {alias,icon,admin,enable,hide}"""
    result = {}
    for k, v in labels.items():
        m = PER_CONTAINER_RE.match(k)
        if m:
            prop = m.group(1)
            result[prop] = v
            vprint(f"  per-container label: {k}={v}")
    return result

def match_urls_for_container(container_name, service_to_urls):
    """Heuristic: match service keys to container name to gather URLs"""
    urls = set()
    for svc_key, ulist in service_to_urls.items():
        if not svc_key:
            continue
        if container_name == svc_key or container_name in svc_key or svc_key in container_name or svc_key.startswith(container_name + "-") or container_name.startswith(svc_key + "-"):
            urls.update(ulist)
    return sorted(urls)

def str_is_true(val):
    return isinstance(val, str) and val.lower() == "true"

def build_app_list(docker_client, service_to_urls, overrides):
    """
    Inclusion rules:
      - Include container if it has any per-container label starting with 'traefik-home.' OR
      - container.name present in overrides (traefik-home.app.<name>.*)
    Also include "override-only" entries: services present in overrides but with no container found (unless hidden).
    Exclude any service/container named exactly 'router'.
    Exclude entries marked Hide=true.
    """
    results = []
    containers = docker_client.containers.list(all=True)

    # Map container name to container object for quick lookup
    name_to_container = {c.name: c for c in containers}

    vprint(f"Total containers inspected: {len(containers)}")
    # First: iterate containers and include those that meet inclusion criteria
    for c in containers:
        try:
            name = c.name
            if not isinstance(name, str):
                continue
            if name.lower() == "router":
                vprint(f"Skipping container with name 'router': {name}")
                continue

            labels = c.attrs.get("Config", {}).get("Labels", {}) or {}
            per_labels = collect_per_container_labels(labels)
            has_per_labels = bool(per_labels)
            has_override = name in overrides

            if not (has_per_labels or has_override):
                vprint(f"Skipping {name}: no per-container traefik-home labels and no overrides")
                continue

            # Running state
            state = c.attrs.get("State", {}) or {}
            running = state.get("Running", False)

            # Determine properties with precedence: per-container labels override traefik-home overrides
            alias = per_labels.get("alias") or overrides.get(name, {}).get("alias", "") or name
            icon = per_labels.get("icon") or overrides.get(name, {}).get("icon", "") or ""
            admin_raw = per_labels.get("admin") or overrides.get(name, {}).get("admin", "") or ""
            enable_raw = per_labels.get("enable") or overrides.get(name, {}).get("enable", "") or ""
            hide_raw = per_labels.get("hide") or overrides.get(name, {}).get("hide", "") or ""

            vprint(f"Including container {name}: alias='{alias}' admin='{admin_raw}' enable_raw='{enable_raw}' hide_raw='{hide_raw}'")

            # Normalize booleans: admin only "true"/"false" if explicit; enable defaults to "true" unless explicitly "false"
            admin = admin_raw.lower() if isinstance(admin_raw, str) else ""
            admin = admin if admin in ("true", "false") else ""
            if isinstance(enable_raw, str) and enable_raw.lower() == "false":
                enable = "false"
            else:
                enable = "true"
            hide = str_is_true(hide_raw)

            # If hide true -> omit entirely (hide from homepage)
            if hide:
                vprint(f"  Hiding {name} because hide=true")
                continue

            urls = match_urls_for_container(name, service_to_urls)
            vprint(f"  URLs matched for {name}: {urls}")

            obj = {
                "Name": name,
                "Alias": alias,
                "URLs": urls,
                "Icon": icon,
                "Admin": admin,
                "Enable": enable,
                "Hide": hide,
                "Running": bool(running),
            }
            results.append(obj)
        except Exception:
            traceback.print_exc(file=sys.stderr)

    # Second: include override-only services (present in overrides but no matching container included above)
    for svc, props in overrides.items():
        if not isinstance(svc, str):
            continue
        svc_l = svc.lower()
        if svc_l == "router":
            vprint(f"Skipping override-only service named 'router': {svc}")
            continue
        if any(r["Name"] == svc for r in results):
            vprint(f"Skipping override-only {svc}: already included")
            continue
        # If there is a container with this name but it wasn't included earlier, skip
        if svc in name_to_container:
            vprint(f"Skipping override-only {svc}: container exists but was not included earlier")
            continue
        hide_raw = props.get("hide", "")
        if str_is_true(hide_raw):
            vprint(f"Skipping override-only {svc}: hide=true in overrides")
            continue
        alias = props.get("alias", svc)
        icon = props.get("icon", "")
        admin_raw = props.get("admin", "")
        enable_raw = props.get("enable", "")
        admin = admin_raw.lower() if isinstance(admin_raw, str) else ""
        admin = admin if admin in ("true", "false") else ""
        if isinstance(enable_raw, str) and enable_raw.lower() == "false":
            enable = "false"
        else:
            enable = "true"
        urls = sorted(list(service_to_urls.get(svc, [])))
        vprint(f"Including override-only service {svc}: alias='{alias}' enable='{enable}' urls={urls}")
        obj = {
            "Name": svc,
            "Alias": alias,
            "URLs": urls,
            "Icon": icon,
            "Admin": admin,
            "Enable": enable,
            "Hide": False,
            "Running": False,
        }
        results.append(obj)

    vprint(f"Final app count: {len(results)}")
    return results

# --- Main -------------------------------------------------------------------
def main(argv=None):
    global VERBOSE
    parser = argparse.ArgumentParser(description="Generate traefik-home apps JSON")
    parser.add_argument("--api-url", help="Explicit Traefik API URL (overrides env/discovery)", default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug output")
    args = parser.parse_args(argv)

    VERBOSE = args.verbose

    traefik_api = discover_traefik_api(cli_api_url=args.api_url)
    if not traefik_api:
        print("ERROR: Could not discover a working Traefik API endpoint.", file=sys.stderr)
        print("Hints:", file=sys.stderr)
        print("- If running this script in a container, attach it to the same Docker network as Traefik (e.g. --network proxy) and/or set TRAEFIK_API_URL=http://traefik:8080 or pass --api-url", file=sys.stderr)
        print("- Ensure /var/run/docker.sock is mounted if the script needs to inspect containers", file=sys.stderr)
        sys.exit(2)

    vprint(f"Using Traefik API endpoint: {traefik_api}")

    # Docker client
    try:
        client = docker.from_env()
    except Exception as e:
        print("ERROR: could not create docker client:", e, file=sys.stderr)
        sys.exit(2)

    service_to_urls = build_service_url_map(traefik_api)

    # get overrides from traefik-home container (preferred) or any container that has traefik-home.app.* labels
    override_container = find_override_container(client)
    overrides = extract_overrides_from_container(override_container)

    apps = build_app_list(client, service_to_urls, overrides)

    print(json.dumps(apps, indent=2))

if __name__ == "__main__":
    main()
    
