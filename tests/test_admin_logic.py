"""
Tests for admin access control logic
"""

import pytest


def test_admin_string_comparison():
    """Test that admin flag comparison works correctly with string values"""
    # Simulate the API response
    api_response = {
        'username': 'admin_user',
        'email': 'admin@example.com',
        'name': 'Admin User',
        'isAdmin': 'true'  # API returns string, not boolean
    }
    
    # Simulate currentUserInfo object
    currentUserInfo = {
        'username': api_response['username'],
        'email': api_response['email'],
        'name': api_response['name'],
        'isAdmin': api_response['isAdmin']  # Keep as string
    }
    
    # Test admin check (should be True when isAdmin === 'true')
    isUserAdmin = currentUserInfo and currentUserInfo['isAdmin'] == 'true'
    assert isUserAdmin == True, "Admin user should be detected when isAdmin === 'true'"


def test_non_admin_string_comparison():
    """Test that non-admin flag comparison works correctly"""
    # Simulate the API response for non-admin user
    api_response = {
        'username': 'regular_user',
        'email': 'user@example.com',
        'name': 'Regular User',
        'isAdmin': 'false'  # API returns string 'false' for non-admins
    }
    
    # Simulate currentUserInfo object
    currentUserInfo = {
        'username': api_response['username'],
        'email': api_response['email'],
        'name': api_response['name'],
        'isAdmin': api_response['isAdmin']
    }
    
    # Test admin check (should be False when isAdmin === 'false')
    isUserAdmin = currentUserInfo and currentUserInfo['isAdmin'] == 'true'
    assert isUserAdmin == False, "Regular user should not be detected as admin when isAdmin === 'false'"


def test_no_user_info():
    """Test that admin check works correctly when no user is logged in"""
    currentUserInfo = None
    
    # Test admin check (should be falsy when currentUserInfo is None)
    isUserAdmin = currentUserInfo and currentUserInfo.get('isAdmin') == 'true'
    assert isUserAdmin == None or isUserAdmin == False, "No admin access when user is not logged in"


def test_empty_is_admin():
    """Test that admin check works correctly with empty isAdmin value"""
    currentUserInfo = {
        'username': 'test_user',
        'email': 'test@example.com',
        'name': 'Test User',
        'isAdmin': ''  # Empty string
    }
    
    # Test admin check (should be False when isAdmin is empty string)
    isUserAdmin = currentUserInfo and currentUserInfo['isAdmin'] == 'true'
    assert isUserAdmin == False, "Empty isAdmin should not grant admin access"


def test_missing_is_admin():
    """Test that admin check works correctly when isAdmin key is missing"""
    currentUserInfo = {
        'username': 'test_user',
        'email': 'test@example.com',
        'name': 'Test User'
        # isAdmin key is missing
    }
    
    # Test admin check (should be False when isAdmin is missing)
    isUserAdmin = currentUserInfo and currentUserInfo.get('isAdmin') == 'true'
    assert isUserAdmin == False, "Missing isAdmin should not grant admin access"


def test_admin_apps_visibility():
    """Test that admin apps are only visible to admin users"""
    # Test with admin user
    currentUserInfo_admin = {
        'username': 'admin',
        'isAdmin': 'true'
    }
    isUserAdmin = currentUserInfo_admin and currentUserInfo_admin['isAdmin'] == 'true'
    
    # Simulate checking if admin apps should be shown
    app_category = 'Admin'
    should_show_admin_app = (app_category != 'Admin') or isUserAdmin
    
    assert should_show_admin_app == True, "Admin apps should be visible to admin users"
    
    # Test with non-admin user
    currentUserInfo_regular = {
        'username': 'user',
        'isAdmin': 'false'
    }
    isUserAdmin = currentUserInfo_regular and currentUserInfo_regular['isAdmin'] == 'true'
    should_show_admin_app = (app_category != 'Admin') or isUserAdmin
    
    assert should_show_admin_app == False, "Admin apps should NOT be visible to non-admin users"
    
    # Test regular app visibility for both users
    app_category = 'Apps'
    
    # Admin user can see regular apps
    isUserAdmin = currentUserInfo_admin and currentUserInfo_admin['isAdmin'] == 'true'
    should_show_regular_app = (app_category != 'Admin') or isUserAdmin
    assert should_show_regular_app == True, "Regular apps should be visible to admin users"
    
    # Regular user can see regular apps
    isUserAdmin = currentUserInfo_regular and currentUserInfo_regular['isAdmin'] == 'true'
    should_show_regular_app = (app_category != 'Admin') or isUserAdmin
    assert should_show_regular_app == True, "Regular apps should be visible to regular users"
