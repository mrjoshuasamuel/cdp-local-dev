# CDP Local Developer Environment

Run Apache Airflow on a local Kubernetes cluster (Kind) on your laptop —
no cloud account, no VPN, no waiting for Dataproc.

---

## Install

### Step 1 — Install the package
```bash
pip install git+https://github.com/mrjoshuasamuel/cdp-local-dev.git
```

### Step 2 — Fix PATH (run once)
```bash
python -c "import cdp_dev.bootstrap; cdp_dev.bootstrap" 
```
Or download and run the bootstrap script directly:
```bash
python bootstrap.py
```

This auto-detects where pip installed `cdp-dev` on **your specific machine**
and adds it to PATH permanently. Works on Windows, macOS, and Linux —
no hardcoded paths, no manual steps.

### Step 3 — Install the environment
```bash
cdp-dev install
```

Takes ~5–10 minutes on first run (Docker pulls ~1 GB of images).

**Login:** http://localhost:8080 → `admin` / `admin`

---

## Prerequisites

| Tool | Notes |
|------|-------|
| Docker Desktop | Allocate ≥ 6 GB RAM. `cdp-dev install` will start it automatically if it's not running. |
| Python 3.10+ | Must be installed before pip install |

> `helm`, `kind`, and `kubectl` are installed automatically by `cdp-dev install` if missing.

---

## Daily Usage

```bash
cdp-dev start     # resume after reboot
cdp-dev status    # check pod health
cdp-dev logs      # tail Airflow logs
cdp-dev stop      # pause at end of day
```

---

## All Commands

| Command | Description |
|---------|-------------|
| `cdp-dev install` | First-time setup |
| `cdp-dev start` | Resume after reboot or stop |
| `cdp-dev stop` | Pause cluster (data preserved) |
| `cdp-dev status` | Pod health + port-forward status |
| `cdp-dev logs [service]` | Tail logs (airflow/scheduler/webserver/worker) |
| `cdp-dev destroy` | Delete everything and start fresh |
