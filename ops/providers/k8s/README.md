# Hardened Kubernetes provider (Helm values)

This template ships secure-by-default Helm values for the Inspect
sandbox provider on Kubernetes (H2 in Tx.Hx.Nx). It applies restricted
Pod and container security settings, ephemeral writable paths, resource
limits, and a default deny egress NetworkPolicy stub.

Prerequisites
- Kubernetes cluster with a CNI that enforces NetworkPolicy (e.g.,
  Calico, Cilium)
- Helm 3
- Access to the Inspect sandbox Helm chart (chart name may vary)

Deploy with Helm (example)
```bash
kubectl create namespace inspect-sandbox --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace inspect-sandbox \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/enforce-version=latest --overwrite

helm upgrade --install inspect-sandbox <inspect-chart> \
  -n inspect-sandbox -f ops/providers/k8s/values.yaml
```

Use with Inspect
- CLI: set `--sandbox k8s` when running `inspect eval` once the sandbox
  is deployed
- Programmatic: construct `Task(..., sandbox="k8s")`

Security defaults in values.yaml
- Non-root user and group, `runAsNonRoot: true`
- `seccompProfile: RuntimeDefault`
- `allowPrivilegeEscalation: false`
- `readOnlyRootFilesystem: true`
- `capabilities.drop: [ALL]`
- `emptyDir` for `/tmp` and `/run`; `/work` is `emptyDir` by default with
  a comment for swapping to a PVC
- `automountServiceAccountToken: false` on the ServiceAccount
- CPU and memory requests/limits for basic guardrails
- NetworkPolicy section with `defaultDenyEgress: true` and DNS allowance

Notes on N1/N2 profiles
- Domain-based allowlists require an egress proxy or L7 enforcement.
  Populate the proxy IPs in `networkPolicy.egressCIDRs` or implement
  proxy-aware policies. Prefer Kubernetes for N1/N2 profiles.

Example NetworkPolicy for N1
- See `policies/networkpolicy-n1-proxy-egress.yaml` for a policy that
  allows egress only to kube-dns and a labeled in-namespace proxy. Apply
  it after deploying the sandbox and ensure your proxy enforces domains.
