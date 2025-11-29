"""Tests for landing page functionality."""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch

# Import the app module
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))


class TestFindMarkdownFile:
    """Test the find_markdown_file function."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_find_markdown_file_missing_directory(self):
        """Test find_markdown_file when content directory doesn't exist."""
        with patch.dict('os.environ', {'CONTENT_DIR': '/nonexistent/path'}):
            import app
            filename, error = app.find_markdown_file()
            assert filename is None
            assert "Content directory not found" in error

    @pytest.mark.unit
    def test_find_markdown_file_index_md_priority(self):
        """Test that index.md is selected when multiple files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple markdown files
            for name in ['index.md', 'README.md', 'other.md']:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write(f'# {name}')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                filename, error = app.find_markdown_file()
                assert filename == 'index.md'
                assert error is None

    @pytest.mark.unit
    def test_find_markdown_file_readme_fallback(self):
        """Test that README.md is selected when index.md doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create README.md and other files
            for name in ['README.md', 'other.md']:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write(f'# {name}')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                filename, error = app.find_markdown_file()
                assert filename == 'README.md'
                assert error is None

    @pytest.mark.unit
    def test_find_markdown_file_any_markdown(self):
        """Test that any markdown file is selected when no default files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a non-default markdown file
            with open(os.path.join(tmpdir, 'docs.md'), 'w') as f:
                f.write('# Documentation')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                filename, error = app.find_markdown_file()
                assert filename == 'docs.md'
                assert error is None

    @pytest.mark.unit
    def test_find_markdown_file_empty_directory(self):
        """Test find_markdown_file when content directory is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                filename, error = app.find_markdown_file()
                assert filename is None
                assert "No markdown files found" in error

    @pytest.mark.unit
    def test_find_markdown_file_no_markdown_files(self):
        """Test find_markdown_file when directory has no markdown files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create non-markdown files
            with open(os.path.join(tmpdir, 'file.txt'), 'w') as f:
                f.write('Not markdown')
            with open(os.path.join(tmpdir, 'data.json'), 'w') as f:
                f.write('{}')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                filename, error = app.find_markdown_file()
                assert filename is None
                assert "No markdown files found" in error


class TestIsSafePath:
    """Test the is_safe_path function."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_safe_path_simple(self):
        """Test that simple relative paths are safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import app
            assert app.is_safe_path(tmpdir, 'file.md') is True
            assert app.is_safe_path(tmpdir, 'subdir/file.md') is True

    @pytest.mark.unit
    def test_unsafe_path_traversal(self):
        """Test that path traversal attempts are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import app
            assert app.is_safe_path(tmpdir, '../etc/passwd') is False
            assert app.is_safe_path(tmpdir, '../../etc/passwd') is False
            assert app.is_safe_path(tmpdir, 'subdir/../../etc/passwd') is False

    @pytest.mark.unit
    def test_unsafe_absolute_path(self):
        """Test that absolute paths outside base are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import app
            assert app.is_safe_path(tmpdir, '/etc/passwd') is False


class TestLandingPageEndpoint:
    """Test the / landing page endpoint."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_landing_page_with_content(self):
        """Test landing page when markdown content exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create content file
            with open(os.path.join(tmpdir, 'index.md'), 'w') as f:
                f.write('# Welcome\n\nThis is the landing page.')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                response = client.get('/')
                assert response.status_code == 200
                html = response.get_data(as_text=True)
                assert 'text/html' in response.content_type
                assert '/content/index.md' in html
                assert 'has_content' not in html or 'true' in html.lower()

    @pytest.mark.unit
    def test_landing_page_without_content(self):
        """Test landing page when no markdown content exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                response = client.get('/')
                assert response.status_code == 200
                html = response.get_data(as_text=True)
                assert 'No markdown files found' in html or 'false' in html.lower()

    @pytest.mark.unit
    def test_landing_page_missing_directory(self):
        """Test landing page when content directory doesn't exist."""
        with patch.dict('os.environ', {'CONTENT_DIR': '/nonexistent/content/dir'}):
            import app
            client = app.app.test_client()
            response = client.get('/')
            assert response.status_code == 200
            html = response.get_data(as_text=True)
            assert 'Content directory not found' in html or 'false' in html.lower()


class TestContentEndpoint:
    """Test the /content/<path> endpoint."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_serve_markdown_file(self):
        """Test serving a markdown file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content = '# Test Content\n\nThis is a test.'
            with open(os.path.join(tmpdir, 'test.md'), 'w') as f:
                f.write(content)
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                response = client.get('/content/test.md')
                assert response.status_code == 200
                assert response.get_data(as_text=True) == content

    @pytest.mark.unit
    def test_serve_file_in_subdirectory(self):
        """Test serving a file from a subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, 'docs')
            os.makedirs(subdir)
            content = '# Docs\n\nDocumentation.'
            with open(os.path.join(subdir, 'guide.md'), 'w') as f:
                f.write(content)
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                response = client.get('/content/docs/guide.md')
                assert response.status_code == 200
                assert response.get_data(as_text=True) == content

    @pytest.mark.unit
    def test_serve_nonexistent_file(self):
        """Test serving a file that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                response = client.get('/content/nonexistent.md')
                assert response.status_code == 404

    @pytest.mark.unit
    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'safe.md'), 'w') as f:
                f.write('safe content')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                
                # Various path traversal attempts
                traversal_paths = [
                    '/content/../../../etc/passwd',
                    '/content/..%2F..%2F..%2Fetc%2Fpasswd',
                    '/content/subdir/../../etc/passwd',
                ]
                for path in traversal_paths:
                    response = client.get(path)
                    assert response.status_code == 404, f"Path {path} should return 404"

    @pytest.mark.unit
    def test_serve_image_file(self):
        """Test serving an image file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple PNG header (just for mime type detection)
            img_path = os.path.join(tmpdir, 'test.png')
            with open(img_path, 'wb') as f:
                # PNG header bytes
                f.write(b'\x89PNG\r\n\x1a\n')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                response = client.get('/content/test.png')
                assert response.status_code == 200


class TestMarkdownFilePriority:
    """Test markdown file selection priority."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_index_md_selected_over_readme(self):
        """Test that index.md takes priority over README.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ['index.md', 'README.md']:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write(f'# {name}')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                response = client.get('/')
                html = response.get_data(as_text=True)
                assert '/content/index.md' in html

    @pytest.mark.unit
    def test_readme_md_selected_over_lowercase(self):
        """Test that README.md takes priority over readme.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ['README.md', 'readme.md']:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write(f'# {name}')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                filename, error = app.find_markdown_file()
                assert filename == 'README.md'


class TestContentUpdates:
    """Test that content updates are reflected on reload."""

    def setup_method(self):
        """Reset app module before each test."""
        if 'app' in sys.modules:
            del sys.modules['app']

    @pytest.mark.unit
    def test_content_changes_reflected(self):
        """Test that changing content file updates the served content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test.md')
            
            # Initial content
            with open(filepath, 'w') as f:
                f.write('# Initial Content')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                
                response1 = client.get('/content/test.md')
                assert 'Initial Content' in response1.get_data(as_text=True)
                
                # Update content
                with open(filepath, 'w') as f:
                    f.write('# Updated Content')
                
                response2 = client.get('/content/test.md')
                assert 'Updated Content' in response2.get_data(as_text=True)

    @pytest.mark.unit
    def test_removed_content_shows_error(self):
        """Test that removing content file results in 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test.md')
            
            with open(filepath, 'w') as f:
                f.write('# Test Content')
            
            with patch.dict('os.environ', {'CONTENT_DIR': tmpdir}):
                import app
                client = app.app.test_client()
                
                response1 = client.get('/content/test.md')
                assert response1.status_code == 200
                
                # Remove file
                os.remove(filepath)
                
                response2 = client.get('/content/test.md')
                assert response2.status_code == 404
