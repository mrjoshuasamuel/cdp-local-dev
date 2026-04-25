## 2026-04-23 - Batching Kubectl Commands
**Learning:** Running `kubectl` commands iteratively in a loop introduces significant latency due to repeated CLI subprocess invocations, especially for cleanup operations.
**Action:** When performing `kubectl delete` for multiple resources of the same type (like StatefulSets or PVCs), batched execution by appending all resource names to a single `kubectl delete` command provides a measurable performance improvement in cleanup execution time.
