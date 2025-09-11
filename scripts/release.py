#!/usr/bin/env python3
"""Release management script for inspect-agents.

Handles version bumping, changelog updates, and release preparation.
"""

import argparse
import re
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path


def get_current_version() -> str:
    """Get current version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        raise FileNotFoundError("pyproject.toml not found")

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    return data["project"]["version"]


def update_version(new_version: str) -> None:
    """Update version in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    # Update version line
    updated_content = re.sub(r'^version = "[^"]+"', f'version = "{new_version}"', content, flags=re.MULTILINE)

    pyproject_path.write_text(updated_content)
    print(f"✅ Updated pyproject.toml version to {new_version}")


def update_readme_version(new_version: str) -> None:
    """Update version references in README.md."""
    readme_path = Path("README.md")
    if not readme_path.exists():
        return

    content = readme_path.read_text()

    # Update version line in project status section
    updated_content = re.sub(r"- Version: [0-9.]+ \(repo\)", f"- Version: {new_version} (repo)", content)

    readme_path.write_text(updated_content)
    print(f"✅ Updated README.md version to {new_version}")


def update_changelog(new_version: str) -> None:
    """Update CHANGELOG.md with new version entry."""
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        print("⚠️  CHANGELOG.md not found, skipping update")
        return

    content = changelog_path.read_text()
    today = datetime.now().strftime("%Y-%m-%d")

    # Replace [Unreleased] with new version and add new [Unreleased] section
    new_content = content.replace("## [Unreleased]", f"## [Unreleased]\n\n## [{new_version}] - {today}")

    # Update the links at the bottom
    if f"[{new_version}]:" not in new_content:
        # Add new version link before the last line
        lines = new_content.split("\n")
        last_link_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("[") and "]:" in line and "github.com" in line:
                last_link_idx = i

        if last_link_idx >= 0:
            new_link = f"[{new_version}]: https://github.com/cnm13ryan/inspect_agents/releases/tag/v{new_version}"
            lines.insert(last_link_idx + 1, new_link)
            new_content = "\n".join(lines)

    changelog_path.write_text(new_content)
    print(f"✅ Updated CHANGELOG.md with version {new_version}")


def validate_version(version: str) -> bool:
    """Validate version format (semantic versioning)."""
    pattern = r"^\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$"
    return bool(re.match(pattern, version))


def run_tests() -> bool:
    """Run tests to ensure everything works."""
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "-q", "tests/", "--tb=short"],
            env={"CI": "1", "NO_NETWORK": "1", "PYTHONPATH": "src:external/inspect_ai"},
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("✅ Tests passed")
            return True
        else:
            print(f"❌ Tests failed:\n{result.stdout}\n{result.stderr}")
            return False
    except FileNotFoundError:
        print("⚠️  uv not found, skipping tests")
        return True


def build_package() -> bool:
    """Build the package."""
    try:
        result = subprocess.run(["uv", "build"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Package built successfully")
            return True
        else:
            print(f"❌ Build failed:\n{result.stdout}\n{result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ uv not found")
        return False


def git_status_clean() -> bool:
    """Check if git working directory is clean."""
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        return result.stdout.strip() == ""
    except FileNotFoundError:
        print("⚠️  git not found")
        return True


def main():
    parser = argparse.ArgumentParser(description="Release management for inspect-agents")
    parser.add_argument("version", help="New version number (e.g., 0.1.0, 1.0.0-beta.1)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--skip-build", action="store_true", help="Skip building package")
    parser.add_argument("--force", action="store_true", help="Force release even with uncommitted changes")

    args = parser.parse_args()

    # Validate version format
    if not validate_version(args.version):
        print(f"❌ Invalid version format: {args.version}")
        print("Expected: X.Y.Z or X.Y.Z-{alpha,beta,rc}.N")
        sys.exit(1)

    # Check git status
    if not args.force and not git_status_clean():
        print("❌ Working directory has uncommitted changes")
        print("Commit your changes or use --force to proceed")
        sys.exit(1)

    current_version = get_current_version()
    print(f"Current version: {current_version}")
    print(f"New version: {args.version}")

    # Confirm the release
    if not args.force:
        response = input("Proceed with release? [y/N]: ")
        if response.lower() not in ["y", "yes"]:
            print("Release cancelled")
            sys.exit(0)

    # Update version files
    update_version(args.version)
    update_readme_version(args.version)
    update_changelog(args.version)

    # Run tests
    if not args.skip_tests:
        if not run_tests():
            print("❌ Tests failed, aborting release")
            sys.exit(1)

    # Build package
    if not args.skip_build:
        if not build_package():
            print("❌ Build failed, aborting release")
            sys.exit(1)

    print(f"\n✅ Release {args.version} prepared successfully!")
    print("\nNext steps:")
    print("1. Review the changes:")
    print("   git diff")
    print("2. Commit the changes:")
    print(f"   git add -A && git commit -m 'chore: bump version to {args.version}'")
    print("3. Create and push the tag:")
    print(f"   git tag v{args.version} && git push origin v{args.version}")
    print("4. The GitHub workflow will automatically publish to PyPI")


if __name__ == "__main__":
    main()
