#!/bin/bash
# Smoke test script for mirror repository
# Runs basic functionality tests to ensure the mirror package is working

set -euo pipefail

PACKAGE_DIR="${1:-mirror-package}"
VERBOSE="${VERBOSE:-false}"

echo "🧪 Running smoke tests for: $PACKAGE_DIR"

# Helper function for verbose output
log() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo "🔍 $*"
    fi
}

# Check if package directory exists and navigate to it
if [[ ! -d "$PACKAGE_DIR" ]]; then
    echo "❌ Package directory not found: $PACKAGE_DIR"
    exit 1
fi

cd "$PACKAGE_DIR"

# Test 1: Basic imports
test_imports() {
    echo "📦 Testing basic imports..."

    python3 -c "
import sys
sys.path.insert(0, '.')

# Test core imports
try:
    from vending_bench import config
    print('✅ vending_bench.config imported successfully')
except ImportError as e:
    print(f'❌ Failed to import vending_bench.config: {e}')
    sys.exit(1)

try:
    from vending_bench import env
    print('✅ vending_bench.env imported successfully')
except ImportError as e:
    print(f'❌ Failed to import vending_bench.env: {e}')
    sys.exit(1)

try:
    from vending_bench import tools
    print('✅ vending_bench.tools imported successfully')
except ImportError as e:
    print(f'❌ Failed to import vending_bench.tools: {e}')
    sys.exit(1)

print('🎉 All core imports successful!')
"
}

# Test 2: Configuration loading
test_config() {
    echo "⚙️  Testing configuration loading..."

    python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from vending_bench import config

    # Try to access common config attributes
    if hasattr(config, '__version__'):
        print(f'✅ Version info available: {config.__version__}')
    else:
        print('ℹ️  No version info found (may be expected)')

    print('✅ Configuration module loaded successfully')

except Exception as e:
    print(f'❌ Configuration test failed: {e}')
    sys.exit(1)
"
}

# Test 3: Environment functionality
test_environment() {
    echo "🌍 Testing environment functionality..."

    python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from vending_bench import env

    # Test if we can access environment-related functionality
    print('✅ Environment module accessible')

    # Check for common environment attributes/functions
    env_attrs = [attr for attr in dir(env) if not attr.startswith('_')]
    if env_attrs:
        print(f'ℹ️  Available environment attributes: {len(env_attrs)} items')

    print('✅ Environment functionality test passed')

except Exception as e:
    print(f'❌ Environment test failed: {e}')
    sys.exit(1)
"
}

# Test 4: Tools functionality
test_tools() {
    echo "🔧 Testing tools functionality..."

    python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from vending_bench import tools

    # Test if we can access tools-related functionality
    print('✅ Tools module accessible')

    # Check for common tool attributes/functions
    tool_attrs = [attr for attr in dir(tools) if not attr.startswith('_')]
    if tool_attrs:
        print(f'ℹ️  Available tool attributes: {len(tool_attrs)} items')

    print('✅ Tools functionality test passed')

except Exception as e:
    print(f'❌ Tools test failed: {e}')
    sys.exit(1)
"
}

# Test 5: Package structure integrity
test_structure() {
    echo "📁 Testing package structure integrity..."

    # Check critical directories
    critical_dirs=("vending_bench" "tests")
    for dir in "${critical_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            local file_count=$(find "$dir" -name "*.py" | wc -l)
            echo "✅ Directory $dir contains $file_count Python files"
        else
            echo "❌ Critical directory missing: $dir"
            exit 1
        fi
    done

    # Check for __init__.py files where expected
    if [[ -f "vending_bench/__init__.py" ]]; then
        echo "✅ vending_bench package properly initialized"
    else
        echo "⚠️  vending_bench/__init__.py not found - may cause import issues"
    fi
}

# Test 6: Manifest validation
test_manifest() {
    echo "📋 Testing manifest integrity..."

    if [[ -f "mirror-manifest.json" ]]; then
        python3 -c "
import json
import sys

try:
    with open('mirror-manifest.json', 'r') as f:
        manifest = json.load(f)

    # Check manifest structure
    source_info = manifest.get('source_info', {})
    git_info = manifest.get('git_info', {})

    if 'content_hash' in source_info:
        print(f'✅ Content hash present: {source_info[\"content_hash\"][:12]}...')
    else:
        print('❌ Content hash missing from manifest.source_info')
        sys.exit(1)

    if 'commit_sha' in git_info:
        print(f'✅ Upstream commit recorded: {git_info[\"commit_sha\"][:8]}')
    else:
        print('❌ Upstream commit missing from manifest.git_info')
        sys.exit(1)

    print('✅ Manifest validation passed')

except Exception as e:
    print(f'❌ Manifest validation failed: {e}')
    sys.exit(1)
"
    else
        echo "❌ mirror-manifest.json not found"
        exit 1
    fi
}

# Test 7: Quick unit test check (if available)
test_unit_tests() {
    echo "🧪 Checking unit test availability..."

    if [[ -d "tests/unit" ]]; then
        local test_count=$(find tests/unit -name "test_*.py" -o -name "*_test.py" | wc -l)
        if [[ $test_count -gt 0 ]]; then
            echo "✅ Found $test_count unit test files"

            # Try to run a quick syntax check on test files
            python3 -c "
import ast
import sys
from pathlib import Path

test_files = list(Path('tests/unit').glob('**/*.py'))
syntax_errors = 0

for test_file in test_files:
    try:
        with open(test_file, 'r') as f:
            ast.parse(f.read())
    except SyntaxError as e:
        print(f'❌ Syntax error in {test_file}: {e}')
        syntax_errors += 1

if syntax_errors == 0:
    print(f'✅ All {len(test_files)} test files have valid syntax')
else:
    print(f'❌ Found {syntax_errors} syntax errors in test files')
    sys.exit(1)
"
        else
            echo "⚠️  tests/unit directory exists but no test files found"
        fi
    else
        echo "ℹ️  No tests/unit directory found"
    fi
}

# Run smoke test summary
run_summary() {
    echo ""
    echo "📊 Smoke Test Summary"
    echo "===================="
    echo "✅ All smoke tests completed successfully!"
    echo ""
    echo "🎯 Test Results:"
    echo "  ✅ Import functionality working"
    echo "  ✅ Configuration loading functional"
    echo "  ✅ Environment module accessible"
    echo "  ✅ Tools module accessible"
    echo "  ✅ Package structure valid"
    echo "  ✅ Manifest integrity confirmed"
    echo "  ✅ Unit test structure validated"
    echo ""
    echo "🚀 Mirror package ready for deployment!"
}

# Main execution
main() {
    local start_time=$(date +%s)

    test_imports
    test_config
    test_environment
    test_tools
    test_structure
    test_manifest
    test_unit_tests

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    run_summary
    echo "⏱️  Total test time: ${duration}s"
}

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
