## 2024-10-24 - Batching Kubernetes resource deletions
**Learning:** Multiple Kubernetes resources of the same type should be deleted in a single batched `kubectl delete` command instead of iterating through a loop to optimize performance and reduce subprocess overhead.
**Action:** When managing multiple Kubernetes resources of the same kind, ensure to use list arguments to batch delete commands into a single `kubectl` invocation.
