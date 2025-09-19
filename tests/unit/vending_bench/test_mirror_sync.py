"""Unit tests for mirror sync functionality."""

import json
import subprocess

# Import the mirror sync module
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tools"))
from mirror_sync import MirrorSync, MirrorSyncError


class TestMirrorSyncInit:
    """Test MirrorSync initialization."""

    def test_init_with_valid_source(self, tmp_path):
        """Test initialization with valid source directory."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        mirror_sync = MirrorSync(str(source_dir), str(target_dir))

        assert mirror_sync.source_path == source_dir.resolve()
        assert mirror_sync.target_path == target_dir.resolve()
        assert not mirror_sync.dry_run

    def test_init_with_missing_source(self, tmp_path):
        """Test initialization with missing source directory."""
        source_dir = tmp_path / "missing"
        target_dir = tmp_path / "target"

        with pytest.raises(MirrorSyncError, match="Source directory does not exist"):
            MirrorSync(str(source_dir), str(target_dir))

    def test_init_dry_run_mode(self, tmp_path):
        """Test initialization with dry run mode."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        mirror_sync = MirrorSync(str(source_dir), str(target_dir), dry_run=True)

        assert mirror_sync.dry_run


class TestGitInfo:
    """Test git information retrieval."""

    @patch("subprocess.check_output")
    def test_get_git_info_success(self, mock_subprocess, tmp_path):
        """Test successful git info retrieval."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Mock git command outputs
        mock_subprocess.side_effect = [
            "abc123def456\n",  # commit SHA
            "2023-09-19 10:30:00 +0000\n",  # commit date
            "main\n",  # branch
            "",  # status (no changes)
        ]

        mirror_sync = MirrorSync(str(source_dir), str(tmp_path / "target"))
        git_info = mirror_sync.get_git_info()

        expected_info = {
            "commit_sha": "abc123def456",
            "commit_date": "2023-09-19 10:30:00 +0000",
            "branch": "main",
            "has_uncommitted_changes": False,
            "status": None,
        }

        assert git_info == expected_info

    @patch("subprocess.check_output")
    def test_get_git_info_with_uncommitted_changes(self, mock_subprocess, tmp_path):
        """Test git info retrieval with uncommitted changes."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Mock git command outputs
        mock_subprocess.side_effect = [
            "abc123def456\n",  # commit SHA
            "2023-09-19 10:30:00 +0000\n",  # commit date
            "feature-branch\n",  # branch
            "M  modified_file.py\n?? new_file.py\n",  # status with changes
        ]

        mirror_sync = MirrorSync(str(source_dir), str(tmp_path / "target"))
        git_info = mirror_sync.get_git_info()

        assert git_info["has_uncommitted_changes"] is True
        assert git_info["status"] == "M  modified_file.py\n?? new_file.py"
        assert git_info["branch"] == "feature-branch"

    @patch("subprocess.check_output")
    def test_get_git_info_failure(self, mock_subprocess, tmp_path):
        """Test git info retrieval failure."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Mock subprocess failure
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "git")

        mirror_sync = MirrorSync(str(source_dir), str(tmp_path / "target"))

        with pytest.raises(MirrorSyncError, match="Failed to get git information"):
            mirror_sync.get_git_info()


class TestContentHash:
    """Test content hash calculation."""

    def test_calculate_content_hash_empty_directory(self, tmp_path):
        """Test content hash calculation for empty directory."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        mirror_sync = MirrorSync(str(source_dir), str(tmp_path / "target"))
        content_hash = mirror_sync.calculate_content_hash()

        # Hash should be deterministic for empty directory
        assert isinstance(content_hash, str)
        assert len(content_hash) == 64  # SHA256 hex digest

    def test_calculate_content_hash_with_files(self, tmp_path):
        """Test content hash calculation with files."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create test files
        (source_dir / "file1.py").write_text("print('hello')")
        (source_dir / "subdir").mkdir()
        (source_dir / "subdir" / "file2.py").write_text("print('world')")

        mirror_sync = MirrorSync(str(source_dir), str(tmp_path / "target"))
        content_hash = mirror_sync.calculate_content_hash()

        assert isinstance(content_hash, str)
        assert len(content_hash) == 64

        # Hash should be different with different content
        (source_dir / "file1.py").write_text("print('modified')")
        modified_hash = mirror_sync.calculate_content_hash()
        assert modified_hash != content_hash

    def test_calculate_content_hash_excludes_patterns(self, tmp_path):
        """Test content hash excludes certain file patterns."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create files that should be included
        (source_dir / "included.py").write_text("included")

        # Create files that should be excluded
        (source_dir / "__pycache__").mkdir()
        (source_dir / "__pycache__" / "cache.pyc").write_text("cache")
        (source_dir / "file.pyc").write_text("compiled")
        (source_dir / ".DS_Store").write_text("system")

        mirror_sync = MirrorSync(str(source_dir), str(tmp_path / "target"))
        content_hash = mirror_sync.calculate_content_hash()

        # Create another directory with only the included file
        source_dir2 = tmp_path / "source2"
        source_dir2.mkdir()
        (source_dir2 / "included.py").write_text("included")

        mirror_sync2 = MirrorSync(str(source_dir2), str(tmp_path / "target2"))
        content_hash2 = mirror_sync2.calculate_content_hash()

        # Hashes should be the same (excluded files don't affect hash)
        assert content_hash == content_hash2


class TestManifestCreation:
    """Test mirror manifest creation."""

    def test_create_manifest(self, tmp_path):
        """Test manifest creation with valid data."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        mirror_sync = MirrorSync(str(source_dir), str(tmp_path / "target"))

        git_info = {
            "commit_sha": "abc123",
            "commit_date": "2023-09-19 10:30:00",
            "branch": "main",
            "has_uncommitted_changes": False,
            "status": None,
        }
        content_hash = "hash123"

        manifest = mirror_sync.create_manifest(git_info, content_hash)

        assert manifest["mirror_version"] == "1.0"
        assert "sync_timestamp" in manifest
        assert manifest["source_info"]["path"] == str(source_dir.resolve())
        assert manifest["source_info"]["content_hash"] == content_hash
        assert manifest["git_info"] == git_info
        assert "package_structure" in manifest
        assert "entry_points" in manifest


class TestFileCopying:
    """Test file copying operations."""

    def test_copy_source_files(self, tmp_path):
        """Test copying source files to target."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        # Create source files
        (source_dir / "file1.py").write_text("source content")
        (source_dir / "subdir").mkdir()
        (source_dir / "subdir" / "file2.py").write_text("nested content")

        mirror_sync = MirrorSync(str(source_dir), str(target_dir))
        mirror_sync.copy_source_files()

        # Check files were copied
        assert (target_dir / "vending_bench" / "file1.py").exists()
        assert (target_dir / "vending_bench" / "file1.py").read_text() == "source content"
        assert (target_dir / "vending_bench" / "subdir" / "file2.py").exists()
        assert (target_dir / "vending_bench" / "subdir" / "file2.py").read_text() == "nested content"

    def test_copy_source_files_dry_run(self, tmp_path):
        """Test copying source files in dry run mode."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        # Create source files
        (source_dir / "file1.py").write_text("source content")

        mirror_sync = MirrorSync(str(source_dir), str(target_dir), dry_run=True)
        mirror_sync.copy_source_files()

        # No files should be copied in dry run
        assert not (target_dir / "vending_bench").exists()

    def test_copy_tests(self, tmp_path):
        """Test copying test files."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        # Create mock test directories structure
        tests_base = source_dir.parent.parent / "tests"
        unit_tests = tests_base / "unit" / "vending_bench"
        integration_tests = tests_base / "integration" / "vending_bench"

        unit_tests.mkdir(parents=True)
        integration_tests.mkdir(parents=True)

        # Create test files
        (unit_tests / "test_unit.py").write_text("unit test")
        (integration_tests / "test_integration.py").write_text("integration test")

        mirror_sync = MirrorSync(str(source_dir), str(target_dir))
        mirror_sync.copy_tests()

        # Check test files were copied
        assert (target_dir / "tests" / "unit" / "test_unit.py").exists()
        assert (target_dir / "tests" / "integration" / "test_integration.py").exists()
        assert (target_dir / "tests" / "run_tests.py").exists()


class TestMirrorReadme:
    """Test mirror README creation."""

    def test_create_mirror_readme(self, tmp_path):
        """Test creation of mirror README."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        git_info = {"commit_sha": "abc123def456", "branch": "main"}

        mirror_sync = MirrorSync(str(source_dir), str(target_dir))
        mirror_sync.create_mirror_readme(git_info)

        readme_path = target_dir / "README.md"
        assert readme_path.exists()

        readme_content = readme_path.read_text()
        assert "Vending-Bench Mirror" in readme_content
        assert "abc123de" in readme_content  # Shortened commit SHA
        assert "main" in readme_content
        assert "Quick Start" in readme_content
        assert "uv sync" in readme_content

    def test_create_mirror_readme_dry_run(self, tmp_path):
        """Test creation of mirror README in dry run mode."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        git_info = {"commit_sha": "abc123", "branch": "main"}

        mirror_sync = MirrorSync(str(source_dir), str(target_dir), dry_run=True)
        mirror_sync.create_mirror_readme(git_info)

        # No README should be created in dry run
        assert not (target_dir / "README.md").exists()


class TestPackageStructure:
    """Test package structure creation."""

    def test_create_package_structure(self, tmp_path):
        """Test creation of package structure."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        mirror_sync = MirrorSync(str(source_dir), str(target_dir))
        mirror_sync.create_package_structure()

        assert target_dir.exists()
        assert (target_dir / "docs").exists()
        assert (target_dir / "docs" / "DEVELOPMENT.md").exists()

        dev_guide = (target_dir / "docs" / "DEVELOPMENT.md").read_text()
        assert "Development Guide" in dev_guide
        assert "uv sync" in dev_guide


class TestFullSync:
    """Test complete sync process."""

    @patch("subprocess.check_output")
    def test_sync_success(self, mock_subprocess, tmp_path):
        """Test successful complete sync."""
        # Setup
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        # Create source content
        (source_dir / "main.py").write_text("main content")
        (source_dir / "README.md").write_text("source readme")

        # Mock git commands
        mock_subprocess.side_effect = [
            "abc123\n",  # commit SHA
            "2023-09-19 10:30:00\n",  # commit date
            "main\n",  # branch
            "",  # status
        ]

        # Create mock test directories (needed for copy_tests)
        tests_base = source_dir.parent.parent / "tests"
        unit_tests = tests_base / "unit" / "vending_bench"
        unit_tests.mkdir(parents=True, exist_ok=True)
        (unit_tests / "test_example.py").write_text("test")

        # Run sync
        mirror_sync = MirrorSync(str(source_dir), str(target_dir))
        report = mirror_sync.sync()

        # Verify results
        assert report["status"] == "success"
        assert not report["dry_run"]
        assert "content_hash" in report
        assert "git_info" in report

        # Check files were created
        assert (target_dir / "vending_bench" / "main.py").exists()
        assert (target_dir / "README.md").exists()
        assert (target_dir / "mirror-manifest.json").exists()
        assert (target_dir / "docs" / "DEVELOPMENT.md").exists()
        assert (target_dir / "tests" / "run_tests.py").exists()

        # Check manifest content
        manifest_path = target_dir / "mirror-manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert manifest["mirror_version"] == "1.0"
        assert manifest["git_info"]["commit_sha"] == "abc123"

    @patch("subprocess.check_output")
    def test_sync_dry_run(self, mock_subprocess, tmp_path):
        """Test sync in dry run mode."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        (source_dir / "main.py").write_text("content")

        # Mock git commands
        mock_subprocess.side_effect = [
            "abc123\n",  # commit SHA
            "2023-09-19 10:30:00\n",  # commit date
            "main\n",  # branch
            "",  # status
        ]

        mirror_sync = MirrorSync(str(source_dir), str(target_dir), dry_run=True)
        report = mirror_sync.sync()

        assert report["status"] == "success"
        assert report["dry_run"] is True

        # No files should be created
        assert not (target_dir / "vending_bench").exists()
        assert not (target_dir / "README.md").exists()
        assert not (target_dir / "mirror-manifest.json").exists()


class TestReleaseNotesValidation:
    """Test release note validation integration."""

    @patch("subprocess.check_output")
    def test_validation_runs_when_release_version_set(self, mock_check_output, tmp_path, monkeypatch):
        """Ensure validator is invoked with expected arguments."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        (source_dir / "main.py").write_text("main content")

        mock_check_output.side_effect = [
            "abc123\n",
            "2025-09-19 12:00:00\n",
            "main\n",
            "",
        ]

        captured: dict[str, object] = {}

        def fake_run(cmd, capture_output, text):
            captured["cmd"] = cmd
            captured["capture_output"] = capture_output
            captured["text"] = text
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        mirror_sync = MirrorSync(
            str(source_dir),
            str(target_dir),
            release_version="mirror-v1.2.3",
        )
        mirror_sync.sync()

        assert captured["cmd"][2] == "validate"
        assert "mirror-v1.2.3" in captured["cmd"]
        assert str(target_dir / "mirror-manifest.json") in captured["cmd"]

    @patch("subprocess.check_output")
    def test_validation_failure_raises(self, mock_check_output, tmp_path, monkeypatch):
        """Validator failures should surface as MirrorSyncError."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        (source_dir / "main.py").write_text("main content")

        mock_check_output.side_effect = [
            "abc123\n",
            "2025-09-19 12:00:00\n",
            "main\n",
            "",
        ]

        def failing_run(cmd, capture_output, text):
            return subprocess.CompletedProcess(cmd, 1, stdout="out", stderr="err")

        monkeypatch.setattr(subprocess, "run", failing_run)

        mirror_sync = MirrorSync(
            str(source_dir),
            str(target_dir),
            release_version="mirror-v1.2.3",
        )

        with pytest.raises(MirrorSyncError, match="Release notes validation failed"):
            mirror_sync.sync()


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_missing_source_directory(self, tmp_path):
        """Test handling of missing source directory."""
        source_dir = tmp_path / "missing"
        target_dir = tmp_path / "target"

        with pytest.raises(MirrorSyncError, match="Source directory does not exist"):
            MirrorSync(str(source_dir), str(target_dir))

    @patch("subprocess.check_output")
    def test_git_info_failure_propagates(self, mock_subprocess, tmp_path):
        """Test that git info failures are properly propagated."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        mock_subprocess.side_effect = subprocess.CalledProcessError(128, "git")

        mirror_sync = MirrorSync(str(source_dir), str(target_dir))

        with pytest.raises(MirrorSyncError, match="Failed to get git information"):
            mirror_sync.sync()


if __name__ == "__main__":
    pytest.main([__file__])
