## 2024-10-25 - Minimize kubectl subprocess calls
**Learning:** Subprocess I/O in monitoring loops and iterative deletions cause significant performance bottlenecks in this codebase's architecture.
**Action:** Fetch Kubernetes resource data once per iteration and pass it to helper functions. Batch deletions using a single command instead of looping over resources.
