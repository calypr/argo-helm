# Persistence

> [!IMPORTANT]
> This deployment uses **Vault Integrated Storage (Raft)** with Kubernetes PersistentVolumeClaims (PVCs)
> to persist Vault data across pod restarts and node failures. Read this document carefully before
> enabling persistence in a shared or production cluster.

## 1. How Vault persistence works with Raft integrated storage

This setup runs Vault using [Integrated Storage](https://developer.hashicorp.com/vault/docs/configuration/storage/raft),
backed by persistent volumes:

- Each Vault server pod in the StatefulSet mounts a **PersistentVolumeClaim**.
- The Raft storage backend writes:
  - The encrypted Vault data (key/value secrets, auth backends, leases, etc.).
  - Raft logs and snapshots used for replication and recovery.
- As long as the underlying PVCs remain intact, Vault’s data survives:
  - Pod restarts
  - Node drains or re-scheduling
  - Helm upgrades of the chart

In Raft mode:

- One Vault node is the **leader**, handling reads and writes.
- Other nodes are **followers**, replicating the Raft log.
- If the leader fails, Raft elects a new leader from the remaining healthy nodes.

The persistence behavior therefore depends on the lifecycle of the **PVCs**:

- If pods are deleted but PVCs remain, **all Vault data is preserved**.
- If PVCs are deleted or the underlying storage is recreated from scratch, Vault behaves like a **new,
  empty cluster** and must be re-initialized.

## 2. Initializing and unsealing Vault with persistent storage

The first time you deploy Vault with persistent storage, the Raft backend is empty and Vault starts in a
**sealed** and **uninitialized** state.

### 2.1 One-time initialization

Run these steps **once per new Raft storage** (per new set of PVCs). Do **not** re-run `vault operator init`
against an already-initialized storage backend.

1. Port-forward or otherwise access the active Vault pod:

   ```bash
   kubectl port-forward -n <namespace> \
     svc/<vault-service-name> 8200:8200
