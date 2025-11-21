#!/usr/bin/env python3
"""Tests for generate_page.py"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

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
        assert urls == ["https://example.com"]
    
    def test_parse_multiple_hosts(self):
        """Test parsing multiple Host() rules with OR"""
        rule = "Host(`example.com`) || Host(`www.example.com`)"
        urls = generate_page.parse_traefik_rule(rule)
        assert "https://example.com" in urls
        assert "https://www.example.com" in urls
    
    def test_parse_host_with_single_quotes(self):
        """Test parsing Host() with single quotes"""
        rule = "Host('example.com')"
        urls = generate_page.parse_traefik_rule(rule)
        assert urls == ["https://example.com"]
    
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
        
        result = generate_page.build_service_url_map(mock_client)
        
        assert "test-service" in result
        assert "https://test.example.com" in result["test-service"]
    
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
        
        result = generate_page.build_service_url_map(mock_client)
        
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
        
        result = generate_page.build_service_url_map(mock_client)
        
        # Should have one unique URL
        assert len(result["test-service"]) == 1
        assert "https://test.example.com" in result["test-service"]


class TestBuildAppList:
    """Tests for build_app_list function"""
    
    def test_build_app_list_includes_all_urls(self):
        """Test that all URLs are included in app list (no host filtering)"""
        service_urls = {
            "test-service": [
                "https://test.example.com",
                "https://test.other.com",
                "https://test.local.com"
            ]
        }
        overrides = {}
        
        apps = generate_page.build_app_list(service_urls, overrides)
        
        assert len(apps) == 1
        app = apps[0]
        assert len(app["urls"]) == 3
        assert "https://test.example.com" in app["urls"]
        assert "https://test.other.com" in app["urls"]
        assert "https://test.local.com" in app["urls"]
    
    def test_build_app_list_enable_defaulting(self):
        """Test that Enable defaults to True for Docker services"""
        service_urls = {
            "test-service": ["https://test.example.com"]
        }
        overrides = {}
        
        apps = generate_page.build_app_list(service_urls, overrides)
        
        assert len(apps) == 1
    
    def test_build_app_list_hide_behavior(self):
        """Test that Hide=true removes app from list"""
        service_urls = {
            "test-service": ["https://test.example.com"]
        }
        overrides = {
            "test-service": {"Hide": True}
        }
        
        apps = generate_page.build_app_list(service_urls, overrides)
        
        assert len(apps) == 0
    
    def test_build_app_list_disable_behavior(self):
        """Test that Enable=false removes app from list"""
        service_urls = {
            "test-service": ["https://test.example.com"]
        }
        overrides = {
            "test-service": {"Enable": False}
        }
        
        apps = generate_page.build_app_list(service_urls, overrides)
        
        assert len(apps) == 0
    
    def test_build_app_list_override_metadata(self):
        """Test that overrides can customize app metadata"""
        service_urls = {
            "test-service": ["https://test.example.com"]
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
        
        apps = generate_page.build_app_list(service_urls, overrides)
        
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
        
        apps = generate_page.build_app_list(service_urls, overrides)
        
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
        
        apps = generate_page.build_app_list(service_urls, overrides)
        
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
        
        apps = generate_page.build_app_list(service_urls, overrides)
        
        assert len(apps) == 1
        app = apps[0]
        assert len(app["urls"]) == 2
        assert "https://external1.example.com" in app["urls"]
        assert "https://external2.example.com" in app["urls"]
    
    def test_build_app_list_primary_url_is_first(self):
        """Test that primary_url is set to first URL"""
        service_urls = {
            "test-service": [
                "https://test1.example.com",
                "https://test2.example.com"
            ]
        }
        overrides = {}
        
        apps = generate_page.build_app_list(service_urls, overrides)
        
        assert len(apps) == 1
        app = apps[0]
        assert app["primary_url"] == "https://test1.example.com"


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
