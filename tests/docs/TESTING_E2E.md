# E2E Sandbox Testing

This guide covers opt-in end-to-end (E2E) sandbox testing for Docker and Kubernetes providers. These tests verify security hardening configurations and sandbox isolation guarantees.

## Overview

E2E sandbox tests are **opt-in only** and never run in default CI pipelines. They require external dependencies (Docker/Kubernetes) and are designed for:
- Local validation of provider configurations
- Manual verification of sandbox security posture
- Debugging provider-specific issues

## Prerequisites

### Docker Provider
- Docker Engine 20.10+
- Docker Compose v2 (or legacy docker-compose)
- Access to `ops/providers/docker/compose.yaml`
- Network access for container pulls

### Kubernetes Provider
- Kubernetes cluster with NetworkPolicy-enforcing CNI (Calico, Cilium, etc.)
- `kubectl` and `helm` CLI tools
- Access to Inspect sandbox Helm chart
- Cluster admin permissions for namespace creation

## Opt-in Configuration

Enable E2E sandbox tests with the `INSPECT_E2E_SANDBOX` environment variable:

```bash
# Enable all sandbox tests
export INSPECT_E2E_SANDBOX=1

# Enable specific provider only
export INSPECT_E2E_SANDBOX=docker  # Docker only
export INSPECT_E2E_SANDBOX=k8s     # Kubernetes only

# Alternative enable values
export INSPECT_E2E_SANDBOX=true
export INSPECT_E2E_SANDBOX=yes
export INSPECT_E2E_SANDBOX=on
export INSPECT_E2E_SANDBOX=all
```

### Kubernetes-Specific Configuration

For Kubernetes runtime tests, also set:

```bash
export INSPECT_E2E_K8S_CHART=<helm-chart-reference>
```

## Test Selection

### Run All E2E Sandbox Tests
```bash
INSPECT_E2E_SANDBOX=1 pytest -q -m sandbox_e2e
```

### Docker Provider Only
```bash
INSPECT_E2E_SANDBOX=docker pytest -q -m sandbox_e2e -k docker
```

### Kubernetes Provider Only
```bash
INSPECT_E2E_SANDBOX=k8s INSPECT_E2E_K8S_CHART=inspect/sandbox \
  pytest -q -m sandbox_e2e -k k8s
```

### Maximum Failures (Fail Fast)
```bash
INSPECT_E2E_SANDBOX=1 pytest -q -m sandbox_e2e --maxfail=1
```

## What Gets Tested

### Docker Tests (`test_sandbox_docker.py`)
- **Container user**: Non-root UID/GID (1000:1000)
- **Read-only filesystem**: `ReadonlyRootfs: true`
- **Process limits**: PIDs limit set to 256
- **Security options**: `no-new-privileges` enabled
- **Capabilities**: All capabilities dropped (`cap_drop: [ALL]`)

### Kubernetes Tests (`test_sandbox_k8s.py`)
**Static validation** (always runs when selected):
- NetworkPolicy defaults in `values.yaml`
- Container security context settings
- Required capability drops

**Runtime validation** (requires chart and cluster):
- Pod security context enforcement
- Read-only root filesystem
- Capability dropping
- Default deny egress NetworkPolicy
- Namespace pod security labels

## Skipping Behavior

Tests skip gracefully when:
- `INSPECT_E2E_SANDBOX` is unset or disabled
- Required tools are missing (`docker`, `kubectl`, `helm`)
- Required files are missing (`compose.yaml`, chart)
- Cluster is unreachable (Kubernetes tests)

Example skip messages:
```
SKIPPED - INSPECT_E2E_SANDBOX not enabled; skipping docker e2e
SKIPPED - docker CLI not available; skipping
SKIPPED - kubectl/helm not available; skipping
SKIPPED - INSPECT_E2E_K8S_CHART not set; skipping runtime apply
```

## Troubleshooting

### Docker Issues

**Permission denied**
```bash
# Add user to docker group or use rootless Docker
sudo usermod -aG docker $USER
# Log out and back in
```

**Compose not found**
```bash
# Verify Docker Compose installation
docker compose version
# Or check legacy
docker-compose version
```

**Container fails to start**
```bash
# Check logs manually
docker compose -f ops/providers/docker/compose.yaml up
docker logs inspect-sandbox
```

### Kubernetes Issues

**NetworkPolicy not enforced**
- Verify your CNI supports NetworkPolicy (Cilium, Calico, etc.)
- Check cluster documentation for NetworkPolicy enablement

**Pod security violations**
```bash
# Check namespace labels
kubectl get namespace inspect-sandbox-e2e -o yaml
# Verify pod security context
kubectl describe pod <pod-name> -n inspect-sandbox-e2e
```

**Helm chart not found**
- Verify chart repository and name
- Check chart version compatibility
- Ensure cluster access and permissions

### Test-Specific Issues

**Runtime validation skipped**
- Ensure `INSPECT_E2E_K8S_CHART` points to valid chart
- Verify cluster connectivity: `kubectl cluster-info`
- Check namespace and RBAC permissions

**Teardown failures**
- Tests perform best-effort cleanup
- Manual cleanup: `docker compose down -v` or `kubectl delete namespace <ns>`

## Integration with Test Guides

When E2E sandbox tests fail, the terminal summary automatically links to this guide if:
- `CI=1` environment variable is set, OR
- `DEEPAGENTS_SHOW_TEST_GUIDES=1` is set

Failed tests with `sandbox_e2e` marker will display:
```
========== DeepAgents test guides ==========
Index: tests/docs/README.md
Relevant:
- tests/docs/TESTING_E2E.md
```

## See Also

- [Provider documentation](../../ops/providers/)
- [Docker hardening guide](../../ops/providers/docker/README.md)
- [Kubernetes hardening guide](../../ops/providers/k8s/README.md)
- [Main testing guide](README.md)
