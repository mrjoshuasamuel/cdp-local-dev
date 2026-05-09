## 2026-05-09 - Batch Kubectl Deletions
**Learning:** Calling `kubectl delete` in a loop incurs significant subprocess overhead in this codebase's architecture, which heavily wraps external CLIs for resource management. Multiple identical operations to the same resource API can be slow.
**Action:** Always batch identical resource deletions into a single `kubectl delete [resource] -n [namespace] resource_a resource_b` command instead of iterating, reducing the number of subprocess creations and API roundtrips. (Note: `kubectl patch` must still be done individually before batched deletion.)
