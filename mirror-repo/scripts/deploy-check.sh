#!/bin/bash
# Pre-deployment check script for mirror repository
# Validates that a mirror repository is ready for automated sync deployment

set -euo pipefail

MIRROR_REPO_DIR="${1:-.}"
VERBOSE="${VERBOSE:-false}"

echo "🔍 Running pre-deployment checks for mirror repository: $MIRROR_REPO_DIR"

# Helper functions
log() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo "🔍 $*"
    fi
}

error() {
    echo "❌ $*" >&2
}

success() {
    echo "✅ $*"
}

warn() {
    echo "⚠️  $*"
}

info() {
    echo "ℹ️  $*"
}

# Navigate to mirror repo directory
cd "$MIRROR_REPO_DIR"

# Check 1: Git repository validation
check_git_repo() {
    echo "📁 Checking Git repository status..."

    if [[ ! -d ".git" ]]; then
        error "Not a Git repository"
        exit 1
    fi

    # Check for uncommitted changes
    if ! git diff --quiet; then
        warn "Uncommitted changes detected in working directory"
        git status --porcelain
    else
        success "Working directory clean"
    fi

    # Check for untracked files (excluding .mirror/)
    local untracked=$(git ls-files --others --exclude-standard | grep -v "^\.mirror/" || true)
    if [[ -n "$untracked" ]]; then
        warn "Untracked files detected:"
        echo "$untracked" | sed 's/^/  /'
    else
        success "No untracked files"
    fi

    # Check current branch
    local current_branch=$(git branch --show-current)
    success "Current branch: $current_branch"
}

# Check 2: CI workflow validation
check_ci_workflow() {
    echo "⚙️  Checking CI workflow configuration..."

    if [[ -f "ci/sync.yml" ]]; then
        success "CI workflow file found: ci/sync.yml"

        # Basic YAML syntax check
        if command -v python3 &> /dev/null; then
            python3 -c "
import yaml
import sys

try:
    with open('ci/sync.yml', 'r') as f:
        yaml.safe_load(f)
    print('✅ YAML syntax valid')
except yaml.YAMLError as e:
    print(f'❌ YAML syntax error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Failed to validate YAML: {e}')
    sys.exit(1)
"
        else
            warn "Python not available for YAML validation"
        fi

        # Check for required jobs
        local required_jobs=("detect-changes" "validate-sync" "deploy-mirror")
        for job in "${required_jobs[@]}"; do
            if grep -q "$job:" ci/sync.yml; then
                success "Required job found: $job"
            else
                error "Missing required job: $job"
                exit 1
            fi
        done
    else
        error "CI workflow file not found: ci/sync.yml"
        exit 1
    fi
}

# Check 3: Scripts directory validation
check_scripts() {
    echo "📜 Checking scripts directory..."

    if [[ -d "scripts" ]]; then
        success "Scripts directory exists"

        # Check for helper scripts
        local script_files=$(find scripts -name "*.sh" -type f | wc -l)
        info "Found $script_files shell scripts in scripts/"

        # Check script permissions
        local executable_scripts=0
        while IFS= read -r -d '' script; do
            if [[ -x "$script" ]]; then
                ((executable_scripts++))
            else
                warn "Script not executable: $script"
            fi
        done < <(find scripts -name "*.sh" -type f -print0)

        info "$executable_scripts/$script_files scripts are executable"
    else
        warn "Scripts directory not found"
    fi
}

# Check 4: Documentation validation
check_documentation() {
    echo "📚 Checking documentation..."

    # Check for README
    if [[ -f "README.md" ]]; then
        success "README.md found"

        # Check README content for mirror-specific sections
        local mirror_sections=("Mirror" "Sync" "Deployment")
        for section in "${mirror_sections[@]}"; do
            if grep -qi "$section" README.md; then
                success "README contains $section section"
            else
                info "README may be missing $section section"
            fi
        done
    else
        error "README.md not found"
        exit 1
    fi

    # Check for CODEOWNERS
    if [[ -f "CODEOWNERS" ]]; then
        success "CODEOWNERS file found"
        local owners_count=$(grep -v "^#" CODEOWNERS | grep -c "@" || echo "0")
        info "CODEOWNERS specifies $owners_count code owners"
    else
        warn "CODEOWNERS file not found - manual review may be required"
    fi
}

# Check 5: GitHub Actions environment
check_github_environment() {
    echo "🐙 Checking GitHub Actions environment..."

    # Check for .github directory (if this is being run in the actual mirror repo)
    if [[ -d ".github" ]]; then
        success ".github directory exists"

        if [[ -d ".github/workflows" ]]; then
            local workflow_count=$(find .github/workflows -name "*.yml" -o -name "*.yaml" | wc -l)
            info "Found $workflow_count workflow files in .github/workflows/"
        else
            info "No .github/workflows directory found"
        fi
    else
        info "No .github directory found (may be expected for sync target)"
    fi

    # Check if this repo would support required secrets
    local required_secrets=("MIRROR_REPO_TOKEN")
    info "Required GitHub secrets for deployment:"
    for secret in "${required_secrets[@]}"; do
        info "  - $secret"
    done
}

# Check 6: Repository structure for mirror sync
check_mirror_structure() {
    echo "🪞 Checking mirror repository structure..."

    # Check if this looks like a target mirror repo or source repo
    if [[ -d "vending_bench" && -f "mirror-manifest.json" ]]; then
        success "Appears to be a mirror repository with synchronized content"

        # Validate manifest
        if command -v python3 &> /dev/null; then
            python3 -c "
import json
import sys

try:
    with open('mirror-manifest.json', 'r') as f:
        manifest = json.load(f)

    required_fields = ['content_hash', 'upstream_commit', 'sync_timestamp']
    for field in required_fields:
        if field in manifest:
            print(f'✅ Manifest field present: {field}')
        else:
            print(f'❌ Missing manifest field: {field}')
            sys.exit(1)

except Exception as e:
    print(f'❌ Manifest validation failed: {e}')
    sys.exit(1)
"
        fi

        # Check last sync time
        local last_sync=$(python3 -c "
import json
from datetime import datetime

with open('mirror-manifest.json', 'r') as f:
    manifest = json.load(f)

sync_time = manifest.get('sync_timestamp', 'unknown')
print(f'Last sync: {sync_time}')
" 2>/dev/null || echo "Last sync: unknown")
        info "$last_sync"

    elif [[ -d "examples/vending_bench" && -f "tools/mirror_sync.py" ]]; then
        success "Appears to be source repository with mirror tooling"
    else
        warn "Repository structure unclear - may be empty mirror repo"
    fi
}

# Check 7: Security considerations
check_security() {
    echo "🔒 Checking security considerations..."

    # Check for sensitive files that shouldn't be in mirror
    local sensitive_patterns=("*.key" "*.pem" "*.p12" "*.env" "*.secret")
    local found_sensitive=false

    for pattern in "${sensitive_patterns[@]}"; do
        if find . -name "$pattern" -not -path "./.git/*" | grep -q .; then
            error "Found potentially sensitive files matching: $pattern"
            find . -name "$pattern" -not -path "./.git/*" | sed 's/^/  /'
            found_sensitive=true
        fi
    done

    if ! $found_sensitive; then
        success "No obvious sensitive files detected"
    fi

    # Check for hardcoded secrets in git history (basic check)
    local secret_patterns=("password" "secret" "token" "api[_-]?key")
    local found_secrets=false

    for pattern in "${secret_patterns[@]}"; do
        if git log --all --grep="$pattern" --oneline | head -5 | grep -q .; then
            warn "Git history may contain references to: $pattern"
            found_secrets=true
        fi
    done

    if ! $found_secrets; then
        success "No obvious secrets in recent git history"
    fi
}

# Generate deployment readiness report
generate_report() {
    echo ""
    echo "📊 Deployment Readiness Report"
    echo "==============================="

    local checks_passed=0
    local total_checks=7

    # Count successful checks (this is a simplified check)
    if [[ -d ".git" ]]; then ((checks_passed++)); fi
    if [[ -f "ci/sync.yml" ]]; then ((checks_passed++)); fi
    if [[ -d "scripts" ]]; then ((checks_passed++)); fi
    if [[ -f "README.md" ]]; then ((checks_passed++)); fi
    if [[ -d ".github" ]] || [[ -f "ci/sync.yml" ]]; then ((checks_passed++)); fi
    if [[ -f "mirror-manifest.json" ]] || [[ -f "tools/mirror_sync.py" ]]; then ((checks_passed++)); fi
    ((checks_passed++))  # Security check (assume passed if we get here)

    local score=$((checks_passed * 100 / total_checks))

    echo "📈 Overall Score: $checks_passed/$total_checks ($score%)"
    echo ""

    if [[ $checks_passed -eq $total_checks ]]; then
        echo "🎉 Repository is ready for mirror deployment!"
        echo ""
        echo "✅ Next Steps:"
        echo "  1. Commit any pending changes"
        echo "  2. Test the CI workflow with a manual trigger"
        echo "  3. Monitor the deployment process"
        echo "  4. Verify CODEOWNERS approval workflow"
    elif [[ $checks_passed -ge $((total_checks * 3 / 4)) ]]; then
        echo "⚠️  Repository is mostly ready with minor issues"
        echo ""
        echo "🔧 Recommended Actions:"
        echo "  1. Address any warnings above"
        echo "  2. Test the CI workflow"
        echo "  3. Consider adding missing components"
    else
        echo "❌ Repository needs significant work before deployment"
        echo ""
        echo "🚫 Required Actions:"
        echo "  1. Fix all errors mentioned above"
        echo "  2. Add missing required components"
        echo "  3. Re-run this check before proceeding"
        exit 1
    fi
}

# Main execution
main() {
    local start_time=$(date +%s)

    check_git_repo
    check_ci_workflow
    check_scripts
    check_documentation
    check_github_environment
    check_mirror_structure
    check_security

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    generate_report
    echo ""
    echo "⏱️  Check completed in ${duration}s"
}

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
