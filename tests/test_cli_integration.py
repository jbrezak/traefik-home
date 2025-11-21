#!/usr/bin/env python3
"""Integration tests for generate_page CLI"""

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


class TestCLIIntegration:
    """Integration tests for the CLI"""
    
    def test_main_creates_apps_json(self, tmp_path, monkeypatch):
        """Test that main() creates apps.json file"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Mock Docker client
        mock_docker_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-service"
        mock_container.labels = {
            "traefik.http.routers.test.rule": "Host(`test.example.com`)",
            "com.docker.compose.service": "test-service"
        }
        mock_docker_client.containers.list.return_value = [mock_container]
        
        # Patch sys.argv and docker.from_env
        monkeypatch.setattr(sys, "argv", [
            "generate_page.py",
            "--output-dir", str(output_dir),
            "--overrides", "/nonexistent/overrides.json"
        ])
        
        with patch("docker.from_env", return_value=mock_docker_client):
            generate_page.main()
        
        # Check that apps.json was created
        apps_json_path = output_dir / "apps.json"
        assert apps_json_path.exists()
        
        # Parse and validate apps.json
        with open(apps_json_path) as f:
            data = json.load(f)
        
        assert "_generated" in data
        assert "apps" in data
        assert len(data["apps"]) > 0
        
        # Check that app has full URL list
        app = data["apps"][0]
        assert "urls" in app
        assert "http://test.example.com" in app["urls"]
    
    def test_main_creates_html_files(self, tmp_path, monkeypatch):
        """Test that main() creates home.html and index.html"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Mock Docker client
        mock_docker_client = Mock()
        mock_docker_client.containers.list.return_value = []
        
        # Patch sys.argv and docker.from_env
        monkeypatch.setattr(sys, "argv", [
            "generate_page.py",
            "--output-dir", str(output_dir),
            "--overrides", "/nonexistent/overrides.json"
        ])
        
        with patch("docker.from_env", return_value=mock_docker_client):
            generate_page.main()
        
        # Check that HTML files were created
        home_html = output_dir / "home.html"
        index_html = output_dir / "index.html"
        
        assert home_html.exists()
        assert index_html.exists()
        
        # Check that HTML contains expected content
        content = home_html.read_text()
        assert "<!DOCTYPE html>" in content
        assert "Traefik Home" in content
        assert "apps.json" in content
    
    def test_main_with_multiple_urls_per_service(self, tmp_path, monkeypatch):
        """Test that main() includes all URLs for a service"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Mock Docker client with service having multiple URLs
        mock_docker_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-service"
        mock_container.labels = {
            "traefik.http.routers.test1.rule": "Host(`test1.example.com`)",
            "traefik.http.routers.test2.rule": "Host(`test2.example.com`)",
            "traefik.http.routers.test3.rule": "Host(`test3.example.com`)",
            "com.docker.compose.service": "test-service"
        }
        mock_docker_client.containers.list.return_value = [mock_container]
        
        # Patch sys.argv and docker.from_env
        monkeypatch.setattr(sys, "argv", [
            "generate_page.py",
            "--output-dir", str(output_dir),
            "--overrides", "/nonexistent/overrides.json"
        ])
        
        with patch("docker.from_env", return_value=mock_docker_client):
            generate_page.main()
        
        # Check apps.json
        apps_json_path = output_dir / "apps.json"
        with open(apps_json_path) as f:
            data = json.load(f)
        
        # Should have one app with all three URLs
        assert len(data["apps"]) == 1
        app = data["apps"][0]
        assert len(app["urls"]) == 3
        assert "http://test1.example.com" in app["urls"]
        assert "http://test2.example.com" in app["urls"]
        assert "http://test3.example.com" in app["urls"]
    
    def test_main_uses_custom_template(self, tmp_path, monkeypatch):
        """Test that main() uses custom template if provided"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        template_file = tmp_path / "custom.tmpl"
        template_content = "<html><body>Custom Template</body></html>"
        template_file.write_text(template_content)
        
        # Mock Docker client
        mock_docker_client = Mock()
        mock_docker_client.containers.list.return_value = []
        
        # Patch sys.argv and docker.from_env
        monkeypatch.setattr(sys, "argv", [
            "generate_page.py",
            "--output-dir", str(output_dir),
            "--template", str(template_file),
            "--overrides", "/nonexistent/overrides.json"
        ])
        
        with patch("docker.from_env", return_value=mock_docker_client):
            generate_page.main()
        
        # Check that HTML files use custom template
        home_html = output_dir / "home.html"
        content = home_html.read_text()
        assert content == template_content
    
    def test_main_with_overrides_file(self, tmp_path, monkeypatch):
        """Test that main() applies overrides from file"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Create overrides file
        overrides_file = tmp_path / "overrides.json"
        overrides_data = {
            "test-service": {
                "Name": "Custom Service Name",
                "Icon": "🚀",
                "Category": "Testing"
            }
        }
        overrides_file.write_text(json.dumps(overrides_data))
        
        # Mock Docker client
        mock_docker_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-service"
        mock_container.labels = {
            "traefik.http.routers.test.rule": "Host(`test.example.com`)",
            "com.docker.compose.service": "test-service"
        }
        mock_docker_client.containers.list.return_value = [mock_container]
        
        # Patch sys.argv and docker.from_env
        monkeypatch.setattr(sys, "argv", [
            "generate_page.py",
            "--output-dir", str(output_dir),
            "--overrides", str(overrides_file)
        ])
        
        with patch("docker.from_env", return_value=mock_docker_client):
            generate_page.main()
        
        # Check apps.json
        apps_json_path = output_dir / "apps.json"
        with open(apps_json_path) as f:
            data = json.load(f)
        
        # Check that overrides were applied
        app = data["apps"][0]
        assert app["name"] == "Custom Service Name"
        assert app["icon"] == "🚀"
        assert app["category"] == "Testing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
