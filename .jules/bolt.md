## 2023-10-27 - Batching kubectl deletes
**Learning:** For performance optimization in `cdp_dev`, multiple Kubernetes resources of the same type should be deleted in a single batched `kubectl delete` command instead of iterating through a loop. This saves execution time overhead of invoking `kubectl` multiple times.
**Action:** Always batch operations in `kubectl` when the command accepts multiple resource names.
