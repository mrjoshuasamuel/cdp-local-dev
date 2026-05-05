
## 2024-05-18 - Batching kubectl deletes
**Learning:** To optimize performance in `cdp_dev`, multiple Kubernetes resources of the same type should be deleted in a single batched `kubectl delete` command instead of iterating through a loop. This avoids the overhead of multiple subprocess calls. Note that `kubectl patch` commands (e.g., removing PVC finalizers) must still be executed individually before the batched deletion.
**Action:** When working with the Kubernetes CLI via python `subprocess`, always check if operations on lists of resources can be batched into a single command invocation to significantly reduce execution time.
