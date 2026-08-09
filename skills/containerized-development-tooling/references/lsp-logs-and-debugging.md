# LSP, Logs, and Debugging

## Topology Decision

### Container-resident editor and LSP

Best alignment for container-only SDKs and dependencies. The editor server, LSP, build, and watcher see the same paths and files. Pin editor extensions/features where reproducibility matters.

### Host editor and host LSP

Appropriate when the host intentionally carries the same SDK/toolchain and dependency graph. Keep container outputs separate so host and container do not rewrite incompatible generated metadata.

### Host editor with container LSP bridge

Useful for specialist tooling but requires explicit transport, lifecycle, and path mapping. Do not invent a network-exposed unauthenticated LSP endpoint; prefer editor-supported remote-container mechanisms.

## devcontainer Contract

A `.devcontainer/devcontainer.json` should identify the Compose service/workspace and align user settings:

```json
{
  "name": "project-dev",
  "dockerComposeFile": ["../compose.yaml", "../compose.dev.yaml"],
  "service": "api",
  "workspaceFolder": "/workspace",
  "remoteUser": "dev",
  "shutdownAction": "none"
}
```

Whether `containerUser`, `remoteUser`, or UID-update behavior is appropriate depends on the image and editor implementation. Keep the runtime Compose `user` and filesystem ownership contract authoritative. Never let an editor silently switch the steady-state app to root.

Install LSPs and debuggers in the image or pinned features. Lifecycle hooks may restore project dependencies, but globally installing unpinned tools on every attach is neither fast nor reproducible.

## Generated Code

LSP correctness often depends on generated code:

- protobuf/gRPC stubs;
- OpenAPI clients;
- ORM models/migrations;
- TypeScript declaration output;
- source generators and annotation processors.

After changing the generator, schema, SDK, or plugin:

1. stop the watcher if host/container outputs can conflict;
2. remove only the generated/output boundary;
3. regenerate with the container toolchain;
4. verify generated files/content;
5. reload the project/LSP;
6. run contract tests through the actual client/server path.

Silent unknown-field dropping and stale declarations produce failures without compiler errors. Verify wire behavior, not merely editor calmness.

## Ecosystem Alignment Matrix

| Ecosystem | Container-resident tooling | Inputs that must agree |
|---|---|---|
| C# / F# | Editor-supported .NET language server plus matching SDK | solution/project graph, target framework, NuGet root, generated `obj` |
| TypeScript / JavaScript | workspace TypeScript/tsserver or pinned language-server wrapper | package-manager lockfile, `node_modules`, `tsconfig`, generated declarations |
| Python | Pyright, basedpyright, pylsp, or chosen server | interpreter, virtualenv, import path, generated stubs |
| Rust | rust-analyzer | Rust toolchain, target triple, features, build-script output |
| Go | `gopls` | Go version, module/workspace files, build tags, generated source |
| Java/Kotlin | JDT LS or chosen IDE server | JDK, Maven/Gradle model, annotation processing, generated classes |

Prefer repository-local or image-pinned versions. If the editor injects its own server build, record that behavior and still align the SDK/dependency paths. For TypeScript, selecting the workspace TypeScript version is often as important as where tsserver runs.

## Watcher Matrix

| Symptom | Evidence | Response |
|---|---|---|
| No edit detected | touch/stat inside container, watcher diagnostics | Fix mount/event delivery; enable polling only if required |
| Rebuild occurs, browser stale | app logs, direct origin, proxy/CDN path | Locate stale layer; do not restart everything |
| Watcher says waiting but app down | child PID/socket/readiness | Recreate watcher container |
| Repeated full rebuild | ignored paths, generated/cache mount | Exclude outputs and dependency trees |
| High CPU idle | polling interval/process list | Restore native events or tune bounded polling |
| Old branch served | inspect bind source/project working dir | Recreate from intended worktree |

## Log Collection

Start with:

```bash
docker compose ps --all
docker compose logs --since 10m --timestamps api web
docker inspect container-id --format '{{json .State}}'
```

Then narrow by service/time. Include the first error and enough preceding context to explain it. Separate application stdout/stderr from proxy, database, and Docker daemon events.

Configure log rotation for long-lived development environments. Unbounded JSON logs can fill the Docker data root while everyone debugs the application that is now failing because the disk is full. Comedy does not improve merely because it is recursive.

## Container Inspection

Verify live facts:

```bash
docker inspect container-id --format '{{json .Config.User}}'
docker inspect container-id --format '{{json .Mounts}}'
docker inspect container-id --format '{{json .NetworkSettings.Networks}}'
docker inspect container-id --format '{{json .State.Health}}'
```

Use `docker compose exec` only when the process is running. For crash loops, inspect the image with a one-shot Compose run using the same mounts, network, environment subset, and non-root user; avoid mutating persistent state.

## Debugger Safety

- Node inspector, JDWP, debugpy, Delve, and .NET debugger endpoints can execute code or expose application memory.
- Bind host ports to `127.0.0.1` when host access is required.
- Prefer per-worktree dynamic ports or editor-managed forwarding.
- Never expose debugger endpoints through shared ingress, a public tunnel, or a LAN wildcard firewall rule.
- Add `SYS_PTRACE`/relaxed seccomp only when a debugger requires it and only to that dev service.
- Remove core dumps or dumps containing secrets after controlled analysis.

## Path Mapping

Record the three paths explicitly:

| Layer | Example |
|---|---|
| Host worktree | repository-specific absolute path |
| Container source | `/source` |
| Writable workspace/runtime | `/workspace` |

Configure source maps against the path embedded in stack traces/binaries. Test a breakpoint in source that actually executes; a successful debugger connection with hollow breakpoints is not success.

## Sources

- Language Server Protocol: https://microsoft.github.io/language-server-protocol/
- Development Containers specification: https://containers.dev/implementors/spec/
- Dev Container metadata and user configuration: https://containers.dev/implementors/json_reference/
- Docker logs command: https://docs.docker.com/reference/cli/docker/container/logs/
- Docker health checks: https://docs.docker.com/reference/dockerfile/#healthcheck
- Docker runtime metrics/events: https://docs.docker.com/engine/containers/runmetrics/
