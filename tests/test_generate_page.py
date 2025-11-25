#!/usr/bin/env python3
"""Tests for generate_page.py"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Mock docker and requests before importing generate_page
sys.modules['docker'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Add app directory to path to import generate_page
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
import generate_page


class TestAtomicWrite:
    """Tests for atomic_write function"""
    
    def test_atomic_write_creates_file(self, tmp_path):
        """Test that atomic_write creates a file with content"""
        filepath = tmp_path / "test.txt"
        content = "Hello, World!"
        
        generate_page.atomic_write(str(filepath), content)
        
        assert filepath.exists()
        assert filepath.read_text() == content
    
    def test_atomic_write_no_tmp_files_left(self, tmp_path):
        """Test that atomic_write doesn't leave temporary files"""
        filepath = tmp_path / "test.txt"
        content = "Test content"
        
        generate_page.atomic_write(str(filepath), content)
        
        # Check no .tmp files left
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0
        
        # Check no hidden temp files left
        hidden_files = [f for f in tmp_path.iterdir() if f.name.startswith('.')]
        assert len(hidden_files) == 0


class TestParseTraefikRule:
    """Tests for parse_traefik_rule function"""
    
    def test_parse_single_host(self):
        """Test parsing a single Host() rule"""
        rule = "Host(`example.com`)"
        urls = generate_page.parse_traefik_rule(rule)
        assert urls == ["http://example.com"]
    
    def test_parse_multiple_hosts(self):
        """Test parsing multiple Host() rules with OR"""
        rule = "Host(`example.com`) || Host(`www.example.com`)"
        urls = generate_page.parse_traefik_rule(rule)
        assert "http://example.com" in urls
        assert "http://www.example.com" in urls
    
    def test_parse_host_with_single_quotes(self):
        """Test parsing Host() with single quotes"""
        rule = "Host('example.com')"
        urls = generate_page.parse_traefik_rule(rule)
        assert urls == ["http://example.com"]
    
    def test_parse_empty_rule(self):
        """Test parsing empty rule"""
        rule = ""
        urls = generate_page.parse_traefik_rule(rule)
        assert urls == []


class TestBuildServiceUrlMap:
    """Tests for build_service_url_map function"""
    
    def test_build_service_url_map_basic(self):
        """Test building URL map from Docker containers"""
        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-service"
        mock_container.labels = {
            "traefik.http.routers.test.rule": "Host(`test.example.com`)",
            "com.docker.compose.service": "test-service"
        }
        mock_client.containers.list.return_value = [mock_container]
        
        result, metadata = generate_page.build_service_url_map(mock_client)
        
        assert "test-service" in result
        assert "http://test.example.com" in result["test-service"]
    
    def test_build_service_url_map_skips_redirects(self):
        """Test that redirect routers are skipped"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-service"
        mock_container.labels = {
            "traefik.http.routers.test-redirect.rule": "Host(`test.example.com`)",
            "traefik.http.routers.test.rule": "Host(`test.example.com`)",
            "com.docker.compose.service": "test-service"
        }
        mock_client.containers.list.return_value = [mock_container]
        
        result, metadata = generate_page.build_service_url_map(mock_client)
        
        # Should have one URL, not two (redirect should be skipped)
        assert len(result["test-service"]) == 1
    
    def test_build_service_url_map_removes_duplicates(self):
        """Test that duplicate URLs are removed"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-service"
        mock_container.labels = {
            "traefik.http.routers.test1.rule": "Host(`test.example.com`)",
            "traefik.http.routers.test2.rule": "Host(`test.example.com`)",
            "com.docker.compose.service": "test-service"
        }
        mock_client.containers.list.return_value = [mock_container]
        
        result, metadata = generate_page.build_service_url_map(mock_client)
        
        # Should have one unique URL
        assert len(result["test-service"]) == 1
        assert "http://test.example.com" in result["test-service"]


class TestBuildAppList:
    """Tests for build_app_list function"""
    
    def test_build_app_list_includes_all_urls(self):
        """Test that all URLs are included in app list (no host filtering)"""
        service_urls = {
            "test-service": [
                "http://test.example.com",
                "http://test.other.com",
                "http://test.local.com"
            ]
        }
        # Service must have traefik-home metadata to be included
        service_metadata = {
            "test-service": {"icon": "", "alias": "", "hide": False, "is_admin": False}
        }
        overrides = {}
        
        apps = generate_page.build_app_list(service_urls, service_metadata, overrides)
        
        assert len(apps) == 1
        app = apps[0]
        assert len(app["urls"]) == 3
        assert "http://test.example.com" in app["urls"]
        assert "http://test.other.com" in app["urls"]
        assert "http://test.local.com" in app["urls"]
    
    def test_build_app_list_enable_defaulting(self):
        """Test that Enable defaults to True for Docker services with traefik-home labels"""
        service_urls = {
            "test-service": ["http://test.example.com"]
        }
        # Service must have traefik-home metadata to be included
        service_metadata = {
            "test-service": {"icon": "", "alias": "", "hide": False, "is_admin": False}
        }
        overrides = {}
        
        apps = generate_page.build_app_list(service_urls, service_metadata, overrides)
        
        assert len(apps) == 1
    
    def test_build_app_list_hide_behavior(self):
        """Test that Hide=true removes app from list"""
        service_urls = {
            "test-service": ["http://test.example.com"]
        }
        # Service has traefik-home metadata with hide=True
        service_metadata = {
            "test-service": {"icon": "", "alias": "", "hide": True, "is_admin": False}
        }
        overrides = {}
        
        apps = generate_page.build_app_list(service_urls, service_metadata, overrides)
        
        assert len(apps) == 0
    
    def test_build_app_list_disable_behavior(self):
        """Test that Enable=false removes app from list"""
        service_urls = {
            "test-service": ["http://test.example.com"]
        }
        # Service has traefik-home metadata
        service_metadata = {
            "test-service": {"icon": "", "alias": "", "hide": False, "is_admin": False}
        }
        overrides = {
            "test-service": {"Enable": False}
        }
        
        apps = generate_page.build_app_list(service_urls, service_metadata, overrides)
        
        assert len(apps) == 0
    
    def test_build_app_list_override_metadata(self):
        """Test that overrides can customize app metadata"""
        service_urls = {
            "test-service": ["http://test.example.com"]
        }
        # Service must have traefik-home metadata to be included
        service_metadata = {
            "test-service": {"icon": "", "alias": "", "hide": False, "is_admin": False}
        }
        overrides = {
            "test-service": {
                "Name": "Custom Name",
                "Icon": "🚀",
                "Description": "A test service",
                "Category": "Testing",
                "Badge": "NEW"
            }
        }
        
        apps = generate_page.build_app_list(service_urls, service_metadata, overrides)
        
        assert len(apps) == 1
        app = apps[0]
        assert app["name"] == "Custom Name"
        assert app["icon"] == "🚀"
        assert app["description"] == "A test service"
        assert app["category"] == "Testing"
        assert app["badge"] == "NEW"
    
    def test_build_app_list_override_only_entries(self):
        """Test that override-only entries (not in Docker) can be added"""
        service_urls = {}
        overrides = {
            "external-service": {
                "Enable": True,
                "Name": "External Service",
                "Url": "https://external.example.com"
            }
        }
        
        apps = generate_page.build_app_list(service_urls, {}, overrides)
        
        assert len(apps) == 1
        app = apps[0]
        assert app["name"] == "External Service"
        assert "https://external.example.com" in app["urls"]
    
    def test_build_app_list_override_only_disabled_by_default(self):
        """Test that override-only entries need explicit Enable=true"""
        service_urls = {}
        overrides = {
            "external-service": {
                "Name": "External Service",
                "Url": "https://external.example.com"
            }
        }
        
        apps = generate_page.build_app_list(service_urls, {}, overrides)
        
        # Should not appear without Enable=true
        assert len(apps) == 0
    
    def test_build_app_list_override_with_multiple_urls(self):
        """Test override-only entry with multiple URLs"""
        service_urls = {}
        overrides = {
            "external-service": {
                "Enable": True,
                "Name": "External Service",
                "URLs": [
                    "https://external1.example.com",
                    "https://external2.example.com"
                ]
            }
        }
        
        apps = generate_page.build_app_list(service_urls, {}, overrides)
        
        assert len(apps) == 1
        app = apps[0]
        assert len(app["urls"]) == 2
        assert "https://external1.example.com" in app["urls"]
        assert "https://external2.example.com" in app["urls"]
    
    def test_build_app_list_urls_list_contains_all(self):
        """Test that urls list contains all URLs (no primary_url field, browser selects)"""
        service_urls = {
            "test-service": [
                "http://test1.example.com",
                "http://test2.example.com"
            ]
        }
        # Service must have traefik-home metadata to be included
        service_metadata = {
            "test-service": {"icon": "", "alias": "", "hide": False, "is_admin": False}
        }
        overrides = {}
        
        apps = generate_page.build_app_list(service_urls, service_metadata, overrides)
        
        assert len(apps) == 1
        app = apps[0]
        assert "urls" in app
        assert len(app["urls"]) == 2
        assert "http://test1.example.com" in app["urls"]
        assert "http://test2.example.com" in app["urls"]
        # Verify primary_url is NOT in the app (browser determines it)
        assert "primary_url" not in app
    
    def test_build_app_list_no_traefik_home_labels_excluded(self):
        """Test that services without traefik-home labels are NOT included"""
        service_urls = {
            "test-service": ["http://test.example.com"],
            "no-labels-service": ["http://nolabels.example.com"]
        }
        # Only test-service has traefik-home metadata
        service_metadata = {
            "test-service": {"icon": "", "alias": "", "hide": False, "is_admin": False}
        }
        overrides = {}
        
        apps = generate_page.build_app_list(service_urls, service_metadata, overrides)
        
        # Only test-service should be included
        assert len(apps) == 1
        assert apps[0]["name"] == "Test Service"


class TestExternalApps:
    """Tests for external app discovery and integration"""
    
    def test_get_external_apps_from_labels(self):
        """Test parsing external app labels from traefik-home container"""
        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()
        mock_container.labels = {
            "traefik-home.app.router.enable": "true",
            "traefik-home.app.router.alias": "Home Router",
            "traefik-home.app.router.url": "http://192.168.1.1",
            "traefik-home.app.router.icon": "/icons/router.png",
            "traefik-home.app.router.category": "Network",
            "traefik-home.app.router.description": "Local network router",
            "traefik-home.app.nas.enable": "true",
            "traefik-home.app.nas.alias": "NAS Storage",
            "traefik-home.app.nas.url": "http://nas.local",
            "traefik-home.app.nas.admin": "true",
            "traefik-home.app.disabled-app.enable": "false",
            "traefik-home.app.disabled-app.url": "http://disabled.local"
        }
        
        # Mock environment variable
        with patch.dict(os.environ, {"HOSTNAME": "test-container-id"}):
            mock_client.containers.get.return_value = mock_container
            
            result = generate_page.get_external_apps_from_labels(mock_client)
        
        # Should have 3 apps parsed (router, nas, disabled-app)
        assert len(result) == 3
        
        # Check router app
        assert "router" in result
        assert result["router"]["enabled"] == True
        assert result["router"]["alias"] == "Home Router"
        assert result["router"]["urls"] == ["http://192.168.1.1"]
        assert result["router"]["icon"] == "/icons/router.png"
        assert result["router"]["category"] == "Network"
        assert result["router"]["description"] == "Local network router"
        
        # Check NAS app (admin)
        assert "nas" in result
        assert result["nas"]["enabled"] == True
        assert result["nas"]["alias"] == "NAS Storage"
        assert result["nas"]["urls"] == ["http://nas.local"]
        assert result["nas"]["is_admin"] == True
        
        # Check disabled app
        assert "disabled-app" in result
        assert result["disabled-app"]["enabled"] == False
    
    def test_docker_and_external_apps_integration(self):
        """
        Test complete integration: Docker app + External app with all labels.
        
        Scenario:
        1. Docker container with traefik labels (discovered service)
        2. External app via traefik-home.app.<name> labels (manual entry)
        3. Result should be 2 apps with all label data present
        """
        # 1. Docker app with container labels
        service_urls = {
            "whoami": ["http://whoami.example.com", "http://whoami.local"]
        }
        service_metadata = {
            "whoami": {
                "alias": "Who Am I",
                "icon": "/icons/whoami.png",
                "is_admin": False
            }
        }
        
        # 2. External app via traefik-home.app.<name> labels
        external_apps = {
            "router": {
                "enabled": True,
                "alias": "Home Router",
                "urls": ["http://192.168.1.1"],
                "icon": "/icons/router.png",
                "category": "Network",
                "description": "Local network router",
                "is_admin": False
            },
            "nas": {
                "enabled": True,
                "alias": "NAS Storage",
                "urls": ["http://nas.local"],
                "icon": "/icons/nas.png",
                "is_admin": True,
                "description": "Network attached storage"
            }
        }
        
        overrides = {}
        
        # 3. Build app list with both Docker and external apps
        apps = generate_page.build_app_list(
            service_urls,
            service_metadata,
            overrides,
            external_apps
        )
        
        # Should have 3 apps total: 1 Docker + 2 external
        assert len(apps) == 3, f"Expected 3 apps, got {len(apps)}: {[app['name'] for app in apps]}"
        
        # Find and verify whoami (Docker app)
        whoami_app = next((app for app in apps if "who am i" in app["name"].lower()), None)
        assert whoami_app is not None, f"whoami app not found in: {[app['name'] for app in apps]}"
        assert whoami_app["name"] == "Who Am I"
        assert len(whoami_app["urls"]) == 2
        assert "http://whoami.example.com" in whoami_app["urls"]
        assert "http://whoami.local" in whoami_app["urls"]
        assert whoami_app["icon"] == "/icons/whoami.png"
        assert whoami_app["category"] == "Apps"
        
        # Find and verify router (external app)
        router_app = next((app for app in apps if "Router" in app["name"]), None)
        assert router_app is not None
        assert router_app["name"] == "Home Router"
        assert router_app["urls"] == ["http://192.168.1.1"]
        assert router_app["icon"] == "/icons/router.png"
        assert router_app["category"] == "Network"
        assert router_app["description"] == "Local network router"
        
        # Find and verify NAS (external admin app)
        nas_app = next((app for app in apps if "NAS" in app["name"]), None)
        assert nas_app is not None
        assert nas_app["name"] == "NAS Storage"
        assert nas_app["urls"] == ["http://nas.local"]
        assert nas_app["icon"] == "/icons/nas.png"
        assert nas_app["category"] == "Admin"  # Should be Admin category
        assert nas_app["description"] == "Network attached storage"
    
    def test_external_app_disabled_not_in_list(self):
        """Test that disabled external apps don't appear in the final list"""
        external_apps = {
            "enabled-app": {
                "enabled": True,
                "urls": ["http://enabled.local"]
            },
            "disabled-app": {
                "enabled": False,
                "urls": ["http://disabled.local"]
            }
        }
        
        apps = generate_page.build_app_list({}, {}, {}, external_apps)
        
        # Should only have 1 app (enabled-app)
        assert len(apps) == 1
        assert apps[0]["urls"] == ["http://enabled.local"]
    
    def test_external_app_without_url_not_in_list(self):
        """Test that external apps without URL don't appear in the final list"""
        external_apps = {
            "no-url-app": {
                "enabled": True,
                "alias": "No URL App"
                # Missing url field
            },
            "with-url-app": {
                "enabled": True,
                "urls": ["http://valid.local"]
            }
        }
        
        apps = generate_page.build_app_list({}, {}, {}, external_apps)
        
        # Should only have 1 app (with-url-app)
        assert len(apps) == 1
        assert apps[0]["urls"] == ["http://valid.local"]


class TestTraefikAPIDiscovery:
    """Tests for Traefik API router discovery"""
    
    def test_fetch_traefik_routers_list_format(self):
        """Test fetching routers from Traefik API (list format)"""
        # Mock requests module
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "name": "omv@file",
                "entryPoints": ["web"],
                "rule": "Host(`omv.locker.local`)",
                "service": "omv",
                "status": "enabled"
            },
            {
                "name": "rclone@file",
                "entryPoints": ["websecure"],
                "rule": "Host(`rclone.example.com`) || Host(`rclone.locker.local`)",
                "service": "rclone",
                "status": "enabled"
            }
        ]
        
        with patch.object(generate_page.requests, 'get', return_value=mock_response):
            result = generate_page.fetch_traefik_routers("http://traefik:8080")
        
        # Should have URLs for both routers
        assert "omv" in result
        assert "http://omv.locker.local" in result["omv"]
        
        assert "rclone" in result
        # rclone uses websecure, should be https
        assert "https://rclone.example.com" in result["rclone"]
        assert "https://rclone.locker.local" in result["rclone"]
    
    def test_fetch_traefik_routers_stores_under_multiple_keys(self):
        """Test that routers are stored under service name, router name, and base name"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "name": "traefik-ui@file",
                "entryPoints": ["web"],
                "rule": "Host(`traefik.locker.local`)",
                "service": "api@internal",
                "status": "enabled"
            }
        ]
        
        with patch.object(generate_page.requests, 'get', return_value=mock_response):
            result = generate_page.fetch_traefik_routers("http://traefik:8080")
        
        # Should be stored under full router name and base name
        assert "traefik-ui@file" in result
        assert "traefik-ui" in result
        assert "http://traefik.locker.local" in result["traefik-ui"]
    
    def test_external_app_matches_traefik_api_router(self):
        """Test that external apps can match routers from Traefik API"""
        # Service URLs discovered from Traefik API (simulates file provider)
        service_urls = {
            "omv": ["http://omv.locker.local"],
            "omv@file": ["http://omv.locker.local"],
            "rclone": ["https://rclone.locker.local"],
            "rclone@file": ["https://rclone.locker.local"]
        }
        
        # External apps defined on traefik-home container
        external_apps = {
            "omv": {
                "enabled": True,
                "alias": "OpenMediaVault NAS",
                "icon": "https://www.openmediavault.org/favicon.ico",
                "is_admin": True,
                "category": "Admin"  # Explicit category
            },
            "rclone": {
                "enabled": True,
                "alias": "Rclone WebUI",
                "icon": "https://rclone.org/favicon.ico",
                "is_admin": True,
                "category": "Admin"  # Explicit category
            }
        }
        
        apps = generate_page.build_app_list(service_urls, {}, {}, external_apps)
        
        # Should find both external apps with URLs from Traefik API
        assert len(apps) >= 2
        
        omv_app = next((app for app in apps if "OpenMediaVault" in app["name"]), None)
        assert omv_app is not None
        assert "http://omv.locker.local" in omv_app["urls"]
        assert omv_app["category"] == "Admin"
        
        rclone_app = next((app for app in apps if "Rclone" in app["name"]), None)
        assert rclone_app is not None
        assert "https://rclone.locker.local" in rclone_app["urls"]
        assert rclone_app["category"] == "Admin"


class TestLoadOverrides:
    """Tests for load_overrides function"""
    
    def test_load_overrides_file_exists(self, tmp_path):
        """Test loading overrides from existing file"""
        override_file = tmp_path / "overrides.json"
        overrides_data = {
            "test-service": {
                "Name": "Test Service",
                "Icon": "🧪"
            }
        }
        override_file.write_text(json.dumps(overrides_data))
        
        result = generate_page.load_overrides(str(override_file))
        
        assert result == overrides_data
    
    def test_load_overrides_file_not_exists(self):
        """Test loading overrides when file doesn't exist"""
        result = generate_page.load_overrides("/nonexistent/file.json")
        assert result == {}
    
    def test_load_overrides_none_path(self):
        """Test loading overrides with None path"""
        result = generate_page.load_overrides(None)
        assert result == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
