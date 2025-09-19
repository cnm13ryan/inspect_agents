#!/bin/bash
# Mirror package validation script
# Validates the structure and content of a mirror sync package

set -euo pipefail

PACKAGE_DIR="${1:-mirror-package}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔍 Validating mirror package at: $PACKAGE_DIR"

# Check if package directory exists
if [[ ! -d "$PACKAGE_DIR" ]]; then
    echo "❌ Package directory not found: $PACKAGE_DIR"
    exit 1
fi

cd "$PACKAGE_DIR"

# Validation functions
validate_structure() {
    echo "📁 Validating package structure..."

    local required_dirs=("vending_bench" "tests")
    local required_files=("README.md" "mirror-manifest.json")

    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            echo "❌ Missing required directory: $dir"
            exit 1
        fi
        echo "✅ Directory found: $dir"
    done

    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            echo "❌ Missing required file: $file"
            exit 1
        fi
        echo "✅ File found: $file"
    done
}

validate_manifest() {
    echo "📋 Validating mirror manifest..."

    python3 -c "
import json
import sys

try:
    with open('mirror-manifest.json', 'r') as f:
        manifest = json.load(f)

    required_fields = ['sync_timestamp']
    required_nested = {
        'source_info': ['content_hash'],
        'git_info': ['commit_sha']
    }

    for field in required_fields:
        if field not in manifest:
            print(f'❌ Missing required field in manifest: {field}')
            sys.exit(1)
        print(f'✅ Manifest field present: {field}')

    for parent_field, nested_fields in required_nested.items():
        if parent_field not in manifest:
            print(f'❌ Missing required section in manifest: {parent_field}')
            sys.exit(1)

        for nested_field in nested_fields:
            if nested_field not in manifest[parent_field]:
                print(f'❌ Missing required field in manifest.{parent_field}: {nested_field}')
                sys.exit(1)
            print(f'✅ Manifest field present: {parent_field}.{nested_field}')

    content_hash = manifest.get('source_info', {}).get('content_hash', 'unknown')
    upstream_commit = manifest.get('git_info', {}).get('commit_sha', 'unknown')
    sync_timestamp = manifest.get('sync_timestamp', 'unknown')

    print(f'📊 Content hash: {content_hash[:12]}...')
    print(f'📊 Upstream commit: {upstream_commit[:8]}')
    print(f'📊 Sync timestamp: {sync_timestamp}')

    print('✅ Manifest validation passed')

except Exception as e:
    print(f'❌ Manifest validation failed: {e}')
    sys.exit(1)
"

    if [ $? -eq 0 ]; then
        echo "✅ Manifest validation completed successfully"
    else
        echo "❌ Manifest validation failed"
        exit 1
    fi
}

validate_imports() {
    echo "🐍 Validating Python imports..."

    if python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from vending_bench import config, env, tools
    print('✅ Core vending_bench imports successful')
except ImportError as e:
    print(f'❌ Import test failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
        echo "✅ Import validation passed"
    else
        echo "❌ Import validation failed"
        exit 1
    fi
}

validate_tests() {
    echo "🧪 Validating test structure..."

    if [[ -d "tests/unit" ]]; then
        local test_files=$(find tests/unit -name "test_*.py" -o -name "*_test.py" | wc -l)
        echo "✅ Found $test_files test files in tests/unit"
    else
        echo "⚠️  No tests/unit directory found"
    fi

    if [[ -d "tests/integration" ]]; then
        local integration_tests=$(find tests/integration -name "test_*.py" -o -name "*_test.py" | wc -l)
        echo "✅ Found $integration_tests integration test files"
    else
        echo "ℹ️  No tests/integration directory found"
    fi
}

show_summary() {
    echo ""
    echo "📊 Package Summary:"
    echo "==================="

    echo "📁 Directory structure:"
    find . -type d -not -path './.*' | head -10 | sort

    echo ""
    echo "📄 File count by type:"
    echo "  Python files: $(find . -name "*.py" | wc -l)"
    echo "  Markdown files: $(find . -name "*.md" | wc -l)"
    echo "  JSON files: $(find . -name "*.json" | wc -l)"
    echo "  YAML files: $(find . -name "*.yml" -o -name "*.yaml" | wc -l)"

    echo ""
    echo "💾 Total size: $(du -sh . | cut -f1)"
}

# Run all validations
main() {
    validate_structure
    validate_manifest
    validate_imports
    validate_tests
    show_summary

    echo ""
    echo "✅ Package validation completed successfully!"
    echo "🚀 Package is ready for deployment to mirror repository"
}

main "$@"
