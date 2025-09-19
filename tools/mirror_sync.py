#!/usr/bin/env python3
"""
Mirror sync tool for Vending-Bench.

Packages artifacts from examples/vending_bench for deployment to the external mirror repository.
This tool prepares the mirror package structure that the CI pipeline will sync to the public mirror.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RELEASE_NOTES_DIR = REPO_ROOT / "mirror-repo" / "release-notes"
RELEASE_NOTES_SCRIPT = REPO_ROOT / "mirror-repo" / "scripts" / "generate_release_notes.py"


class MirrorSyncError(Exception):
    """Errors related to mirror synchronization."""

    pass


class MirrorSync:
    """Handles packaging and preparation of mirror artifacts."""

    def __init__(
        self,
        source_dir: str,
        target_dir: str,
        dry_run: bool = False,
        release_version: str | None = None,
        release_notes_dir: str | Path | None = None,
    ) -> None:
        """
        Initialize mirror sync.

        Args:
            source_dir: Source directory to mirror (e.g., "examples/vending_bench")
            target_dir: Target directory for mirror preparation
            dry_run: If True, only show what would be done
            release_version: Optional release tag (mirror-vX.Y.Z) to validate notes for
            release_notes_dir: Optional override for release notes directory
        """
        self.source_path = Path(source_dir).resolve()
        self.target_path = Path(target_dir).resolve()
        self.dry_run = dry_run
        self.release_version = release_version
        self.release_notes_dir = Path(release_notes_dir).resolve() if release_notes_dir else None

        if not self.source_path.exists():
            raise MirrorSyncError(f"Source directory does not exist: {self.source_path}")

    def get_git_info(self) -> dict[str, Any]:
        """Get current git commit information."""
        try:
            # Get current commit SHA
            commit_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True, cwd=self.source_path.parent.parent
            ).strip()

            # Get commit date
            commit_date = subprocess.check_output(
                ["git", "show", "-s", "--format=%ci", "HEAD"], text=True, cwd=self.source_path.parent.parent
            ).strip()

            # Get current branch
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"], text=True, cwd=self.source_path.parent.parent
            ).strip()

            # Check for uncommitted changes
            status = subprocess.check_output(
                ["git", "status", "--porcelain"], text=True, cwd=self.source_path.parent.parent
            ).strip()

            return {
                "commit_sha": commit_sha,
                "commit_date": commit_date,
                "branch": branch,
                "has_uncommitted_changes": bool(status),
                "status": status if status else None,
            }

        except subprocess.CalledProcessError as e:
            raise MirrorSyncError(f"Failed to get git information: {e}")

    def calculate_content_hash(self) -> str:
        """Calculate hash of source content for change detection."""
        hasher = hashlib.sha256()

        # Get all files in source directory, excluding common non-essential files
        exclude_patterns = {"__pycache__", ".pytest_cache", "*.pyc", ".DS_Store", "*.egg-info"}

        def should_include(path: Path) -> bool:
            """Check if file should be included in hash calculation."""
            for exclude in exclude_patterns:
                if exclude.startswith("*"):
                    if path.name.endswith(exclude[1:]):
                        return False
                elif exclude in str(path):
                    return False
            return True

        # Sort files for consistent ordering
        files = sorted([f for f in self.source_path.rglob("*") if f.is_file() and should_include(f)])

        for file_path in files:
            # Include relative path in hash
            rel_path = file_path.relative_to(self.source_path)
            hasher.update(str(rel_path).encode())

            # Include file content in hash
            try:
                with open(file_path, "rb") as f:
                    hasher.update(f.read())
            except (OSError, UnicodeDecodeError) as e:
                # Skip files that can't be read
                print(f"Warning: Skipping file in hash calculation: {file_path} ({e})")
                continue

        return hasher.hexdigest()

    def create_manifest(self, git_info: dict[str, Any], content_hash: str) -> dict[str, Any]:
        """Create mirror manifest with metadata."""
        return {
            "mirror_version": "1.0",
            "sync_timestamp": datetime.now(UTC).isoformat(),
            "source_info": {"path": str(self.source_path), "content_hash": content_hash},
            "git_info": git_info,
            "package_structure": {
                "vending_bench/": "Main benchmark implementation",
                "tests/": "Test suite",
                "docs/": "Documentation and usage guides",
                "ci/": "Continuous integration workflows",
            },
            "entry_points": {
                "main": "vending_bench/run.py",
                "tests": "pytest tests/",
                "examples": "vending_bench/README.md",
            },
        }

    def copy_source_files(self) -> None:
        """Copy source files to target directory."""
        vending_bench_target = self.target_path / "vending_bench"

        if self.dry_run:
            print(f"[DRY RUN] Would copy {self.source_path} -> {vending_bench_target}")
            return

        # Remove target if it exists
        if vending_bench_target.exists():
            shutil.rmtree(vending_bench_target)

        # Copy source directory
        shutil.copytree(
            self.source_path, vending_bench_target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
        )

        print(f"Copied source files to {vending_bench_target}")

    def copy_tests(self) -> None:
        """Copy relevant test files."""
        tests_source = self.source_path.parent.parent / "tests" / "unit" / "vending_bench"
        integration_tests = self.source_path.parent.parent / "tests" / "integration" / "vending_bench"
        tests_target = self.target_path / "tests"

        if self.dry_run:
            print(f"[DRY RUN] Would copy test files from {tests_source} and {integration_tests}")
            return

        # Remove target if it exists
        if tests_target.exists():
            shutil.rmtree(tests_target)

        tests_target.mkdir(parents=True)

        # Copy unit tests
        if tests_source.exists():
            shutil.copytree(tests_source, tests_target / "unit", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            print(f"Copied unit tests to {tests_target / 'unit'}")

        # Copy integration tests
        if integration_tests.exists():
            shutil.copytree(
                integration_tests, tests_target / "integration", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
            print(f"Copied integration tests to {tests_target / 'integration'}")

        # Create test runner script
        test_runner = tests_target / "run_tests.py"
        with open(test_runner, "w") as f:
            f.write("""#!/usr/bin/env python3
\"\"\"Test runner for vending-bench mirror.\"\"\"

import subprocess
import sys
from pathlib import Path

def main():
    \"\"\"Run the test suite.\"\"\"
    tests_dir = Path(__file__).parent

    # Run unit tests
    print("Running unit tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", "-v",
        str(tests_dir / "unit")
    ], cwd=tests_dir.parent)

    if result.returncode != 0:
        print("Unit tests failed!")
        return result.returncode

    # Run integration tests
    print("Running integration tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", "-v",
        str(tests_dir / "integration")
    ], cwd=tests_dir.parent)

    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
""")
        test_runner.chmod(0o755)

    def create_mirror_readme(self, git_info: dict[str, Any]) -> None:
        """Create README for mirror repository."""
        readme_content = f"""# Vending-Bench Mirror

This is a public mirror of the Vending-Bench long-horizon agent benchmark from the `inspect_agents` repository.

## Sync Information

- **Source Repository**: `inspect_agents` (private)
- **Source Commit**: `{git_info["commit_sha"][:8]}`
- **Source Branch**: `{git_info["branch"]}`
- **Sync Date**: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M %Z")}

## Quick Start

### Prerequisites
- Python 3.12+
- UV package manager
- Inspect AI framework

### Installation

```bash
# Install dependencies
uv sync

# Run basic test
python tests/run_tests.py

# Run benchmark
python vending_bench/run.py --episodes 1 --max-messages 100
```

## Documentation

See `vending_bench/README.md` for comprehensive documentation, including:
- Architecture overview
- Configuration options
- Evaluation metrics
- Development guide
- Troubleshooting

## Repository Structure

```
├── vending_bench/          # Main benchmark implementation
│   ├── README.md          # Detailed documentation
│   ├── run.py             # Main entry point
│   ├── env.py             # Environment simulation
│   ├── tools.py           # Agent tools
│   └── ...                # Additional modules
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── run_tests.py       # Test runner
├── ci/                    # CI configuration
└── docs/                  # Additional documentation
```

## Release Process

This mirror follows semantic versioning with tags in the format `mirror-v<major>.<minor>.<patch>`.

- **Patch releases**: Bug fixes, documentation updates
- **Minor releases**: New features, tool additions, backwards-compatible changes
- **Major releases**: Breaking changes, major architectural updates

## Issues and Contributions

This is a read-only mirror. For issues, feature requests, or contributions:

1. **Issues**: Open issues in this repository for mirror-specific problems
2. **Feature Requests**: Discuss in GitHub Discussions
3. **Contributions**: Contributions should be made to the upstream `inspect_agents` repository

## License

See the upstream repository for license information.

## Upstream Repository

The source code for this benchmark is maintained in the `inspect_agents` repository. This mirror provides public access to stable releases and documentation.

### Sync Status

The mirror sync process:
1. Detects changes in the upstream `examples/vending_bench/` directory
2. Runs smoke tests to validate functionality
3. Updates mirror content and creates release tags
4. Publishes release notes with change summaries

### Mirror Automation

The mirror is updated automatically via GitHub Actions when:
- New commits are pushed to relevant upstream branches
- Manual sync is triggered via workflow dispatch
- Scheduled weekly sync runs (Sundays at 00:00 UTC)
"""

        if self.dry_run:
            print("[DRY RUN] Would create mirror README.md")
            return

        readme_path = self.target_path / "README.md"
        with open(readme_path, "w") as f:
            f.write(readme_content)

        print(f"Created mirror README at {readme_path}")

    def create_package_structure(self) -> None:
        """Create the full mirror package structure."""
        if self.dry_run:
            print("[DRY RUN] Would create package structure")
            return

        # Ensure target directory exists
        self.target_path.mkdir(parents=True, exist_ok=True)

        # Create docs directory
        docs_dir = self.target_path / "docs"
        docs_dir.mkdir(exist_ok=True)

        # Create basic docs
        with open(docs_dir / "DEVELOPMENT.md", "w") as f:
            f.write("""# Development Guide

## Local Development

### Setup
```bash
uv sync
```

### Running Tests
```bash
python tests/run_tests.py
```

### Running Benchmark
```bash
python vending_bench/run.py --help
```

## Architecture

See `vending_bench/README.md` for detailed architecture documentation.
""")

        print(f"Created package structure in {self.target_path}")

    def validate_release_notes(self, git_info: dict[str, Any], manifest_path: Path) -> None:
        """Run release-note validation if a release version is configured."""
        if not self.release_version:
            return

        if self.dry_run:
            print(f"[DRY RUN] Would validate release notes for {self.release_version}")
            return

        script_path = RELEASE_NOTES_SCRIPT
        if not script_path.exists():
            raise MirrorSyncError(f"Release notes validator not found: {script_path}")

        notes_dir = self.release_notes_dir or DEFAULT_RELEASE_NOTES_DIR
        if not notes_dir.exists():
            raise MirrorSyncError(f"Release notes directory not found: {notes_dir}")

        if not manifest_path.exists():
            raise MirrorSyncError(f"Manifest not found for validation: {manifest_path}")

        cmd = [
            sys.executable,
            str(script_path),
            "validate",
            "--version",
            self.release_version,
            "--notes-dir",
            str(notes_dir),
            "--manifest-path",
            str(manifest_path),
            "--require-source-commit",
            git_info["commit_sha"],
        ]

        print(f"Validating release notes for {self.release_version}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            details = "\n".join(filter(None, [stdout, stderr]))
            message = "Release notes validation failed"
            if details:
                message = f"{message}\n{details}"
            raise MirrorSyncError(message)

    def sync(self) -> dict[str, Any]:
        """
        Perform the complete mirror sync process.

        Returns:
            Sync report with metadata and status
        """
        print(f"Starting mirror sync: {self.source_path} -> {self.target_path}")

        # Get git information
        git_info = self.get_git_info()

        # Calculate content hash
        content_hash = self.calculate_content_hash()

        # Create manifest
        manifest = self.create_manifest(git_info, content_hash)

        # Create package structure
        self.create_package_structure()

        # Copy source files
        self.copy_source_files()

        # Copy tests
        self.copy_tests()

        # Create mirror README
        self.create_mirror_readme(git_info)

        # Write manifest
        manifest_path = self.target_path / "mirror-manifest.json"
        if not self.dry_run:
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            print(f"Created manifest at {manifest_path}")
        else:
            print("[DRY RUN] Would create mirror-manifest.json")

        # Validate release notes if requested
        self.validate_release_notes(git_info, manifest_path)

        # Create sync report
        report = {
            "status": "success",
            "source_path": str(self.source_path),
            "target_path": str(self.target_path),
            "content_hash": content_hash,
            "git_info": git_info,
            "dry_run": self.dry_run,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if self.dry_run:
            print("\n[DRY RUN] Mirror sync completed (no changes made)")
        else:
            print("\nMirror sync completed successfully")
            print(f"Target directory: {self.target_path}")
            print(f"Content hash: {content_hash[:12]}...")

        return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Mirror sync tool for Vending-Bench")
    parser.add_argument(
        "--source",
        default="examples/vending_bench",
        help="Source directory to mirror (default: examples/vending_bench)",
    )
    parser.add_argument(
        "--target", default="mirror-prep", help="Target directory for mirror preparation (default: mirror-prep)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--output-manifest", help="Write sync report to specified file")
    parser.add_argument("--release-version", help="Release tag to validate notes for (mirror-vX.Y.Z)")
    parser.add_argument("--release-notes-dir", help="Override release notes directory")

    args = parser.parse_args()

    release_version = args.release_version
    if not release_version:
        env_tag = (
            os.environ.get("MIRROR_RELEASE_TAG") or os.environ.get("GITHUB_REF_NAME") or os.environ.get("GITHUB_REF")
        )
        if env_tag:
            candidate = env_tag.split("/")[-1]
            if candidate.startswith("mirror-v"):
                release_version = candidate

    try:
        # Create mirror sync instance
        mirror_sync = MirrorSync(
            args.source,
            args.target,
            dry_run=args.dry_run,
            release_version=release_version,
            release_notes_dir=args.release_notes_dir,
        )

        # Perform sync
        report = mirror_sync.sync()

        # Output manifest if requested
        if args.output_manifest:
            with open(args.output_manifest, "w") as f:
                json.dump(report, f, indent=2)
            print(f"Sync report written to {args.output_manifest}")

        return 0

    except MirrorSyncError as e:
        print(f"Mirror sync failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
