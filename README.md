# CDP Local Developer Environment

Run Apache Airflow on a local Kubernetes cluster (Kind) on your laptop —
no cloud account, no VPN, no waiting for Dataproc.

---

## Install

```bash
# Step 1 — install the package (python is always on PATH)
pip install git+https://github.com/mrjoshuasamuel/cdp-local-dev.git

# Step 2 — run install (python -m always works, no PATH setup needed)
python -m cdp_dev install
```

On first run, `python -m cdp_dev install` will:
- Automatically install `cdp-dev.bat` into `C:\Windows\System32` (Windows UAC prompt)
- After that, `cdp-dev install` also works in every terminal permanently

**That's it. No manual PATH editing. No bootstrap script. No restart needed.**

---

## Prerequisites

| Tool | Notes |
|------|-------|
| Docker Desktop | Allocate ≥ 6 GB RAM. Started automatically if not running. |
| Python 3.10+ | Must be installed before pip install |

> `helm`, `kind`, and `kubectl` are installed automatically if missing.

---

## Daily Usage

```bash
# These both work after first run:
python -m cdp_dev start     # always works
cdp-dev start               # works after first run

cdp-dev status
cdp-dev logs
cdp-dev stop
```

---

## All Commands

| Command | Description |
|---------|-------------|
| `python -m cdp_dev install` | First-time setup (always works) |
| `cdp-dev install` | First-time setup (works after first run) |
| `cdp-dev start` | Resume after reboot or stop |
| `cdp-dev stop` | Pause cluster (data preserved) |
| `cdp-dev status` | Pod health + port-forward status |
| `cdp-dev logs [service]` | Tail logs (airflow/scheduler/webserver/worker) |
| `cdp-dev destroy` | Delete everything and start fresh |
