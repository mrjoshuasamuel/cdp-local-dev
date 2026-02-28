# CDP Local Developer Environment

Run Apache Airflow on a local Kubernetes cluster (Kind) on your laptop —
no cloud account, no VPN, no waiting for Dataproc.

## Prerequisites

| Tool | Min Version | Install |
|------|------------|---------|
| Docker Desktop | 24+ | [docker.com](https://www.docker.com/products/docker-desktop/) — allocate **≥ 8 GB RAM** |
| Python | 3.10+ | `brew install python` / `winget install Python.Python.3.10` |
| Git | 2.30+ | already installed on most systems |

> `kind`, `kubectl`, and `helm` are checked by the CLI — it will tell you if they're missing and how to install them.

---

## Install

```bash
pip install git+https://github.com/<org>/cdp-local-dev.git
```

### First-time setup (~5 minutes)

```bash
cdp-dev install
```

This will:
1. Check all prerequisites
2. Create a local Kubernetes cluster (Kind)
3. Install Apache Airflow via Helm
4. Start port-forwards so you can access Airflow at **http://localhost:8080**

**Login:** `admin` / `admin`

---

## Daily Usage

```bash
# Morning — start the environment after Docker Desktop is running
cdp-dev start

# Check everything is healthy
cdp-dev status

# Tail Airflow logs
cdp-dev logs

# Tail just the scheduler
cdp-dev logs scheduler

# End of day — pause (data is preserved)
cdp-dev stop
```

---

## All Commands

| Command | Description |
|---------|-------------|
| `cdp-dev install` | First-time setup |
| `cdp-dev start` | Resume after reboot or `stop` |
| `cdp-dev stop` | Pause cluster (data preserved) |
| `cdp-dev status` | Pod health + port-forward status |
| `cdp-dev logs [service]` | Tail logs (airflow / scheduler / webserver / worker) |
| `cdp-dev destroy` | Delete everything and start fresh |

---

## Windows WSL2

Run all commands from inside a **WSL2 Ubuntu terminal** (not PowerShell).
Make sure Docker Desktop has WSL2 integration enabled:
> Docker Desktop → Settings → Resources → WSL Integration → Enable for your distro

---

## Apple Silicon (M1 / M2 / M3)

Works natively — Docker Desktop runs Linux/arm64 containers on Apple Silicon.
No extra configuration needed.

---

## Troubleshooting

**`cdp-dev install` fails at Airflow step**
```bash
# Check pod events
kubectl get pods -n airflow
kubectl describe pod <pod-name> -n airflow
```

**Port 8080 already in use**
```bash
# Find and kill the process using 8080
lsof -ti:8080 | xargs kill -9
cdp-dev start
```

**Cluster exists but pods not starting**
```bash
cdp-dev destroy
cdp-dev install
```

---

## What's Next (Phase 2)

- MinIO local object storage (replaces GCS)
- Spark on Kubernetes (replaces Dataproc)
- PostgreSQL for CDP config_db
- `cdp-dev pull-config --pipeline_id` to sync pipeline configs from UDM
- `cdp-dev trigger --pipeline_id` to run a pipeline locally
