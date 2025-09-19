#!/usr/bin/env python3
"""Tests for mirror repository release notes functionality."""

import json

# Add mirror-repo/scripts to path for imports
import sys
import tempfile
from pathlib import Path

import pytest

script_dir = Path(__file__).parent.parent.parent.parent / "mirror-repo" / "scripts"
sys.path.insert(0, str(script_dir))

from generate_release_notes import (  # noqa: E402
    generate_release_notes,
    get_manifest_hash,
    get_release_notes_dir,
    get_template_path,
    validate_release_notes,
)


class TestReleaseNotesGeneration:
    """Test release notes generation functionality."""

    def test_template_exists(self):
        """Test that the release notes template exists."""
        template_path = get_template_path()
        assert template_path.exists(), f"Template not found at {template_path}"

    def test_generate_basic_release_notes(self):
        """Test basic release notes generation without manifest."""
        version = "mirror-v1.0.0"
        content = generate_release_notes(version)

        assert version in content
        assert "### Summary" in content
        assert "### Added" in content
        assert "### Changed" in content
        assert "### Fixed" in content
        assert "### Technical Details" in content

        # Should not contain template placeholders for version
        assert "mirror-vX.Y.Z" not in content

        # Should contain source commit placeholder for user to replace
        assert "PLACEHOLDER_SOURCE_COMMIT" in content

    def test_generate_with_manifest(self):
        """Test release notes generation with manifest file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            manifest_data = {
                "version": "1.0.0",
                "timestamp": "2024-01-01T00:00:00Z",
                "source_commit": "abc123",
                "files": [],
            }
            json.dump(manifest_data, f)
            manifest_path = Path(f.name)

        try:
            version = "mirror-v1.0.0"
            content = generate_release_notes(version, manifest_path)

            # Should contain manifest hash
            expected_hash = get_manifest_hash(manifest_path)
            assert expected_hash in content
            assert "PLACEHOLDER_MANIFEST_SHA256" not in content

        finally:
            manifest_path.unlink()

    def test_get_manifest_hash(self):
        """Test manifest hash calculation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            test_data = {"test": "data"}
            json.dump(test_data, f)
            manifest_path = Path(f.name)

        try:
            hash_value = get_manifest_hash(manifest_path)
            assert len(hash_value) == 64  # SHA256 hex length
            assert isinstance(hash_value, str)

            # Same file should produce same hash
            hash_value2 = get_manifest_hash(manifest_path)
            assert hash_value == hash_value2

        finally:
            manifest_path.unlink()

    def test_get_manifest_hash_missing_file(self):
        """Test manifest hash with missing file."""
        nonexistent_path = Path("/nonexistent/file.json")

        with pytest.raises(FileNotFoundError):
            get_manifest_hash(nonexistent_path)


class TestReleaseNotesValidation:
    """Test release notes validation functionality."""

    def create_test_release_notes(self, content: str) -> Path:
        """Create a temporary release notes file for testing."""
        release_notes_dir = get_release_notes_dir()
        release_notes_dir.mkdir(exist_ok=True)

        test_file = release_notes_dir / "test-release.md"
        test_file.write_text(content)
        return test_file

    def test_validate_missing_file(self):
        """Test validation of missing release notes file."""
        result = validate_release_notes("nonexistent-version")
        assert result is False

    def test_validate_with_placeholders(self):
        """Test validation fails when placeholders are not replaced."""
        content = """
        # Release Notes

        Version: mirror-vX.Y.Z
        Date: YYYY-MM-DD
        Source: PLACEHOLDER_SOURCE_COMMIT
        Manifest: PLACEHOLDER_MANIFEST_SHA256

        ### Summary
        Test release

        ### Added
        - New feature

        ### Changed
        - Updated component

        ### Fixed
        - Bug fix

        ### Technical Details
        - Source Commit: PLACEHOLDER_SOURCE_COMMIT
        """

        test_file = self.create_test_release_notes(content)

        try:
            result = validate_release_notes("test-release")
            assert result is False
        finally:
            test_file.unlink()

    def test_validate_complete_release_notes(self):
        """Test validation passes for complete release notes."""
        content = """
        # Release Notes

        ## [test-release] - 2024-01-01

        ### Summary
        Initial release of vending bench mirror

        ### Added
        - New vending bench implementation
        - Documentation and examples

        ### Changed
        - Updated configuration handling

        ### Fixed
        - Fixed import paths

        ### Technical Details
        - Source Commit: abc123def456
        - Manifest SHA256: 567890abcdef
        - Release Date: 2024-01-01
        """

        test_file = self.create_test_release_notes(content)

        try:
            result = validate_release_notes("test-release")
            assert result is True
        finally:
            test_file.unlink()

    def test_validate_with_manifest_hash(self):
        """Test validation with manifest hash checking."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            manifest_data = {"version": "1.0.0", "files": []}
            json.dump(manifest_data, f)
            manifest_path = Path(f.name)

        expected_hash = get_manifest_hash(manifest_path)

        content = f"""
        # Release Notes

        ## [test-release] - 2024-01-01

        ### Summary
        Test release with manifest

        ### Added
        - New feature

        ### Changed
        - Updated component

        ### Fixed
        - Bug fix

        ### Technical Details
        - Source Commit: abc123def456
        - Manifest SHA256: {expected_hash}
        - Release Date: 2024-01-01
        """

        test_file = self.create_test_release_notes(content)

        try:
            result = validate_release_notes("test-release", manifest_path)
            assert result is True
        finally:
            test_file.unlink()
            manifest_path.unlink()

    def test_validate_with_source_commit_requirement(self):
        """Test validation with required source commit."""
        required_commit = "abc123def456"

        content = f"""
        # Release Notes

        ## [test-release] - 2024-01-01

        ### Summary
        Test release with source commit

        ### Added
        - New feature

        ### Changed
        - Updated component

        ### Fixed
        - Bug fix

        ### Technical Details
        - Source Commit: {required_commit}
        - Manifest SHA256: 567890abcdef
        - Release Date: 2024-01-01
        """

        test_file = self.create_test_release_notes(content)

        try:
            result = validate_release_notes("test-release", require_source_commit=required_commit)
            assert result is True

            # Test with wrong commit
            result = validate_release_notes("test-release", require_source_commit="wrong_commit")
            assert result is False

        finally:
            test_file.unlink()

    def test_validate_missing_sections(self):
        """Test validation fails when required sections are missing."""
        content = """
        # Release Notes

        ## [mirror-v1.0.0] - 2024-01-01

        ### Summary
        Incomplete release notes

        ### Added
        - New feature

        # Missing other required sections
        """

        test_file = self.create_test_release_notes(content)

        try:
            result = validate_release_notes("test-release")
            assert result is False
        finally:
            test_file.unlink()


class TestIntegration:
    """Integration tests for the release notes system."""

    def test_generate_and_validate_workflow(self):
        """Test the complete generate -> edit -> validate workflow."""
        version = "mirror-v1.2.3"

        # Generate release notes
        content = generate_release_notes(version)

        # Simulate manual editing by replacing placeholders
        edited_content = content.replace("PLACEHOLDER_SOURCE_COMMIT", "abc123def456")
        edited_content = edited_content.replace("PLACEHOLDER_MANIFEST_SHA256", "567890abcdef")

        # Add some actual content
        edited_content = edited_content.replace(
            "<!-- Provide a concise summary", "Initial mirror release with core functionality"
        )
        edited_content = edited_content.replace("-", "- Added vending bench core implementation", 1)

        # Write to release notes directory
        release_notes_dir = get_release_notes_dir()
        release_notes_dir.mkdir(exist_ok=True)
        release_file = release_notes_dir / f"{version}.md"
        release_file.write_text(edited_content)

        try:
            # Validate the edited release notes
            result = validate_release_notes(version)
            assert result is True

        finally:
            if release_file.exists():
                release_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
