# Hardened Docker provider (Compose)

This template provides a secure-by-default Docker Compose setup for
Inspect’s sandbox provider (H1 in the Tx.Hx.Nx profiles). It runs the
sandbox container as a non-root user with a read-only root filesystem,
drops all Linux capabilities, and enables `no-new-privileges`.

Prerequisites
- Docker Engine 20.10+ and Docker Compose v2
- Linux host recommended; rootless Docker strongly encouraged
- Ensure the `./sandbox_work` and `./sandbox_cache` paths exist (or
  adjust mounts in `compose.yaml`)

How to use with Inspect CLI
```bash
uv run inspect eval examples/tasks/prompt_task.py \
  --sandbox 'docker:ops/providers/docker/compose.yaml' \
  -T prompt="List files and summarize"
```

Notes and options
- Image: The template uses `ubuntu:22.04`. You may swap for a base that
  includes the tools you need (bash, python). Keep the hardening flags.
- Seccomp/AppArmor: The Compose file includes commented lines for custom
  profiles. Provide valid profiles on the host and uncomment:
  - `security_opt: [seccomp=./seccomp-restricted.json]`
  - `security_opt: [apparmor:docker-default]`
- Networks: The `sandbox_net` is a dedicated bridge. For restrictive
  egress, connect the service to a network with firewall/proxy rules or
  pair with a K8s profile (H2) for fine-grained N1/N2.
- Read-only root FS: With `read_only: true`, package installation inside
  the container will fail unless you remount writable paths. Prefer
  pre-baked images for reproducibility.

Mapping to profiles
- H1 corresponds to Docker/Compose. Use this template with:
  - T2 (text-only) or T1 (web-only) profiles
  - T0 (exec) only when approvals and sandbox policies are in place

E2E tests (opt-in)
- These provider-hardening tests are optional and disabled by default.
- Enable with: `INSPECT_E2E_SANDBOX=1 pytest -q -m sandbox_e2e -k docker`
- The test brings `compose.yaml` up and verifies non-root UID/GID,
  read-only rootfs, `no-new-privileges`, `cap_drop: [ALL]`, and a PIDs
  limit. Teardown runs `docker compose down -v`.
