#!/usr/bin/env python3
"""
Release notes generation and validation for mirror repository.

This script generates release notes from templates and validates them against
manifest files and source commits.
"""

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path


def get_template_path() -> Path:
    """Get path to release notes template."""
    script_dir = Path(__file__).parent
    return script_dir.parent / "release-notes" / "_template.md"


def get_release_notes_dir() -> Path:
    """Get path to release notes directory."""
    script_dir = Path(__file__).parent
    return script_dir.parent / "release-notes"


def get_manifest_hash(manifest_path: Path) -> str:
    """Calculate SHA256 hash of manifest file."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    with open(manifest_path, "rb") as f:
        content = f.read()

    return hashlib.sha256(content).hexdigest()


def generate_release_notes(version: str, manifest_path: Path | None = None) -> str:
    """Generate release notes from template."""
    template_path = get_template_path()

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    # Read template
    with open(template_path) as f:
        template_content = f.read()

    # Replace version placeholder
    content = template_content.replace("mirror-vX.Y.Z", version)

    # Replace date placeholder
    today = datetime.now().strftime("%Y-%m-%d")
    content = content.replace("YYYY-MM-DD", today)

    # Replace manifest hash if provided
    if manifest_path:
        try:
            manifest_hash = get_manifest_hash(manifest_path)
            content = content.replace("PLACEHOLDER_MANIFEST_SHA256", manifest_hash)
        except FileNotFoundError:
            print(f"Warning: Manifest file not found at {manifest_path}")

    # Keep source commit placeholder for user to fill
    content = content.replace("PLACEHOLDER_SOURCE_COMMIT", "PLACEHOLDER_SOURCE_COMMIT")

    return content


def validate_release_notes(
    version: str, manifest_path: Path | None = None, require_source_commit: str | None = None
) -> bool:
    """Validate release notes file."""
    release_notes_dir = get_release_notes_dir()
    release_file = release_notes_dir / f"{version}.md"

    if not release_file.exists():
        print(f"Error: Release notes file not found: {release_file}")
        return False

    # Read release notes
    with open(release_file) as f:
        content = f.read()

    errors = []

    # Check for placeholders that should be replaced
    if "PLACEHOLDER_SOURCE_COMMIT" in content:
        errors.append("Source commit placeholder not replaced")

    if "PLACEHOLDER_MANIFEST_SHA256" in content:
        errors.append("Manifest SHA256 placeholder not replaced")

    if "YYYY-MM-DD" in content:
        errors.append("Date placeholder not replaced")

    if "mirror-vX.Y.Z" in content:
        errors.append("Version placeholder not replaced")

    # Validate manifest hash if provided
    if manifest_path and manifest_path.exists():
        expected_hash = get_manifest_hash(manifest_path)
        if expected_hash not in content:
            errors.append(f"Expected manifest hash {expected_hash} not found in release notes")

    # Validate source commit if required
    if require_source_commit:
        if require_source_commit not in content:
            errors.append(f"Required source commit {require_source_commit} not found in release notes")

    # Check that version appears in the content
    if version not in content:
        errors.append(f"Version {version} not found in release notes")

    # Check for basic structure
    required_sections = ["### Summary", "### Added", "### Changed", "### Fixed", "### Technical Details"]
    for section in required_sections:
        if section not in content:
            errors.append(f"Required section missing: {section}")

    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        return False

    print(f"Release notes validation passed for {version}")
    return True


def extract_version_from_tag(tag: str) -> str:
    """Extract clean version from git tag."""
    # Remove 'v' prefix if present
    if tag.startswith("v"):
        tag = tag[1:]
    return tag


def main():
    parser = argparse.ArgumentParser(description="Generate and validate release notes")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate release notes from template")
    generate_parser.add_argument("--version", required=True, help="Release version (e.g., mirror-v1.0.0)")
    generate_parser.add_argument("--manifest-path", type=Path, help="Path to manifest file")
    generate_parser.add_argument("--output", type=Path, help="Output file path (default: release-notes/<version>.md)")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate existing release notes")
    validate_parser.add_argument("--version", required=True, help="Release version (e.g., mirror-v1.0.0)")
    validate_parser.add_argument("--manifest-path", type=Path, help="Path to manifest file")
    validate_parser.add_argument("--require-source-commit", help="Required source commit hash")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "generate":
            content = generate_release_notes(args.version, args.manifest_path)

            if args.output:
                output_path = args.output
            else:
                release_notes_dir = get_release_notes_dir()
                release_notes_dir.mkdir(exist_ok=True)
                output_path = release_notes_dir / f"{args.version}.md"

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                f.write(content)

            print(f"Generated release notes: {output_path}")
            print("\nNext steps:")
            print("1. Edit the generated file to replace placeholder content")
            print("2. Add specific changes under each section")
            print("3. Replace PLACEHOLDER_SOURCE_COMMIT with actual commit hash")
            print("4. Validate using: python scripts/generate_release_notes.py validate --version <version>")

        elif args.command == "validate":
            success = validate_release_notes(args.version, args.manifest_path, args.require_source_commit)
            return 0 if success else 1

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
