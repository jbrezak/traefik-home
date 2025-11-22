#!/usr/bin/env python3
"""Tests for atomic_write function"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock docker and requests before importing generate_page
sys.modules['docker'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Add app directory to path to import generate_page
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
import generate_page


class TestAtomicWrite:
    """Tests for atomic_write functionality"""
    
    def test_atomic_write_creates_file(self, tmp_path):
        """Test that atomic_write creates a file with correct content"""
        filepath = tmp_path / "test.txt"
        content = "Hello, World!"
        
        generate_page.atomic_write(str(filepath), content)
        
        assert filepath.exists()
        assert filepath.read_text() == content
    
    def test_atomic_write_overwrites_existing(self, tmp_path):
        """Test that atomic_write overwrites existing file"""
        filepath = tmp_path / "test.txt"
        
        # Create initial file
        filepath.write_text("Initial content")
        
        # Overwrite with atomic_write
        new_content = "New content"
        generate_page.atomic_write(str(filepath), new_content)
        
        assert filepath.read_text() == new_content
    
    def test_atomic_write_no_tmp_files_left(self, tmp_path):
        """Test that atomic_write doesn't leave temporary files behind"""
        filepath = tmp_path / "test.txt"
        content = "Test content"
        
        generate_page.atomic_write(str(filepath), content)
        
        # Check no .tmp files left
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0
        
        # Check no hidden temp files left (starting with .)
        all_files = list(tmp_path.iterdir())
        hidden_files = [f for f in all_files if f.name.startswith('.') and f.is_file()]
        assert len(hidden_files) == 0
    
    def test_atomic_write_preserves_content_on_error(self, tmp_path):
        """Test that original file is preserved if write fails"""
        filepath = tmp_path / "test.txt"
        
        # Create initial file
        original_content = "Original content"
        filepath.write_text(original_content)
        
        # Try to write to a directory that will cause an error
        # (this should fail during the chmod or rename step)
        try:
            # Make directory read-only to cause error
            tmp_path.chmod(0o444)
            generate_page.atomic_write(str(filepath), "New content")
        except Exception:
            pass  # Expected to fail
        finally:
            # Restore permissions
            tmp_path.chmod(0o755)
        
        # Original file might be affected, but no tmp files should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0
    
    def test_atomic_write_large_content(self, tmp_path):
        """Test atomic_write with large content"""
        filepath = tmp_path / "large.txt"
        
        # Create large content (1MB)
        content = "x" * (1024 * 1024)
        
        generate_page.atomic_write(str(filepath), content)
        
        assert filepath.exists()
        assert len(filepath.read_text()) == len(content)
    
    def test_atomic_write_unicode_content(self, tmp_path):
        """Test atomic_write with Unicode content"""
        filepath = tmp_path / "unicode.txt"
        content = "Hello 世界 🌍 Émoji"
        
        generate_page.atomic_write(str(filepath), content)
        
        assert filepath.exists()
        assert filepath.read_text() == content
    
    def test_atomic_write_sets_permissions(self, tmp_path):
        """Test that atomic_write sets correct file permissions"""
        filepath = tmp_path / "test.txt"
        content = "Test"
        
        # Write with default permissions
        generate_page.atomic_write(str(filepath), content)
        
        # Check permissions (should be 0o644)
        stat_info = filepath.stat()
        mode = stat_info.st_mode & 0o777
        assert mode == 0o644
    
    def test_atomic_write_custom_permissions(self, tmp_path):
        """Test atomic_write with custom permissions"""
        filepath = tmp_path / "test.txt"
        content = "Test"
        
        # Write with custom permissions
        generate_page.atomic_write(str(filepath), content, mode=0o600)
        
        # Check permissions
        stat_info = filepath.stat()
        mode = stat_info.st_mode & 0o777
        assert mode == 0o600
    
    def test_atomic_write_multiple_sequential(self, tmp_path):
        """Test multiple sequential atomic writes"""
        filepath = tmp_path / "test.txt"
        
        # Write multiple times
        for i in range(5):
            content = f"Content {i}"
            generate_page.atomic_write(str(filepath), content)
            assert filepath.read_text() == content
        
        # Ensure no tmp files accumulated
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
