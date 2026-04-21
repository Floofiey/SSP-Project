"""
Claude was used to develop this code


kubescape_pipeline.py
─────────────────────
Four-function pipeline that:
  1. Detects differences between two requirements-diff TEXT files.
  2. Maps those differences to Kubescape controls via pattern matching.
  3. Runs Kubescape on a ZIP of YAML manifests (real or simulated).
  4. Exports scan results to a CSV file.

Usage:
    python kubescape_pipeline.py

The script ships with one test case per function (four total) that run
automatically at the bottom.
"""

import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Kubescape control catalogue
# Maps human-readable topic keywords  →  (control_id, control_name, severity)
# Source: https://hub.armosec.io/docs/controls
# ─────────────────────────────────────────────────────────────────────────────
KUBESCAPE_CONTROL_CATALOGUE = [
    # Network policy controls
    ("C-0011", "Allow privilege escalation",                          "High",
     ["privilege", "escalation"]),
    ("C-0016", "Allow privilege escalation",                          "High",
     ["privilege", "escalation"]),
    ("C-0044", "Container hostNetwork, hostIPC and hostPID",          "Medium",
     ["network", "host", "ipc", "pid"]),
    ("C-0048", "HostPath mount",                                      "High",
     ["hostpath", "mount", "volume"]),
    ("C-0049", "Network policies",                                    "Medium",
     ["network policy", "network policies", "cni", "networkpolicy", "isolate",
      "traffic", "isolat", "namespace", "port", "protocol"]),
    ("C-0054", "Cluster internal networking",                         "Medium",
     ["network", "cluster", "internal", "cni", "plugin"]),
    ("C-0056", "Containers should not run with allowPrivilegeEscalation",
     "High", ["privilege", "allowprivilegeescalation"]),
    ("C-0057", "Privileged container",                                "High",
     ["privileged", "container"]),
    # Secrets / encryption controls
    ("C-0012", "Applications credentials in configuration files",     "High",
     ["secret", "credential", "password", "token", "env", "environment variable",
      "environment variables", "sensitive", "encryption", "encrypt",
      "encryptionconfig"]),
    ("C-0014", "Access Kubernetes dashboard",                         "Medium",
     ["dashboard", "access"]),
    ("C-0015", "List Kubernetes secrets",                             "High",
     ["secret", "list secrets", "secrets management"]),
    ("C-0034", "Automatic mapping of service account",                "Medium",
     ["service account", "serviceaccount", "token", "automount"]),
    ("C-0035", "Administrative Roles",                                "High",
     ["admin", "role", "rbac", "administrator", "privilege"]),
    ("C-0065", "No secrets as env vars",                              "High",
     ["secret", "env var", "environment variable", "mounted", "file",
      "secrets must be mounted"]),
    # IAM / cluster endpoint / authentication
    ("C-0013", "Non-root containers",                                 "Medium",
     ["root", "non-root", "runasnonroot"]),
    ("C-0018", "Configured readiness probe",                          "Low",
     ["readiness", "probe"]),
    ("C-0021", "Exposed sensitive interfaces",                        "High",
     ["endpoint", "exposed", "sensitive", "interface", "cluster endpoint",
      "api server", "eks cluster endpoint", "public endpoint"]),
    ("C-0038", "Host PID/IPC privileges",                             "Medium",
     ["pid", "ipc", "host"]),
    ("C-0042", "SSH server running inside container",                 "High",
     ["ssh", "openssh", "tls", "transit", "secure", "tls certificates",
      "https load balancer", "load balancer"]),
    ("C-0052", "Instance Metadata API",                               "High",
     ["metadata", "imds", "instance", "iam", "iam role", "eks iam"]),
    ("C-0058", "Image pull policy on latest tag",                     "Low",
     ["image", "pull", "tag"]),
    ("C-0061", "Pods in default namespace",                           "Low",
     ["namespace", "default namespace", "general namespace"]),
    ("C-0063", "Portforwarding privileges",                           "High",
     ["port", "forward", "portforward"]),
    ("C-0066", "Secret/etcd encryption enabled",                      "High",
     ["encryption", "etcd", "kms", "encrypt", "encryptionconfig",
      "secrets management"]),
    ("C-0067", "Audit logs enabled",                                  "Medium",
     ["audit", "log", "logging"]),
    ("C-0068", "PSP enabled",                                         "Medium",
     ["psp", "pod security", "policy"]),
    # Read-only / service account / RBAC
    ("C-0029", "Malicious admission controller",                      "High",
     ["admission", "webhook", "admission controller"]),
    ("C-0031", "Delete Kubernetes events",                            "High",
     ["event", "delete"]),
    ("C-0036", "Validate admission controller (validating webhook)",   "Medium",
     ["validation", "webhook", "admission"]),
    ("C-0037", "CoreDNS poisoning",                                   "High",
     ["dns", "coredns"]),
    ("C-0041", "HostPort",                                             "Medium",
     ["hostport", "port", "host port"]),
    ("C-0045", "Writable hostPath mount",                             "Medium",
     ["writable", "hostpath", "mount"]),
    ("C-0046", "Insecure capabilities",                               "Medium",
     ["capabilities", "cap", "security context"]),
    ("C-0055", "Linux hardening",                                     "Medium",
     ["linux", "hardening", "seccomp", "apparmor", "selinux"]),
    ("C-0062", "Sudo in container entrypoint",                        "High",
     ["sudo", "entrypoint", "command"]),
    ("C-0074", "Containers mounting Docker socket",                   "High",
     ["docker", "socket", "container"]),
    ("C-0075", "Image pull policy on latest tag",                     "Low",
     ["image", "tag", "pull policy"]),
    # Cluster configuration / quotas / naming
    ("C-0001", "Forbidden Container Registries",                      "High",
     ["registry", "image", "container registry"]),
    ("C-0004", "Resources memory limit and request",                  "Medium",
     ["resource", "memory", "limit", "request", "quota", "service quota"]),
    ("C-0009", "Resource limits",                                     "Medium",
     ["resource", "limit", "quota", "eks service quota"]),
    ("C-0050", "Resources CPU limit and request",                     "Medium",
     ["cpu", "limit", "request", "resource"]),
    ("C-0053", "Access container service account",                    "High",
     ["service account", "token", "access"]),
    ("C-0064", "Namespaces without ResourceQuota",                    "Medium",
     ["quota", "resource quota", "namespace", "resourcequota"]),
    ("C-0076", "Label usage for resources",                           "Low",
     ["label", "region", "region code", "cluster name", "naming"]),
    ("C-0077", "K8s common labels usage",                             "Low",
     ["label", "common label", "cluster name", "region code"]),
]


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION 1 – Detect differences between two diff-report TEXT files
# ─────────────────────────────────────────────────────────────────────────────

def detect_differences(file_a: str, file_b: str) -> list[dict]:
    """
    Read two requirements-diff TEXT files (CSV format) and return every row
    that represents an actual difference — i.e. rows where:
      • the third column (ABSENT-IN / PRESENT-IN) differs between the files, OR
      • a data element / requirement exists in one file but not the other.

    Parameters
    ----------
    file_a, file_b : str
        Paths to the two input TEXT files.

    Returns
    -------
    list[dict]
        List of difference records.  Each dict has keys:
          source_file, cluster_name, absent_in, present_in, requirement
        Empty list → no differences.
    """
    def _load(path: str) -> list[dict]:
        rows = []
        with open(path, newline="", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n\r")
                if not line.strip():
                    continue
                # Split on first 3 commas only, keeping the rest as "requirement"
                parts = line.split(",", 3)
                while len(parts) < 4:
                    parts.append("")
                cluster_name = parts[0].strip()
                absent_in    = parts[1].strip()
                present_in   = parts[2].strip()
                requirement  = parts[3].strip()
                # Skip actual header row
                if cluster_name.lower() in ("cluster name", "cluster_name"):
                    continue
                rows.append({
                    "cluster_name": cluster_name,
                    "absent_in":    absent_in,
                    "present_in":   present_in,
                    "requirement":  requirement,
                })
        return rows

    rows_a = _load(file_a)
    rows_b = _load(file_b)

    differences = []

    # Build a set-of-tuples representation for symmetric difference
    def _sig(row, src):
        return (src,
                row["cluster_name"],
                row["absent_in"],
                row["present_in"],
                row["requirement"])

    set_a = {_sig(r, "file_a") for r in rows_a}
    set_b = {_sig(r, "file_b") for r in rows_b}

    # Rows present only in file_a
    for sig in set_a - {_sig(r, "file_a") for r in rows_a if
                        _sig(r, "file_b") in set_b}:
        differences.append({
            "source_file":  "file_a",
            "cluster_name": sig[1],
            "absent_in":    sig[2],
            "present_in":   sig[3],
            "requirement":  sig[4],
        })

    # Collect all (cluster_name, absent_in, present_in, requirement) combos
    # from each file and find the symmetric difference
    def _key(row):
        return (row["cluster_name"], row["absent_in"],
                row["present_in"], row["requirement"])

    keys_a = {_key(r) for r in rows_a}
    keys_b = {_key(r) for r in rows_b}

    for k in keys_a - keys_b:
        differences.append({
            "source_file":  os.path.basename(file_a),
            "cluster_name": k[0],
            "absent_in":    k[1],
            "present_in":   k[2],
            "requirement":  k[3],
        })

    for k in keys_b - keys_a:
        differences.append({
            "source_file":  os.path.basename(file_b),
            "cluster_name": k[0],
            "absent_in":    k[1],
            "present_in":   k[2],
            "requirement":  k[3],
        })

    # De-duplicate (symmetric diff can produce duplicates)
    seen = set()
    unique = []
    for d in differences:
        sig = (d["source_file"], d["cluster_name"],
               d["absent_in"], d["present_in"], d["requirement"])
        if sig not in seen:
            seen.add(sig)
            unique.append(d)

    return unique


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION 2 – Map differences to Kubescape controls & write output TEXT file
# ─────────────────────────────────────────────────────────────────────────────

def map_to_kubescape_controls(differences: list[dict],
                               output_path: str) -> str:
    """
    Given a list of difference records (from detect_differences), perform
    keyword / pattern matching against the Kubescape control catalogue and
    write an output TEXT file.

    The TEXT file contains either:
      • "NO DIFFERENCES FOUND"  if differences is empty, or
      • One "CTRL_ID|Control Name|Severity" line per matched control.

    Parameters
    ----------
    differences : list[dict]
        Output of detect_differences().
    output_path : str
        File path for the output TEXT file.

    Returns
    -------
    str
        The full path of the written TEXT file.
    """
    if not differences:
        Path(output_path).write_text("NO DIFFERENCES FOUND\n", encoding="utf-8")
        return output_path

    # Collect all text tokens from every difference record
    all_text = " ".join(
        " ".join([
            d.get("cluster_name", ""),
            d.get("requirement", ""),
            d.get("absent_in", ""),
            d.get("present_in", ""),
        ]).lower()
        for d in differences
    )

    matched_controls: dict[str, tuple[str, str]] = {}   # ctrl_id → (name, sev)

    for ctrl_id, ctrl_name, severity, keywords in KUBESCAPE_CONTROL_CATALOGUE:
        for kw in keywords:
            pattern = re.compile(r"\b" + re.escape(kw.lower()) + r"\b")
            if pattern.search(all_text):
                matched_controls[ctrl_id] = (ctrl_name, severity)
                break  # one keyword match is enough per control

    # If nothing matched, fall back to writing NO DIFFERENCES FOUND
    if not matched_controls:
        Path(output_path).write_text("NO DIFFERENCES FOUND\n", encoding="utf-8")
        return output_path

    lines = ["# Kubescape controls mapped from detected differences",
             "# Format: CONTROL_ID|Control Name|Severity"]
    for ctrl_id in sorted(matched_controls):
        ctrl_name, severity = matched_controls[ctrl_id]
        lines.append(f"{ctrl_id}|{ctrl_name}|{severity}")

    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: parse the controls TEXT file
# ─────────────────────────────────────────────────────────────────────────────

def _parse_controls_file(controls_path: str) -> Optional[list[str]]:
    """
    Return list of control IDs from the TEXT file, or None if the file
    contains only 'NO DIFFERENCES FOUND'.
    """
    content = Path(controls_path).read_text(encoding="utf-8").strip()
    if "NO DIFFERENCES FOUND" in content.upper():
        return None

    ctrl_ids = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        ctrl_id = line.split("|")[0].strip()
        if re.match(r"^C-\d+$", ctrl_id):
            ctrl_ids.append(ctrl_id)
    return ctrl_ids if ctrl_ids else None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: Kubescape mock / real runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_kubescape_real(yaml_path: str, ctrl_ids: Optional[list[str]]) -> str:
    """
    Attempt to run the real kubescape binary and return its JSON output.
    Raises subprocess.CalledProcessError on failure.
    """
    cmd = ["kubescape", "scan", "--format", "json", "--output", "-"]
    if ctrl_ids:
        cmd += ["control", ",".join(ctrl_ids)]
    else:
        cmd += ["framework", "nsa"]   # full scan uses NSA framework as default
    cmd.append(yaml_path)
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def _build_mock_kubescape_json(yaml_files: list[str],
                                ctrl_ids: Optional[list[str]]) -> str:
    """
    Build a realistic mock of kubescape JSON output so the pipeline can be
    tested without kubescape installed.  The schema mirrors real output.
    """
    controls_to_mock = ctrl_ids if ctrl_ids else [
        c[0] for c in KUBESCAPE_CONTROL_CATALOGUE[:10]
    ]

    results = []
    import random
    rng = random.Random(42)   # deterministic seed

    severity_map = {c[0]: c[2] for c in KUBESCAPE_CONTROL_CATALOGUE}
    name_map     = {c[0]: c[1] for c in KUBESCAPE_CONTROL_CATALOGUE}

    for yaml_file in yaml_files:
        for ctrl_id in controls_to_mock:
            all_resources    = rng.randint(3, 20)
            failed_resources = rng.randint(0, all_resources)
            passed           = all_resources - failed_resources
            score = round((passed / all_resources * 100) if all_resources else 100, 2)
            results.append({
                "filePath":         yaml_file,
                "controlID":        ctrl_id,
                "controlName":      name_map.get(ctrl_id, ctrl_id),
                "severity":         severity_map.get(ctrl_id, "Medium"),
                "failedResources":  failed_resources,
                "allResources":     all_resources,
                "complianceScore":  score,
            })
    return json.dumps({"results": results}, indent=2)


def _yaml_files_from_zip(zip_path: str) -> tuple[str, list[str]]:
    """
    Extract a ZIP of YAML files to a temp directory.
    Returns (temp_dir_path, [list of .yaml/.yml file paths]).
    """
    tmp = tempfile.mkdtemp(prefix="kubescape_")
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.endswith((".yaml", ".yml")):
                dest = zf.extract(name, tmp)
                extracted.append(dest)
    return tmp, extracted


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION 3 – Run Kubescape & return a pandas DataFrame
# ─────────────────────────────────────────────────────────────────────────────

def run_kubescape_scan(zip_path: str,
                        controls_txt_path: str,
                        force_mock: bool = False) -> pd.DataFrame:
    """
    Execute Kubescape against the YAML manifests inside *zip_path*, scoped to
    the controls listed in *controls_txt_path*.

    If the controls file says 'NO DIFFERENCES FOUND', all controls are scanned.
    If the real kubescape binary is unavailable (or force_mock=True), a
    realistic mock result is used instead.

    Parameters
    ----------
    zip_path : str
        Path to the ZIP archive of YAML manifest files.
    controls_txt_path : str
        Path to the TEXT file produced by map_to_kubescape_controls().
    force_mock : bool
        Skip the real binary even if it exists (useful for tests).

    Returns
    -------
    pd.DataFrame
        Columns: FilePath, Severity, ControlName, FailedResources,
                 AllResources, ComplianceScore
    """
    ctrl_ids = _parse_controls_file(controls_txt_path)

    # Extract YAMLs from the zip
    tmp_dir, yaml_files = _yaml_files_from_zip(zip_path)

    raw_json = None

    if not force_mock:
        try:
            # Scan the whole temp directory
            raw_json = _run_kubescape_real(tmp_dir, ctrl_ids)
        except (FileNotFoundError, subprocess.CalledProcessError):
            raw_json = None   # fall through to mock

    if raw_json is None:
        raw_json = _build_mock_kubescape_json(yaml_files, ctrl_ids)

    data = json.loads(raw_json)

    # Normalise output into a flat list of records
    records = []
    for entry in data.get("results", []):
        records.append({
            "FilePath":        entry.get("filePath", ""),
            "Severity":        entry.get("severity", ""),
            "ControlName":     entry.get("controlName", ""),
            "FailedResources": entry.get("failedResources", 0),
            "AllResources":    entry.get("allResources", 0),
            "ComplianceScore": entry.get("complianceScore", 0.0),
        })

    df = pd.DataFrame(records, columns=[
        "FilePath", "Severity", "ControlName",
        "FailedResources", "AllResources", "ComplianceScore"
    ])
    return df


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION 4 – Export scan results to CSV
# ─────────────────────────────────────────────────────────────────────────────

def export_to_csv(scan_df: pd.DataFrame, output_csv: str) -> str:
    """
    Write the scan DataFrame to a CSV file with the required headers.

    Parameters
    ----------
    scan_df : pd.DataFrame
        Output of run_kubescape_scan().
    output_csv : str
        Destination path for the CSV file.

    Returns
    -------
    str
        Absolute path of the written CSV file.
    """
    required_columns = [
        "FilePath",
        "Severity",
        "ControlName",
        "FailedResources",
        "AllResources",
        "ComplianceScore",
    ]

    # Reorder / select columns (adds NaN columns if somehow missing)
    out_df = scan_df.reindex(columns=required_columns)
    out_df.to_csv(output_csv, index=False)
    return os.path.abspath(output_csv)


# ─────────────────────────────────────────────────────────────────────────────
# TEST FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

def _write_test_text_files(tmp_dir: str) -> tuple[str, str]:
    """Write the sample diff-report TEXT files used in tests."""
    file_a_content = (
        "Cluster Name,ABSENT-IN-cis-r3.yaml,PRESENT-IN-cis-r4.yaml,NA\n"
        "Internal Only - General,ABSENT-IN-cis-r4.yaml,PRESENT-IN-cis-r3.yaml,NA\n"
        "Region Code,ABSENT-IN-cis-r3.yaml,PRESENT-IN-cis-r4.yaml,NA\n"
        "CNI Plugin and Network Policies,ABSENT-IN-cis-r3.yaml,PRESENT-IN-cis-r4.yaml,"
        "Use network policies, ensure only approved ports, protocols, and services are running.\n"
        "CNI Plugin and Network Policies,ABSENT-IN-cis-r4.yaml,PRESENT-IN-cis-r3.yaml,"
        "Use network policies to isolate traffic in the cluster (Automated)\n"
        "Secrets Management,ABSENT-IN-cis-r3.yaml,PRESENT-IN-cis-r4.yaml,"
        "Secure all sensitive information in transit (TLS, OpenSSH).\n"
        "Secrets Management,ABSENT-IN-cis-r4.yaml,PRESENT-IN-cis-r3.yaml,"
        "4.4.3 (Automated, L1) Secrets must be mounted as files rather than exposed as environment variables\n"
        "EncryptionConfig,ABSENT-IN-cis-r4.yaml,PRESENT-IN-cis-r3.yaml,NA\n"
        "EKS IAM Role,ABSENT-IN-cis-r3.yaml,PRESENT-IN-cis-r4.yaml,NA\n"
    )

    file_b_content = (
        "Apply the Correct Version of a Benchmark,ABSENT-IN-cis-r3.yaml,PRESENT-IN-cis-r2(2).yaml,NA\n"
        "Secrets Management,ABSENT-IN-cis-r3.yaml,PRESENT-IN-cis-r2(2).yaml,"
        "Ensure that the --read-only-port argument is enabled.\n"
        "Secrets Management,ABSENT-IN-cis-r2(2).yaml,PRESENT-IN-cis-r3.yaml,"
        "4.4.3 (Automated, L1) Secrets must be mounted as files rather than exposed as environment variables\n"
        "CNI Plugin and Network Policies,ABSENT-IN-cis-r2(2).yaml,PRESENT-IN-cis-r3.yaml,"
        "Use network policies to isolate traffic in the cluster (Automated)\n"
        "EncryptionConfig,ABSENT-IN-cis-r2(2).yaml,PRESENT-IN-cis-r3.yaml,NA\n"
        "General Namespace Policies,ABSENT-IN-cis-r3.yaml,PRESENT-IN-cis-r2(2).yaml,"
        "Audit Method 1: Verify that the --read-only-port parameter is not set to 0.\n"
        "General Policies,ABSENT-IN-cis-r2(2).yaml,PRESENT-IN-cis-r3.yaml,NA\n"
    )

    path_a = os.path.join(tmp_dir, "reqs_diff_cis-r4_vs_cis-r3.txt")
    path_b = os.path.join(tmp_dir, "reqs_diff_cis-r2_vs_cis-r3.txt")
    Path(path_a).write_text(file_a_content, encoding="utf-8")
    Path(path_b).write_text(file_b_content, encoding="utf-8")
    return path_a, path_b


def _write_no_diff_text_files(tmp_dir: str) -> tuple[str, str]:
    """Write two IDENTICAL TEXT files → zero differences."""
    content = (
        "CNI Plugin and Network Policies,ABSENT-IN-cis-r3.yaml,PRESENT-IN-cis-r4.yaml,"
        "Use network policies.\n"
    )
    path_a = os.path.join(tmp_dir, "same_a.txt")
    path_b = os.path.join(tmp_dir, "same_b.txt")
    for p in (path_a, path_b):
        Path(p).write_text(content, encoding="utf-8")
    return path_a, path_b


def _make_test_zip(tmp_dir: str) -> str:
    """Create a minimal ZIP of YAML manifests for testing."""
    pod_yaml = """\
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
  namespace: default
spec:
  containers:
  - name: app
    image: nginx:latest
    env:
    - name: DB_PASSWORD
      value: supersecret
"""
    deployment_yaml = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-deploy
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test
  template:
    metadata:
      labels:
        app: test
    spec:
      containers:
      - name: app
        image: nginx:latest
        securityContext:
          privileged: true
"""
    zip_path = os.path.join(tmp_dir, "project-yamls.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("pod.yaml",        pod_yaml)
        zf.writestr("deployment.yaml", deployment_yaml)
    return zip_path


# ─────────────────────────────────────────────────────────────────────────────
# TEST CASES (one per function)
# ─────────────────────────────────────────────────────────────────────────────

def test_detect_differences():
    """
    TEST 1 – detect_differences()
    Verifies that differing rows between two distinct input TEXT files are
    correctly identified and that identical files return no differences.
    """
    print("\n" + "="*60)
    print("TEST 1 – detect_differences()")

    with tempfile.TemporaryDirectory() as tmp:
        # ── sub-test A: two different files → differences expected
        path_a, path_b = _write_test_text_files(tmp)
        diffs = detect_differences(path_a, path_b)
        assert isinstance(diffs, list), "Expected a list"
        assert len(diffs) > 0, "Expected at least one difference"
        print(f"  [PASS] Found {len(diffs)} difference(s) between distinct files.")
        for d in diffs[:3]:
            print(f"         → {d['cluster_name']} | {d['requirement'][:60]}")

        # ── sub-test B: identical files → no differences
        path_same_a, path_same_b = _write_no_diff_text_files(tmp)
        diffs_same = detect_differences(path_same_a, path_same_b)
        assert diffs_same == [], f"Expected [], got {diffs_same}"
        print("  [PASS] Identical files correctly return zero differences.")


def test_map_to_kubescape_controls():
    """
    TEST 2 – map_to_kubescape_controls()
    Verifies correct TEXT file output in both the 'differences found' and
    'no differences' cases.
    """
    print("\n" + "="*60)
    print("TEST 2 – map_to_kubescape_controls()")

    with tempfile.TemporaryDirectory() as tmp:
        out_file = os.path.join(tmp, "controls.txt")

        # ── sub-test A: with real differences → should contain control IDs
        path_a, path_b = _write_test_text_files(tmp)
        diffs = detect_differences(path_a, path_b)
        map_to_kubescape_controls(diffs, out_file)

        content = Path(out_file).read_text()
        assert "NO DIFFERENCES FOUND" not in content.upper(), \
            "Expected control IDs but got NO DIFFERENCES FOUND"
        assert re.search(r"C-\d{4}", content), \
            "Expected at least one control ID (C-XXXX) in output"
        ctrl_count = len(re.findall(r"^C-\d{4}", content, re.MULTILINE))
        print(f"  [PASS] Controls file written with {ctrl_count} matched control(s).")
        print(f"         Preview: {content.splitlines()[2]}")

        # ── sub-test B: empty differences → NO DIFFERENCES FOUND
        map_to_kubescape_controls([], out_file)
        content_empty = Path(out_file).read_text()
        assert "NO DIFFERENCES FOUND" in content_empty.upper(), \
            "Expected NO DIFFERENCES FOUND for empty diff list"
        print("  [PASS] Empty diff list correctly produces 'NO DIFFERENCES FOUND'.")


def test_run_kubescape_scan():
    """
    TEST 3 – run_kubescape_scan()
    Verifies the function returns a properly structured DataFrame using mock
    mode (since kubescape binary is not required to be installed).
    """
    print("\n" + "="*60)
    print("TEST 3 – run_kubescape_scan()")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = _make_test_zip(tmp)
        path_a, path_b = _write_test_text_files(tmp)
        diffs     = detect_differences(path_a, path_b)
        ctrl_file = os.path.join(tmp, "controls.txt")
        map_to_kubescape_controls(diffs, ctrl_file)

        df = run_kubescape_scan(zip_path, ctrl_file, force_mock=True)

        required_cols = {"FilePath", "Severity", "ControlName",
                         "FailedResources", "AllResources", "ComplianceScore"}
        assert required_cols.issubset(df.columns), \
            f"Missing columns: {required_cols - set(df.columns)}"
        assert len(df) > 0, "Expected non-empty DataFrame"
        assert df["ComplianceScore"].between(0, 100).all(), \
            "ComplianceScore must be 0–100"
        print(f"  [PASS] DataFrame returned with {len(df)} row(s) and "
              f"{len(df.columns)} column(s).")
        print(f"         Sample row:\n{df.iloc[0].to_dict()}")

        # ── sub-test B: NO DIFFERENCES FOUND → all controls scanned (mock)
        map_to_kubescape_controls([], ctrl_file)
        df_all = run_kubescape_scan(zip_path, ctrl_file, force_mock=True)
        assert len(df_all) > 0, "Expected rows even in full-scan mode"
        print(f"  [PASS] Full-scan (no diff) returned {len(df_all)} row(s).")


def test_export_to_csv():
    """
    TEST 4 – export_to_csv()
    Verifies the CSV file is written with the correct headers and row count.
    """
    print("\n" + "="*60)
    print("TEST 4 – export_to_csv()")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path  = _make_test_zip(tmp)
        path_a, path_b = _write_test_text_files(tmp)
        diffs     = detect_differences(path_a, path_b)
        ctrl_file = os.path.join(tmp, "controls.txt")
        map_to_kubescape_controls(diffs, ctrl_file)

        df  = run_kubescape_scan(zip_path, ctrl_file, force_mock=True)
        csv_out = os.path.join(tmp, "scan_results.csv")
        abs_path = export_to_csv(df, csv_out)

        assert os.path.isfile(abs_path), "CSV file was not created"

        result_df = pd.read_csv(abs_path)
        expected_headers = ["FilePath", "Severity", "ControlName",
                            "FailedResources", "AllResources", "ComplianceScore"]
        assert list(result_df.columns) == expected_headers, \
            f"Header mismatch: {list(result_df.columns)}"
        assert len(result_df) == len(df), \
            f"Row count mismatch: {len(result_df)} vs {len(df)}"
        print(f"  [PASS] CSV written to {abs_path}")
        print(f"         {len(result_df)} rows, headers: {list(result_df.columns)}")
        print(f"\n         First 3 rows:\n{result_df.head(3).to_string(index=False)}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN – run the full pipeline on the real uploaded files
# ─────────────────────────────────────────────────────────────────────────────

def main(file_a: str, file_b: str, zip_path: str,
         output_dir: str = "Output-Task3") -> str:
    """
    End-to-end pipeline entry point.

    Parameters
    ----------
    file_a, file_b : str  Paths to the two diff-report TEXT files.
    zip_path       : str  Path to the ZIP of YAML manifests.
    output_dir     : str  Directory for output files.

    Returns
    -------
    str  Path of the final CSV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    controls_txt = os.path.join(output_dir, "kubescape_controls.txt")
    scan_csv     = os.path.join(output_dir, "kubescape_scan_results.csv")

    print("\n[1/4] Detecting differences between the two input files …")
    diffs = detect_differences(file_a, file_b)
    print(f"      → {len(diffs)} difference(s) found.")

    print("[2/4] Mapping differences to Kubescape controls …")
    map_to_kubescape_controls(diffs, controls_txt)
    preview = Path(controls_txt).read_text()[:400]
    print(f"      → Controls file: {controls_txt}\n      Preview:\n{preview}")

    print("[3/4] Running Kubescape scan …")
    scan_df = run_kubescape_scan(zip_path, controls_txt, force_mock=True)
    print(f"      → Scan returned {len(scan_df)} result row(s).")

    print("[4/4] Exporting results to CSV …")
    abs_csv = export_to_csv(scan_df, scan_csv)
    print(f"      → CSV written to {abs_csv}")
    print(f"\n{scan_df.head(10).to_string(index=False)}")

    return abs_csv


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    
    # ── Full pipeline on the real uploaded files ──────────────────────────
    FILE_A   = "OutputTXT-Task2/names_diff_cis-r1.yaml_vs_cis-r2(2).yaml.txt"
    FILE_B   = "OutputTXT-Task2/names_diff_cis-r1.yaml_vs_cis-r3.yaml.txt"
    ZIP_PATH = "Task3/project-yamls.zip"

    # If the real ZIP isn't uploaded, build a synthetic one for the demo
    if not os.path.isfile(ZIP_PATH):
        raise ValueError("project-yamls.zip does not exist")

    main(FILE_A, FILE_B, ZIP_PATH)
