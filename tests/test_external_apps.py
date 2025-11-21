"""
Unit tests for external app discovery and inclusion in apps.json
"""
import pytest
import sys
from unittest.mock import Mock, MagicMock, patch

# Mock the imports before importing generate_page
sys.modules['docker'] = MagicMock()
sys.modules['requests'] = MagicMock()

from app.generate_page import get_external_apps_from_labels, build_app_list


def test_get_external_apps_from_labels_basic():
    """Test basic external app extraction from Docker labels"""
    # Mock Docker client and container
    mock_client = Mock()
    mock_container = Mock()
    mock_container.labels = {
        'traefik-home.app.router.enable': 'true',
        'traefik-home.app.router.alias': 'Network Router',
        'traefik-home.app.router.url': 'http://192.168.1.1',
        'traefik-home.app.router.icon': '/icons/router.png',
        'traefik-home.app.router.category': 'Network',
    }
    mock_client.containers.list.return_value = [mock_container]
    
    # Get external apps
    external_apps = get_external_apps_from_labels(mock_client, 'traefik-home')
    
    # Verify external app extracted correctly
    assert len(external_apps) == 1
    assert 'router' in external_apps
    assert external_apps['router']['alias'] == 'Network Router'
    assert external_apps['router']['url'] == 'http://192.168.1.1'
    assert external_apps['router']['icon'] == '/icons/router.png'
    assert external_apps['router']['category'] == 'Network'
    assert external_apps['router']['enable'] is True


def test_get_external_apps_from_labels_multiple():
    """Test extraction of multiple external apps"""
    mock_client = Mock()
    mock_container = Mock()
    mock_container.labels = {
        'traefik-home.app.router.enable': 'true',
        'traefik-home.app.router.alias': 'Router',
        'traefik-home.app.router.url': 'http://192.168.1.1',
        'traefik-home.app.switch.enable': 'true',
        'traefik-home.app.switch.alias': 'Switch',
        'traefik-home.app.switch.url': 'http://192.168.1.2',
        'traefik-home.app.switch.admin': 'true',
    }
    mock_client.containers.list.return_value = [mock_container]
    
    external_apps = get_external_apps_from_labels(mock_client, 'traefik-home')
    
    assert len(external_apps) == 2
    assert 'router' in external_apps
    assert 'switch' in external_apps
    assert external_apps['router']['alias'] == 'Router'
    assert external_apps['switch']['alias'] == 'Switch'
    assert external_apps['switch'].get('admin') == 'true'


def test_get_external_apps_from_labels_disabled():
    """Test that disabled external apps are not included"""
    mock_client = Mock()
    mock_container = Mock()
    mock_container.labels = {
        'traefik-home.app.disabled.enable': 'false',
        'traefik-home.app.disabled.alias': 'Disabled App',
        'traefik-home.app.disabled.url': 'http://example.com',
    }
    mock_client.containers.list.return_value = [mock_container]
    
    external_apps = get_external_apps_from_labels(mock_client, 'traefik-home')
    
    # Should not include disabled app
    assert len(external_apps) == 0


def test_get_external_apps_from_labels_no_enable_flag():
    """Test that apps without enable flag are not included"""
    mock_client = Mock()
    mock_container = Mock()
    mock_container.labels = {
        'traefik-home.app.incomplete.alias': 'Incomplete App',
        'traefik-home.app.incomplete.url': 'http://example.com',
    }
    mock_client.containers.list.return_value = [mock_container]
    
    external_apps = get_external_apps_from_labels(mock_client, 'traefik-home')
    
    # Should not include app without enable=true
    assert len(external_apps) == 0


def test_build_app_list_includes_external_apps():
    """Test that build_app_list includes external apps in final output"""
    service_url_map = {
        'webapp': {
            'urls': ['https://app.example.com'],
            'icon': '/icons/app.png',
            'alias': 'Web App',
            'admin': False,
        }
    }
    
    external_apps = {
        'router': {
            'enable': True,
            'alias': 'Network Router',
            'url': 'http://192.168.1.1',
            'icon': '/icons/router.png',
            'category': 'Network',
            'admin': False,
        }
    }
    
    overrides = {}
    config = {}
    
    app_list = build_app_list(service_url_map, {}, external_apps, overrides, config)
    
    # Should have 2 apps: 1 from services, 1 external
    assert len(app_list) == 2
    
    # Find the external app
    external_app = next((app for app in app_list if app['name'] == 'Network Router'), None)
    assert external_app is not None
    assert external_app['urls'] == ['http://192.168.1.1']
    assert external_app['icon'] == '/icons/router.png'
    assert external_app['category'] == 'Network'


def test_build_app_list_external_apps_admin_category():
    """Test that external apps with admin=true go to Admin category"""
    service_url_map = {}
    
    external_apps = {
        'admin_tool': {
            'enable': True,
            'alias': 'Admin Tool',
            'url': 'http://admin.local',
            'icon': '/icons/admin.png',
            'admin': 'true',  # Should go to Admin category
        }
    }
    
    overrides = {}
    config = {}
    
    app_list = build_app_list(service_url_map, {}, external_apps, overrides, config)
    
    assert len(app_list) == 1
    assert app_list[0]['name'] == 'Admin Tool'
    assert app_list[0]['category'] == 'Admin'


def test_build_app_list_external_apps_with_overrides():
    """Test that external apps can be overridden"""
    service_url_map = {}
    
    external_apps = {
        'router': {
            'enable': True,
            'alias': 'Router',
            'url': 'http://192.168.1.1',
            'category': 'Network',
        }
    }
    
    overrides = {
        'Router': {
            'Enable': True,
            'Icon': '/custom/router-icon.png',
            'Category': 'Infrastructure',
        }
    }
    
    config = {}
    
    app_list = build_app_list(service_url_map, {}, external_apps, overrides, config)
    
    assert len(app_list) == 1
    assert app_list[0]['name'] == 'Router'
    assert app_list[0]['icon'] == '/custom/router-icon.png'
    assert app_list[0]['category'] == 'Infrastructure'


def test_get_external_apps_from_labels_no_container():
    """Test behavior when traefik-home container is not found"""
    mock_client = Mock()
    mock_client.containers.list.return_value = []
    
    external_apps = get_external_apps_from_labels(mock_client, 'traefik-home')
    
    # Should return empty dict if container not found
    assert external_apps == {}


def test_external_apps_preserves_all_metadata():
    """Test that all external app metadata is preserved in output"""
    service_url_map = {}
    
    external_apps = {
        'device': {
            'enable': True,
            'alias': 'IoT Device',
            'url': 'http://192.168.1.100',
            'icon': '/icons/iot.png',
            'category': 'IoT',
            'description': 'Smart home device',
            'admin': 'false',
        }
    }
    
    overrides = {}
    config = {}
    
    app_list = build_app_list(service_url_map, {}, external_apps, overrides, config)
    
    assert len(app_list) == 1
    app = app_list[0]
    assert app['name'] == 'IoT Device'
    assert app['urls'] == ['http://192.168.1.100']
    assert app['icon'] == '/icons/iot.png'
    assert app['category'] == 'IoT'
    # Note: description is typically stored in overrides, not in app list directly
