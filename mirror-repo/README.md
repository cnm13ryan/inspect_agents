# Vending-Bench Mirror Repository Setup

This directory contains the configuration and documentation for the external mirror repository that provides public access to the Vending-Bench benchmark.

## Repository Structure

The mirror repository follows this structure:

```
inspect-vending-bench-mirror/
├── README.md              # Main mirror documentation
├── vending_bench/         # Mirrored benchmark code
├── tests/                 # Mirrored test suite
├── docs/                  # Additional documentation
├── ci/                    # CI configuration
├── scripts/
│   ├── validate-package.sh   # Package validation script
│   ├── smoke-test.sh        # Smoke testing script
│   └── deploy-check.sh      # Pre-deployment checks
├── .github/
│   └── workflows/
│       └── sync.yml       # Mirror sync automation
└── mirror-manifest.json   # Sync metadata
```

## Mirror Repository Purpose

The mirror repository serves several key functions:

1. **Public Access**: Provides public access to the Vending-Bench benchmark without requiring access to the private `inspect_agents` repository
2. **Versioned Releases**: Enables semantic versioning and stable releases with proper changelogs
3. **External Collaboration**: Allows external researchers and developers to engage via GitHub Issues and Discussions
4. **Isolated Testing**: Provides an environment for testing the benchmark independently

## Sync Process

### Automated Sync

The mirror sync process is automated via GitHub Actions (see `ci/sync.yml`):

1. **Trigger**: Runs on push to relevant upstream branches, manual dispatch, or weekly schedule
2. **Content Sync**: Uses `tools/mirror_sync.py` to package upstream changes
3. **Validation**: Runs smoke tests to ensure functionality
4. **Release**: Creates tagged releases with semantic versioning

### Manual Sync

For manual sync operations:

```bash
# Prepare mirror package locally
uv run python tools/mirror_sync.py --source examples/vending_bench --target mirror-prep

# Validate the mirror package
./scripts/validate-package.sh mirror-prep

# Run smoke tests
./scripts/smoke-test.sh mirror-prep

# Check deployment readiness
./scripts/deploy-check.sh .

# Review changes before deployment
ls -la mirror-prep/

# Deploy via CI pipeline (automated in production)
```

### Validation Scripts

The mirror repository includes validation scripts for quality assurance:

**Package Validation** (`scripts/validate-package.sh`):
- Validates mirror package structure and integrity
- Checks manifest format and required fields
- Verifies Python imports and package completeness
- Generates detailed validation reports

**Smoke Testing** (`scripts/smoke-test.sh`):
- Tests basic functionality and imports
- Validates configuration loading
- Checks environment and tools modules
- Runs syntax validation on test files

**Deployment Checks** (`scripts/deploy-check.sh`):
- Pre-deployment repository validation
- Git repository status and security checks
- CI workflow configuration validation
- Documentation and governance compliance

## Release Management

### Versioning Scheme

Mirror releases follow semantic versioning: `mirror-v<major>.<minor>.<patch>`

- **Major**: Breaking changes, architectural updates
- **Minor**: New features, backwards-compatible changes
- **Patch**: Bug fixes, documentation updates

### Release Process

1. **Content Changes**: Upstream changes detected in `examples/vending_bench/`
2. **Sync Validation**: Automated tests validate the sync package
3. **Release Creation**: CI creates new release tag with generated release notes
4. **Publication**: Release published to mirror repository with artifacts

### Release Notes

Release notes live in `release-notes/` and follow the Keep a Changelog categories used in the upstream `CHANGELOG.md`. Each `mirror-v<major>.<minor>.<patch>.md` entry must capture:
- A concise summary of the release scope
- Changes grouped under Added/Changed/Fixed/Docs
- The exact upstream source commit (`git rev-parse HEAD`)
- The SHA256 of the published `mirror-manifest.json` (if produced by the sync job)
**Authoring workflow**
1. Generate a draft entry from the template: `python scripts/generate_release_notes.py generate --version mirror-vX.Y.Z --manifest-path mirror-manifest.json` (omit `--manifest-path` if the manifest is not yet available).
2. Edit the generated Markdown to replace placeholder bullets with the final summary, referencing upstream PRs where helpful.
3. Validate before opening a PR: `python scripts/generate_release_notes.py validate --version mirror-vX.Y.Z --manifest-path mirror-manifest.json --require-source-commit $(git rev-parse HEAD)`.
4. Commit the new file under `release-notes/` alongside the release tag request.

**CI guardrails**
- `ci/sync.yml` adds a `Validate Release Notes` job on `mirror-v*` tags that runs the same validation script; the pipeline fails if entries are missing or hashes do not match.
- Run the validation script locally when iterating on release candidates to catch issues before pushing tags.

## Configuration Management

### GitHub Actions Configuration

The mirror uses GitHub Actions for automation (see `ci/sync.yml`):

- **Secrets**: Requires `MIRROR_REPO_TOKEN` for write access to mirror repository
- **Scheduling**: Weekly sync runs every Sunday at 00:00 UTC
- **Triggers**: Push events to relevant branches, workflow dispatch
- **Environment**: Ubuntu latest with Python 3.12+

### Sync Settings

Key configuration options for mirror sync:

```python
# In tools/mirror_sync.py
MIRROR_CONFIG = {
    "source_patterns": ["examples/vending_bench/**"],
    "exclude_patterns": ["__pycache__", "*.pyc", ".DS_Store"],
    "test_command": "pytest -q tests/unit/vending_bench -k mirror_sync",
    "validation_required": True
}
```

## Security and Governance

### Repository Security

- **Access Control**: Mirror repository has restricted write access
- **Code Reviews**: All sync PRs require approval from CODEOWNERS
- **Security Scanning**: GitHub security features enabled
- **Dependency Updates**: Automated security updates for dependencies

### Governance Model

- **Maintainers**: Mirror maintained by upstream `inspect_agents` team
- **External Issues**: GitHub Issues enabled for mirror-specific problems
- **Discussions**: GitHub Discussions enabled for community engagement
- **Contributions**: External contributions routed to upstream repository

### Compliance

- **License**: Inherits license from upstream repository
- **Attribution**: Proper attribution to upstream maintained
- **Documentation**: Mirror-specific documentation clearly separated

## Monitoring and Maintenance

### Health Checks

Automated health monitoring includes:
- Daily sync status checks
- Test suite validation
- Link integrity verification
- Documentation currency checks

### Maintenance Tasks

Regular maintenance activities:
- **Quarterly**: Review automation credentials and permissions
- **Monthly**: Update documentation and release notes
- **Weekly**: Automated sync validation
- **Daily**: Monitor sync status and error notifications

## Troubleshooting

### Common Issues

**Sync Failures**:
- Check upstream repository access
- Validate `tools/mirror_sync.py` functionality
- Review CI logs for specific errors

**Test Failures**:
- Ensure test dependencies are properly mirrored
- Check for breaking changes in upstream
- Validate mirror package completeness

**Release Issues**:
- Verify semantic versioning logic
- Check GitHub Actions permissions
- Review release note generation

### Support Contacts

- **Mirror Issues**: File GitHub issues in mirror repository
- **Upstream Issues**: Contact `inspect_agents` repository maintainers
- **Automation Issues**: Review CI/CD logs and configuration

## Development Setup

For local mirror development:

```bash
# Clone mirror repository
git clone https://github.com/example/inspect-vending-bench-mirror.git
cd inspect-vending-bench-mirror

# Install dependencies
uv sync

# Run tests
python tests/run_tests.py

# Run benchmark
python vending_bench/run.py --help
```

## Future Enhancements

Planned improvements to the mirror system:

1. **Enhanced Analytics**: Usage tracking and download metrics
2. **Multi-format Releases**: Docker images, conda packages
3. **Documentation Site**: Dedicated documentation hosting
4. **Community Features**: Enhanced discussion and collaboration tools
5. **Integration Testing**: Extended CI/CD pipeline with integration tests
