## 2024-05-24 - Initial Bolt Journal
**Learning:** Need a journal for critical learnings.
**Action:** Created this file.
## 2024-05-24 - Batching Kubernetes resource deletions
**Learning:** To optimize performance when managing Kubernetes resources in python scripts, multiple resources of the same type should be deleted in a single batched `kubectl delete` command instead of iterating through a loop and running subprocesses for each. This reduces the overhead of invoking the `kubectl` subprocess repeatedly. Note that patch commands like `kubectl patch` must still be run individually.
**Action:** When performing bulk deletion of kubernetes resources like StatefulSets and PVCs, use a list of resources in a single `kubectl delete` call to improve efficiency and reduce subprocess latency.
