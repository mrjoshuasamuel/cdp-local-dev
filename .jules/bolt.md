## 2024-05-24 - Batched Kubernetes Resource Deletion
**Learning:** Deleting multiple resources in a loop using `kubectl` introduces significant subprocess overhead. Batching them into a single `kubectl delete` command significantly reduces this overhead.
**Action:** When operating on multiple Kubernetes resources, batch them into a single `kubectl` command by appending the list of resource names.
