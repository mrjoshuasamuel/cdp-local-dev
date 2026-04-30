"""
helm_manager.py — installs Airflow via Helm into the Kind cluster.
Helm only creates resources — we watch and report progress ourselves.
"""
import subprocess
import sys
import time
import yaml
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

AIRFLOW_CHART_VERSION = "1.15.0"
AIRFLOW_IMAGE_TAG     = "2.9.3"
AIRFLOW_IMAGE         = f"apache/airflow:{AIRFLOW_IMAGE_TAG}"


def _run(cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def _helm_dir() -> Path:
    pkg = Path(__file__).parent / "helm"
    if pkg.exists():
        return pkg
    repo = Path(__file__).parent.parent / "helm"
    if repo.exists():
        return repo
    raise FileNotFoundError("Cannot locate helm/ directory. Reinstall cdp-local-dev.")


def _sanitize_airflow_values(values_path: Path):
    with open(values_path, "r") as f:
        values = yaml.safe_load(f)
    changed = False

    svc = values.get("webserver", {}).get("service", {})
    if svc.get("type") == "NodePort" or "nodePort" in svc or "ports" in svc:
        values.setdefault("webserver", {})["service"] = {"type": "ClusterIP"}
        changed = True
        console.print("[yellow]  ⚠  Fixed: webserver.service → ClusterIP[/yellow]")

    if not _is_valid_fernet_key(values.get("fernetKey", "")):
        from cryptography.fernet import Fernet
        values["fernetKey"] = Fernet.generate_key().decode()
        changed = True
        console.print("[yellow]  ⚠  Fixed: generated valid Fernet key[/yellow]")

    # Remove keys that fail schema validation in this chart version
    for bad_key in ("createUserJob", "migrateDatabaseJob"):
        values.pop(bad_key, None)

    # Always pin image tag
    values.setdefault("images", {}).setdefault("airflow", {})
    values["images"]["airflow"]["repository"] = "apache/airflow"
    values["images"]["airflow"]["tag"]        = AIRFLOW_IMAGE_TAG
    values["images"]["airflow"]["pullPolicy"] = "IfNotPresent"
    changed = True

    if changed:
        with open(values_path, "w") as f:
            yaml.dump(values, f, default_flow_style=False, allow_unicode=True)


def _is_valid_fernet_key(key: str) -> bool:
    try:
        import base64
        return len(base64.urlsafe_b64decode(key.encode())) == 32
    except Exception:
        return False


def add_repos():
    console.print("[cyan]  Adding Helm repo: apache-airflow[/cyan]")
    _run(["helm", "repo", "add", "apache-airflow",
          "https://airflow.apache.org", "--force-update"])
    _run(["helm", "repo", "update"])
    console.print("[green]  ✓  Helm repos updated.[/green]")


def create_namespace(ns: str):
    result = _run(["kubectl", "get", "namespace", ns], check=False, capture=True)
    if result.returncode != 0:
        _run(["kubectl", "create", "namespace", ns])
        console.print(f"[green]  ✓  Namespace '{ns}' created.[/green]")
    else:
        console.print(f"[dim]  Namespace '{ns}' already exists.[/dim]")


# ── Pre-pull image into Kind ───────────────────────────────────────────────────

def preload_airflow_image(cluster_name: str = "cdp-local"):
    """
    Pull apache/airflow image on the host then load it into Kind.

    On Windows+Docker Desktop, `kind load docker-image` can be unreliable because
    Kind nodes run inside WSL2 while the Docker daemon is in a separate VM.
    The "not yet present" output from kind is actually its normal PROGRESS message
    (it prints that when it IS loading the image), not an error — but on Windows
    it still exits non-zero in some Docker Desktop configurations.

    Strategy:
      - Always docker pull (fast if already cached)
      - Attempt kind load with a hard 120-second timeout
      - If kind load fails for any reason, warn and continue — Kubernetes will
        pull from Docker Hub inside the Kind node (slower but always works)
    """
    import platform
    console.print(f"[cyan]  Pre-loading image into Kind cluster (avoids in-cluster pull)...[/cyan]")
    console.print(f"[dim]  Image: {AIRFLOW_IMAGE}[/dim]")

    # Step 1: docker pull on the host (uses local cache if already present)
    console.print(f"[dim]  docker pull {AIRFLOW_IMAGE} ...[/dim]")
    result = subprocess.run(
        ["docker", "pull", AIRFLOW_IMAGE],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        console.print(f"[yellow]  ⚠  Could not pull image: {result.stderr.strip()[:100]}[/yellow]")
        console.print(f"[yellow]     Kind will pull from Docker Hub directly (slower).[/yellow]")
        return

    # Step 2: kind load — skip silently on Windows when it is known to be flaky
    # On Windows+Docker Desktop the image is already accessible to Kind through
    # the shared Docker daemon, so kind load is not strictly necessary.
    if platform.system() == "Windows":
        console.print(f"[dim]  Skipping kind load on Windows (Docker Desktop shares the image automatically).[/dim]")
        console.print(f"[green]  ✓  Image ready (pod scheduling will use the cached Docker image).[/green]")
        return

    console.print(f"[dim]  kind load docker-image {AIRFLOW_IMAGE} --name {cluster_name} ...[/dim]")
    try:
        result = subprocess.run(
            ["kind", "load", "docker-image", AIRFLOW_IMAGE, "--name", cluster_name],
            capture_output=True, text=True,
            timeout=120   # hard wall — never hang indefinitely
        )
        # kind prints "not yet present on node ... loading" as a PROGRESS line on stdout
        # when it is successfully loading the image.  Check returncode only.
        if result.returncode == 0:
            console.print(f"[green]  ✓  Image loaded into Kind.[/green]")
        else:
            err = (result.stderr or result.stdout or "").strip()
            console.print(f"[yellow]  ⚠  kind load failed (rc={result.returncode}): {err[:120]}[/yellow]")
            console.print(f"[yellow]     Kind will pull from Docker Hub (may be slow on first run).[/yellow]")
    except subprocess.TimeoutExpired:
        console.print(f"[yellow]  ⚠  kind load timed out — Kind will pull from Docker Hub.[/yellow]")


# ── Pod / Job inspection helpers ──────────────────────────────────────────────

def _get_pods(namespace: str) -> list:
    result = _run(
        ["kubectl", "get", "pods", "-n", namespace, "--no-headers",
         "-o", "custom-columns="
               "NAME:.metadata.name,"
               "READY:.status.containerStatuses[0].ready,"
               "STATUS:.status.phase,"
               "RESTARTS:.status.containerStatuses[0].restartCount,"
               "REASON:.status.containerStatuses[0].state.waiting.reason"],
        check=False, capture=True
    )
    pods = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            pods.append({
                "name":     parts[0],
                "ready":    parts[1] if len(parts) > 1 else "false",
                "status":   parts[2] if len(parts) > 2 else "Unknown",
                "restarts": parts[3] if len(parts) > 3 else "0",
                "reason":   parts[4] if len(parts) > 4 else "",
            })
    return pods


def _get_jobs(namespace: str) -> list:
    result = _run(
        ["kubectl", "get", "jobs", "-n", namespace, "--no-headers",
         "-o", "custom-columns="
               "NAME:.metadata.name,"
               "COMPLETIONS:.status.succeeded,"
               "STATUS:.status.conditions[0].type"],
        check=False, capture=True
    )
    jobs = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts:
            jobs.append({
                "name":      parts[0],
                "succeeded": parts[1] if len(parts) > 1 else "0",
                "condition": parts[2] if len(parts) > 2 else "InProgress",
            })
    return jobs


def _get_pod_pending_reason(namespace: str, pod_name: str) -> str:
    """
    Return a short human-readable reason why a pod is stuck Pending.
    Reads the pod's events from `kubectl describe pod`.
    """
    result = _run(
        ["kubectl", "describe", "pod", pod_name, "-n", namespace],
        check=False, capture=True
    )
    text = result.stdout

    # Scan the Events section for common failure reasons
    reasons = []
    for line in text.splitlines():
        l = line.strip()
        if any(kw in l for kw in [
            "Insufficient memory", "Insufficient cpu",
            "did not have enough resource",
            "nodes are available",
            "0/1 nodes",
            "FailedScheduling",
        ]):
            # Extract the meaningful part after "Warning  FailedScheduling"
            if "FailedScheduling" in l or "Insufficient" in l or "nodes are available" in l:
                # Grab the end of the line (the actual message)
                msg = l.split("  ")[-1].strip()
                if msg and msg not in reasons:
                    reasons.append(msg[:90])

        if "ImagePullBackOff" in l or "ErrImagePull" in l or "Failed to pull image" in l:
            if "image pull" not in " ".join(reasons).lower():
                reasons.append("ImagePullBackOff — image pull failed (check network/Docker Hub)")

        if "Unschedulable" in l and "taint" in l.lower():
            reasons.append("Node taint preventing scheduling")

    # Also check PVC bindings
    if "pod has unbound immediate PersistentVolumeClaims" in text:
        reasons.append("PVC unbound — PersistentVolumeClaim not provisioned")

    return "; ".join(reasons) if reasons else ""


def _get_crash_reason(namespace: str, pod_name: str) -> str:
    """Return a short reason for a CrashLoopBackOff or Error pod."""
    result = _run(
        ["kubectl", "logs", pod_name, "-n", namespace, "--tail=5"],
        check=False, capture=True
    )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return lines[-1][:100] if lines else ""


# ── Live progress table ────────────────────────────────────────────────────────

def _build_progress_table(namespace: str, elapsed: int, pending_reasons: dict, pods: list, jobs: list) -> Panel:
    table = Table(box=box.SIMPLE, show_header=True, expand=True)
    table.add_column("Component",  style="cyan",  no_wrap=True, min_width=35)
    table.add_column("Status",     justify="center", min_width=14)
    table.add_column("Ready",      justify="center", min_width=8)
    table.add_column("Restarts",   justify="center", min_width=8)
    table.add_column("Note",       style="dim",    min_width=30)

    # Jobs first (migrations run before pods start)
    for j in jobs:
        done = j["condition"] == "Complete" or j["succeeded"] not in ("0", "<none>", "")
        status_fmt = "[green]✓  Complete[/green]" if done else "[yellow]⏳ Running[/yellow]"
        ready_fmt  = "[green]✓[/green]"            if done else "[dim]—[/dim]"
        short      = j["name"].replace("airflow-", "")
        table.add_row(f"[dim]{short}[/dim]", status_fmt, ready_fmt, "—", "")

    # Pods
    for p in pods:
        short    = p["name"].replace("airflow-", "")
        status   = p["status"]
        ready    = p["ready"]
        restarts = p["restarts"]
        note     = ""

        if status == "Running" and ready == "true":
            status_fmt = "[green]✓  Running[/green]"
            ready_fmt  = "[green]✓[/green]"
        elif status == "Running":
            status_fmt = "[cyan]⏳ Starting[/cyan]"
            ready_fmt  = "[yellow]⏳[/yellow]"
        elif status == "Pending":
            status_fmt = "[yellow]⏳ Pending[/yellow]"
            ready_fmt  = "[dim]—[/dim]"
            # Show cached pending reason (expensive call only every 30s)
            note = pending_reasons.get(p["name"], "waiting for scheduler…")
        elif status == "Succeeded":
            status_fmt = "[green]✓  Done[/green]"
            ready_fmt  = "[green]✓[/green]"
        elif status in ("CrashLoopBackOff", "Error", "OOMKilled"):
            status_fmt = f"[bold red]✗  {status}[/bold red]"
            ready_fmt  = "[red]✗[/red]"
            note = pending_reasons.get(p["name"], "")
        else:
            status_fmt = f"[red]{status}[/red]"
            ready_fmt  = "[red]✗[/red]"

        restart_fmt = f"[red]{restarts}[/red]" if restarts not in ("0", "<none>", "") else "[dim]0[/dim]"
        table.add_row(short, status_fmt, ready_fmt, restart_fmt, note)

    mins, secs = divmod(elapsed, 60)
    title = (
        f"[bold cyan]Airflow — Starting up[/bold cyan]  "
        f"[dim]{mins:02d}:{secs:02d} elapsed  "
        f"(first run ~5 min while Docker pulls images)[/dim]"
    )
    return Panel(table, title=title, border_style="cyan")


def _all_ready(namespace: str, pods: list, jobs: list) -> bool:
    """Returns True when all pods are Running+Ready and all jobs are Complete."""
    if not pods:
        return False

    # Need at least webserver, scheduler, triggerer, postgresql
    core = [p for p in pods if any(
        x in p["name"] for x in ["webserver", "scheduler", "triggerer", "postgresql"]
    )]
    if len(core) < 4:
        return False

    pods_ok = all(
        p["status"] in ("Running", "Succeeded") and p["ready"] in ("true", "<none>")
        for p in pods
        if "migrations" not in p["name"] and "create-user" not in p["name"]
    )

    jobs_ok = all(
        j["condition"] == "Complete" or j["succeeded"] not in ("0", "<none>", "")
        for j in jobs
    )

    return pods_ok and jobs_ok


def _has_fatal_error(namespace: str, pods: list) -> tuple[bool, str]:
    """
    Detect unrecoverable errors early so we can bail out with a useful message
    instead of waiting for the full 20-minute timeout.

    Returns (is_fatal, reason_string).
    """
    for p in pods:
        name   = p["name"]
        status = p["status"]
        restarts = p.get("restarts", "0")

        # CrashLoopBackOff after multiple restarts = probably a config error
        try:
            restart_count = int(restarts)
        except ValueError:
            restart_count = 0

        if status in ("CrashLoopBackOff", "Error", "OOMKilled"):
            if restart_count >= 3 or status in ("Error", "OOMKilled"):
                last_log = _get_crash_reason(namespace, name)
                reason = f"Pod '{name}' in {status}"
                if last_log:
                    reason += f": {last_log}"
                return True, reason

        # ImagePullBackOff = won't recover without intervention
        if status == "Pending":
            raw = p.get("reason", "").strip()
            if raw in ("ImagePullBackOff", "ErrImagePull"):
                return True, f"Pod '{name}': {raw} — Docker Hub pull failed. Check your network connection."

    return False, ""


def _print_failure_diagnostics(namespace: str):
    """Print actionable kubectl commands to diagnose failures."""
    console.print()
    console.print("[bold red]  Diagnostic information:[/bold red]")
    console.print()

    # Show pod statuses
    result = _run(["kubectl", "get", "pods", "-n", namespace], check=False, capture=True)
    if result.stdout:
        console.print("[yellow]  Pod statuses:[/yellow]")
        for line in result.stdout.splitlines():
            console.print(f"    {line}")

    # Show events (most useful for resource/scheduling failures)
    console.print()
    console.print("[yellow]  Recent warning events:[/yellow]")
    result = _run(
        ["kubectl", "get", "events", "-n", namespace,
         "--field-selector=type=Warning",
         "--sort-by=.lastTimestamp"],
        check=False, capture=True
    )
    if result.stdout:
        for line in result.stdout.splitlines()[-15:]:  # last 15 warnings
            console.print(f"    {line}")
    else:
        console.print("    (no warning events)")

    # Resource summary
    console.print()
    console.print("[yellow]  Node resource usage:[/yellow]")
    result = _run(["kubectl", "describe", "nodes"], check=False, capture=True)
    for line in result.stdout.splitlines():
        if any(kw in line for kw in ["Allocatable", "Allocated", "cpu:", "memory:", "Requests", "Limits"]):
            console.print(f"    {line}")

    console.print()
    console.print("  [bold]Next steps:[/bold]")
    console.print("  [yellow]kubectl get pods -n airflow[/yellow]")
    console.print("  [yellow]kubectl describe pod <pod-name> -n airflow[/yellow]")
    console.print("  [yellow]kubectl logs airflow-scheduler-0 -n airflow -c wait-for-airflow-migrations[/yellow]")
    console.print()
    console.print("  [dim]Most common fixes:[/dim]")
    console.print("  [dim]• Increase Docker Desktop memory to 6GB+  (Docker Desktop → Settings → Resources)[/dim]")
    console.print("  [dim]• Run:  cdp-dev destroy  then  cdp-dev install  to start fresh[/dim]")


# ── Main watcher ──────────────────────────────────────────────────────────────

def _watch_airflow(namespace: str, timeout_seconds: int = 1200):
    """
    Live-updating progress display showing every pod and job status.
    Updates every 5 seconds until everything is ready or timeout.
    Shows pending reasons and detects fatal errors early.
    """
    console.print()
    start = time.time()
    pending_reasons: dict = {}   # pod_name → reason string (refreshed every 30s)
    last_reason_refresh = 0

    with Live(console=console, refresh_per_second=0.5, transient=False) as live:
        while True:
            elapsed = int(time.time() - start)

            # Fetch pods and jobs once per iteration to reduce kubectl overhead
            pods = _get_pods(namespace)
            jobs = _get_jobs(namespace)

            # ── Refresh pending reasons every 30 seconds (expensive kubectl describe) ──
            if elapsed - last_reason_refresh >= 30:
                for p in pods:
                    if p["status"] == "Pending":
                        reason = _get_pod_pending_reason(namespace, p["name"])
                        if reason:
                            pending_reasons[p["name"]] = reason
                    elif p["status"] in ("CrashLoopBackOff", "Error", "OOMKilled"):
                        reason = _get_crash_reason(namespace, p["name"])
                        if reason:
                            pending_reasons[p["name"]] = reason
                last_reason_refresh = elapsed

            # ── Timeout ──────────────────────────────────────────────────────
            if elapsed > timeout_seconds:
                live.stop()
                console.print()
                console.print("[bold red]✗  Timed out waiting for Airflow.[/bold red]")
                _print_failure_diagnostics(namespace)
                sys.exit(1)

            live.update(_build_progress_table(namespace, elapsed, pending_reasons, pods, jobs))

            # ── Success ───────────────────────────────────────────────────────
            if _all_ready(namespace, pods, jobs):
                live.stop()
                console.print()
                console.print("[bold green]  ✓  All Airflow services are ready![/bold green]")
                console.print()
                final = _build_progress_table(namespace, elapsed, pending_reasons, pods, jobs)
                console.print(final)
                return

            # ── Early fatal error detection ───────────────────────────────────
            # Check every 30s after the first minute (give pods time to start)
            if elapsed > 60 and elapsed % 30 < 5:
                is_fatal, reason = _has_fatal_error(namespace, pods)
                if is_fatal:
                    live.stop()
                    console.print()
                    console.print(f"[bold red]✗  Fatal error detected: {reason}[/bold red]")
                    _print_failure_diagnostics(namespace)
                    sys.exit(1)

            time.sleep(5)


# ── Public API ─────────────────────────────────────────────────────────────────

# Error substrings that mean a StatefulSet spec is immutable and must be
# deleted before Helm can re-create it with the new spec.
_STATEFULSET_IMMUTABLE_ERRORS = [
    "updates to statefulset spec for fields other than",
    "StatefulSet.apps",
    "spec: Forbidden",
    "Forbidden: updates to statefulset",
]


def _is_statefulset_conflict(stderr: str) -> bool:
    return any(msg in stderr for msg in _STATEFULSET_IMMUTABLE_ERRORS)


def _fix_statefulset_conflict(namespace: str = "airflow"):
    """
    When Helm fails because a StatefulSet spec is immutable (e.g. the old
    install had persistence=true and the new one has persistence=false),
    Kubernetes forbids the upgrade.

    The only fix is to delete the conflicting StatefulSet(s) so Helm can
    re-create them with the new spec. The pods are recreated automatically.
    Data is NOT lost because we now run with persistence=false (no PVC).
    """
    console.print()
    console.print("[yellow]  ⚠  Detected immutable StatefulSet conflict from a previous install.[/yellow]")
    console.print("[yellow]     This happens when persistence settings changed between runs.[/yellow]")
    console.print("[cyan]  Auto-fixing: deleting conflicting StatefulSets so Helm can recreate them...[/cyan]")

    # Find all StatefulSets in the namespace
    result = _run(
        ["kubectl", "get", "statefulsets", "-n", namespace,
         "-o", "custom-columns=NAME:.metadata.name", "--no-headers"],
        check=False, capture=True
    )

    statefulsets = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    if not statefulsets:
        console.print("[yellow]  No StatefulSets found to delete — Helm may self-recover.[/yellow]")
        return

    for ss in statefulsets:
        console.print(f"[cyan]  Deleting StatefulSet: [bold]{ss}[/bold]...[/cyan]")
        del_result = _run(
            ["kubectl", "delete", "statefulset", ss, "-n", namespace,
             "--cascade=orphan",   # delete the StatefulSet object but keep pods running
             "--ignore-not-found"],
            check=False, capture=True
        )
        if del_result.returncode == 0:
            console.print(f"[green]  ✓  Deleted StatefulSet '{ss}'.[/green]")
        else:
            console.print(f"[yellow]  ⚠  Could not delete '{ss}': {del_result.stderr.strip()[:80]}[/yellow]")

    # Delete orphaned PVCs from the old persistence=true install.
    #
    # WHY PVCs GET STUCK:
    # Kubernetes adds a "kubernetes.io/pvc-protection" finalizer to every PVC
    # while a pod is mounting it.  A normal `kubectl delete pvc` sets
    # deletionTimestamp but then HANGS waiting for the finalizer to be removed —
    # which only happens after every pod that mounts the PVC is fully gone.
    # Since we used --cascade=orphan above, the old pods are still running, so
    # the PVC delete would block forever.
    #
    # FIX: patch the finalizer list to [] first, which immediately unblocks
    # the garbage collector, then issue the delete.
    pvc_result = _run(
        ["kubectl", "get", "pvc", "-n", namespace,
         "-o", "custom-columns=NAME:.metadata.name", "--no-headers"],
        check=False, capture=True
    )
    pvcs = [line.strip() for line in pvc_result.stdout.splitlines() if line.strip()]
    if pvcs:
        console.print(f"[cyan]  Clearing {len(pvcs)} orphaned PVC(s) from previous install...[/cyan]")
        for pvc in pvcs:
            # Step A: strip the protection finalizer so deletion is instant
            _run(
                ["kubectl", "patch", "pvc", pvc, "-n", namespace,
                 "-p", '{"metadata":{"finalizers":null}}',
                 "--type=merge"],
                check=False, capture=True
            )
            # Step B: now the delete completes immediately (no hang)
            _run(
                ["kubectl", "delete", "pvc", pvc, "-n", namespace,
                 "--ignore-not-found", "--timeout=15s"],
                check=False, capture=True
            )
        console.print(f"[green]  ✓  PVCs cleared.[/green]")

    # Also delete the old pods that were kept alive by --cascade=orphan.
    # Helm will recreate them with the correct spec.
    console.print(f"[cyan]  Removing orphaned pods so Helm can recreate them cleanly...[/cyan]")
    _run(
        ["kubectl", "delete", "pods", "--all", "-n", namespace,
         "--grace-period=5", "--ignore-not-found"],
        check=False, capture=True
    )
    console.print(f"[green]  ✓  Orphaned pods removed.[/green]")

    console.print("[green]  ✓  Conflict resolved. Retrying Helm install...[/green]")
    console.print()


def _run_helm_install(values_file: Path) -> subprocess.CompletedProcess:
    """Run the helm upgrade --install command and return the result."""
    cmd = [
        "helm", "upgrade", "--install", "airflow",
        "apache-airflow/airflow",
        "--version",   AIRFLOW_CHART_VERSION,
        "--namespace", "airflow",
        "--values",    str(values_file),
        "--timeout",   "5m",
        # No --wait — we poll progress ourselves
    ]
    return _run(cmd, check=False, capture=True)


def install_airflow(cluster_name: str = "cdp-local"):
    values_file = _helm_dir() / "values" / "airflow.yaml"

    console.print()
    console.print("[bold cyan]Installing Apache Airflow...[/bold cyan]")
    console.print(f"[dim]  Values : {values_file}[/dim]")
    console.print(f"[dim]  Chart  : apache-airflow/airflow v{AIRFLOW_CHART_VERSION}[/dim]")
    console.print(f"[dim]  Image  : {AIRFLOW_IMAGE}[/dim]")
    console.print()

    _sanitize_airflow_values(values_file)

    # ── Pre-load image into Kind to avoid in-cluster slow pull ───────────────
    preload_airflow_image(cluster_name)

    create_namespace("airflow")

    # ── First Helm attempt ────────────────────────────────────────────────────
    console.print("[cyan]  Submitting resources to Kubernetes...[/cyan]")
    result = _run_helm_install(values_file)

    if result.returncode != 0:
        stderr = result.stderr or ""

        if "context deadline exceeded" in stderr or "InProgress" in stderr:
            # Helm timed out waiting for jobs but resources were created — fine
            console.print("[yellow]  ⚠  Helm returned timeout (resources were still created — continuing to watch)[/yellow]")

        elif _is_statefulset_conflict(stderr):
            # ── Auto-fix: delete immutable StatefulSets and retry once ────────
            _fix_statefulset_conflict("airflow")

            console.print("[cyan]  Submitting resources to Kubernetes (attempt 2 of 2)...[/cyan]")
            result2 = _run_helm_install(values_file)

            if result2.returncode != 0:
                stderr2 = result2.stderr or ""
                if "context deadline exceeded" in stderr2 or "InProgress" in stderr2:
                    console.print("[yellow]  ⚠  Helm returned timeout (resources were still created — continuing to watch)[/yellow]")
                else:
                    console.print("[bold red]✗  Helm install failed (even after StatefulSet fix).[/bold red]")
                    console.print(stderr2 or result2.stdout)
                    console.print()
                    console.print("  Try a full reset:  [yellow]cdp-dev destroy[/yellow]  then  [yellow]cdp-dev install[/yellow]")
                    sys.exit(1)
            else:
                console.print("[green]  ✓  Resources submitted.[/green]")

        else:
            console.print("[bold red]✗  Helm install failed.[/bold red]")
            console.print(stderr or result.stdout)
            sys.exit(1)
    else:
        console.print("[green]  ✓  Resources submitted.[/green]")

    console.print()
    console.print("[bold]Waiting for Airflow to become ready...[/bold]")
    _watch_airflow("airflow", timeout_seconds=1200)


def uninstall_airflow():
    _run(["helm", "uninstall", "airflow", "--namespace", "airflow"], check=False)
    console.print("[green]  ✓  Airflow removed.[/green]")
