# Mount Ownership Patterns

## Why Nested Mounts Fail

Docker establishes mounts before the container command runs. If a bind mount hides an image-owned directory and another volume/tmpfs is mounted below it, Docker may create the host-side nested mountpoint as root or obscure the ownership prepared in the image. A later non-root watcher sees `EACCES`, while the host repository gains an attractive little root-owned souvenir.

Prefer this separation:

```text
/source       read-only bind from current worktree
/workspace    project-scoped named volume, runtime-writable
/tmp          UID/GID-owned tmpfs
/home/dev     image-owned home plus explicit cache volumes
```

Avoid this topology when the nested paths do not already exist with proven ownership:

```text
/workspace/app                writable host bind
/workspace/app/node_modules   named volume
/workspace/app/.next          tmpfs
```

## Initialization Strategies

### Image-owned target

Create `/workspace`, cache homes, and temporary directories in the image using numeric ownership. On first mount, verify whether the volume copies image content and ownership on the deployed Docker implementation; do not rely on folklore across runtimes.

### Bounded volume initializer

A one-shot initializer may run with only the privileges required to prepare a new named volume, then exit. The long-running service still runs non-root. Scope `chown` to the volume path and never traverse a bind-mounted repository.

### Read-only source plus non-root synchronization

Copy selected source into the writable workspace or create idempotent links as the runtime user. If links persist in a named volume, use replacement-safe operations such as `ln -sfn` and prove a same-container restart.

## Numeric Identity

Numeric `user: "UID:GID"` avoids depending on `/etc/passwd` name lookup at runtime, but many tools still require a valid home directory and passwd entry. Align all four:

- passwd/group entry;
- numeric runtime user;
- `HOME`;
- ownership of workspace and cache roots.

If the desired UID/GID already exists in a base image, reuse or rename the existing entry instead of creating a duplicate. Never map a root host UID/GID into the dev service; choose a stable non-root fallback and report it.

## Mount Matrix

| Need | Bind | Named volume | tmpfs | Image |
|---|---:|---:|---:|---:|
| Host edits visible instantly | Yes | No | No | No |
| Persist across recreation | Yes | Yes | No | Yes, immutable |
| Project-scoped by Compose | No | Yes | N/A | No |
| High-churn disposable output | Poor | Good | Best | No |
| Host backup/inspection | Direct | Docker-managed | No | Build artifact |
| Ownership controlled at build | Only existing host path | Initial target/init | Mount options | Yes |

## Read-only Root Filesystem

`read_only: true` is compatible with development when every write path is explicit:

- `/workspace` or application output volume;
- `/tmp` tmpfs;
- language/package cache volumes;
- debugger/LSP sockets if used;
- framework-specific state directories.

Start read-only only after tracing writes. Do not respond to failures by making the whole root filesystem writable again; add the missing bounded path.

## Secret and Socket Mounts

Mount credentials read-only and outside source/workspace paths. Prefer secret files with narrow mode to environment variables when tooling supports them. Never copy credentials into a cache volume.

Mounting the Docker socket gives the container infrastructure-level control even if its process UID is non-root. Non-root inside a container is not a force field around a privileged host socket.

## Recovery from Root-Owned Files

1. Stop the service that writes the path.
2. Inspect mount type/source and the live runtime UID/GID.
3. Back up non-disposable data.
4. Fix the Dockerfile/mount/init root cause.
5. Repair only affected paths with explicit ownership.
6. Recreate and prove no new root-owned files appear.

Do not recursively chown an entire repository without inspecting symlinks, submodules, worktrees, and shared mounts.

## Platform Notes

### Linux

Host UID/GID and bind ownership are directly visible. Supplemental groups may be needed for intentional shared host files, but broad groups should not grant Docker-socket access accidentally.

### macOS/Windows Docker Desktop

The VM/file-sharing layer mediates bind ownership and event delivery. Numeric identity still matters inside named volumes and image layers. Test actual writes and watcher behavior rather than inferring from host file metadata.

### WSL2

Keep source under the Linux filesystem for better metadata/event semantics and performance. Windows-mounted paths can behave differently with executable bits, case, symlinks, and file notifications.

## Sources

- Docker bind mounts: https://docs.docker.com/engine/storage/bind-mounts/
- Docker volumes: https://docs.docker.com/engine/storage/volumes/
- Docker tmpfs mounts: https://docs.docker.com/engine/storage/tmpfs/
- Dockerfile `USER`: https://docs.docker.com/reference/dockerfile/#user
- Dev Container user model: https://containers.dev/implementors/json_reference/
- Docker daemon attack surface: https://docs.docker.com/engine/security/
