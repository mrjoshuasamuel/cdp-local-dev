## 2024-05-24 - Minimize Kubernetes Subprocess Calls in Polling Loops
**Learning:** In local development environments, launching many `kubectl` subprocesses sequentially within a tight polling loop (e.g., `_watch_airflow`) causes significant I/O overhead and slows down the loop's responsiveness.
**Action:** Always fetch Kubernetes resource data (like `pods` and `jobs`) exactly once per iteration at the top of the polling loop, and pass the resulting lists as arguments to any helper functions (like `_all_ready` or `_build_progress_table`) instead of re-fetching them internally.
