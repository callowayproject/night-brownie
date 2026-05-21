# Container Runtime Abstraction

## Problem Statement

How might we let Night Brownie run agent containers on whatever runtime the maintainer already has installed — Docker,
Podman, or Apple Containers — without hard-wiring the harness to the Docker SDK?

## Context

`night_brownie/containers.py` currently imports and calls the Docker Python SDK directly.
Every container operation — pull, run, stop, inspect — goes through `docker.from_env()`.
A user on macOS who prefers Apple Containers
(the new macOS-native runtime introduced in 2025),
or a Linux user running rootless Podman, cannot use Night Brownie without installing Docker.

## Recommended Direction

Extract a `ContainerBackend` ABC modelled on the existing `LLMBackend` abstraction in `night_brownie/llm/base.py`.
Each runtime becomes a concrete implementation:

- `DockerBackend` — wraps the existing Docker SDK logic (no behaviour change for current users)
- `PodmanBackend` — reuses the Docker SDK pointed at Podman's Docker-compatible socket
- `AppleContainersBackend` — shells out to the `container` CLI (no Python SDK exists)

`ContainerManager` is refactored to accept an injected backend; its public API is unchanged.
A factory `backend_from_config()` selects the right implementation from a new top-level `containers:` section in
`config.yaml`.

## Key Assumptions to Validate

- [ ] The Docker Python SDK connects to Podman's socket without modification beyond `base_url` —
    *test by pointing `DockerClient(base_url=...)` at `podman.sock` and running a container*
- [ ] The `container` CLI (Apple Containers) accepts the same image tags as Docker —
    *test by pulling `night-brownie-issue-triage:latest` via `container pull` on macOS*
- [ ] `container run` supports `-p host:container` port mapping and `--env` flags —
    *confirm flags against Apple Containers CLI docs before coding*
- [ ] Subprocess latency for CLI backends is acceptable within the startup path —
    *measure wall-clock time for a `container run` + health-check cycle*

## Out of Scope

- Remote container daemons (Docker over TCP, remote Podman API) — socket-only for now
- Kubernetes / containerd / other runtimes
- Container build — the harness only pulls and runs pre-built images
- Multi-runtime routing (e.g. "try Docker, fall back to Podman")
