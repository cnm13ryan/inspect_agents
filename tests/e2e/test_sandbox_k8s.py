"""
E2E: Hardened Kubernetes provider checks (opt-in).

Two layers of validation:
 1) Static assertions on values.yaml defaults (always runs, fast)
 2) Optional runtime apply via Helm when explicitly enabled with env vars

Enable runtime checks with:
  INSPECT_E2E_SANDBOX=1 INSPECT_E2E_K8S_CHART=<chart-ref>
  pytest -q -m sandbox_e2e -k k8s

Skips gracefully when kubectl/helm are unavailable or env not set.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.sandbox_e2e


ROOT = Path(__file__).resolve().parents[2]
VALUES = ROOT / "ops/providers/k8s/values.yaml"


def _enabled() -> bool:
    val = os.getenv("INSPECT_E2E_SANDBOX", "").lower()
    return val in {"1", "true", "yes", "on", "k8s", "all"}


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        capture_output=True,
    )


def test_values_security_defaults_static() -> None:
    # Always perform static checks against the values file
    text = VALUES.read_text(encoding="utf-8")

    # NetworkPolicy defaults: enabled with default deny egress; preset N2
    assert "networkPolicy:" in text
    assert "enabled: true" in text
    assert "defaultDenyEgress: true" in text
    assert "netPreset: N2" in text

    # Container security context: read-only rootfs and drop ALL caps
    assert "containerSecurityContext:" in text
    assert "readOnlyRootFilesystem: true" in text
    assert 'drop: ["ALL"]' in text or 'drop: ["ALL"]' in text


@pytest.mark.network
def test_k8s_runtime_security_and_egress() -> None:
    if not _enabled():
        pytest.skip("INSPECT_E2E_SANDBOX not enabled; skipping k8s e2e")
    if shutil.which("kubectl") is None or shutil.which("helm") is None:
        pytest.skip("kubectl/helm not available; skipping")

    chart = os.getenv("INSPECT_E2E_K8S_CHART")
    if not chart:
        pytest.skip("INSPECT_E2E_K8S_CHART not set; skipping runtime apply")

    ns = "inspect-sandbox-e2e"
    release = "inspect-sandbox-e2e"

    # Namespace + pod security labels
    _run(["kubectl", "create", "namespace", ns, "--dry-run=client", "-o", "yaml"])  # validate client-side
    _run(
        ["kubectl", "apply", "-f", "-"],
    ).stdout
    _run(
        [
            "kubectl",
            "label",
            "namespace",
            ns,
            "pod-security.kubernetes.io/enforce=restricted",
            "pod-security.kubernetes.io/enforce-version=latest",
            "--overwrite",
        ]
    )

    try:
        # Install/upgrade chart with hardened values
        _run(
            [
                "helm",
                "upgrade",
                "--install",
                release,
                chart,
                "-n",
                ns,
                "-f",
                str(VALUES),
            ]
        )

        # Wait for pod ready
        _run(
            ["kubectl", "wait", "--for=condition=Ready", "pod/-l", "app=inspect-sandbox", "-n", ns, "--timeout=90s"]
        )  # label may differ by chart

        # Grab first pod name
        pods = _run(["kubectl", "get", "pods", "-n", ns, "-o", "json"]).stdout
        items = json.loads(pods).get("items", [])
        assert items, "no pods found in namespace"
        pod = items[0]["metadata"]["name"]

        # SecurityContext assertions
        pod_json = json.loads(_run(["kubectl", "get", "pod", pod, "-n", ns, "-o", "json"]).stdout)
        c0 = pod_json["spec"]["containers"][0]
        sc = c0.get("securityContext", {})
        assert sc.get("readOnlyRootFilesystem") is True
        caps = (sc.get("capabilities", {}) or {}).get("drop", [])
        assert "ALL" in caps

        # Egress deny: try HTTP fetch and expect non-zero exit
        # Ubuntu image may not have curl; try busybox wget via sh -c if present.
        rc = subprocess.call(
            [
                "kubectl",
                "exec",
                pod,
                "-n",
                ns,
                "--",
                "sh",
                "-lc",
                "(command -v wget >/dev/null && wget -q --spider --timeout=3 http://example.com) || "
                "(command -v curl >/dev/null && curl -sSf -m 3 http://example.com); echo $?",
            ]
        )
        assert rc != 0, "egress unexpectedly allowed (expected default deny)"

        # Namespace labels present
        ns_json = json.loads(_run(["kubectl", "get", "ns", ns, "-o", "json"]).stdout)
        labels = ns_json.get("metadata", {}).get("labels", {})
        assert labels.get("pod-security.kubernetes.io/enforce") == "restricted"

    finally:
        # Teardown (best-effort)
        try:
            _run(["helm", "uninstall", release, "-n", ns])
        except Exception:
            pass
        try:
            _run(["kubectl", "delete", "namespace", ns, "--wait=false"])
        except Exception:
            pass
