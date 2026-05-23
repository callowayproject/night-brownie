# Container Runtime Abstraction — Specification

> Status: Draft

## 1. Objective

Decouple Night Brownie's container management from the Docker SDK so that agent containers can be started on Docker,
Podman, or Apple Containers without changing harness code.
Current users see no behaviour change; new users pick their preferred runtime in `config.yaml`.

## 2. Scope

### In

| Item | Description |
|------|-------------|
| `ContainerBackend` ABC | Minimal interface covering the five operations `ContainerManager` needs |
| `DockerBackend` | Extracted from the current `containers.py`; wraps Docker SDK |
| `PodmanBackend` | Reuses Docker SDK connected to Podman's Docker-compatible socket |
| `AppleContainersBackend` | Shells out to the `container` CLI (macOS-only) |
| `ContainerManager` refactor | Accepts an injected backend; public API unchanged |
| Config extension | New `containers:` top-level section; `backend_from_config()` factory |
| Updated tests | Each backend fully unit-tested; `ContainerManager` tests backend-agnostic |

### Out of Scope

- Remote container daemons (Docker over TCP, HTTPS)
- Kubernetes / containerd / other runtimes
- Container image builds
- Multi-runtime fallback / health-check routing

## 3. Module Structure

`containers.py` becomes a package.
Existing imports (`from night_brownie.containers import ContainerManager, ContainerError`) remain valid.

```text
night_brownie/containers/
├── __init__.py          # re-exports ContainerManager, ContainerError, ContainerBackend
├── base.py              # ContainerBackend ABC + ContainerBackendConfig + backend_from_config()
├── manager.py           # ContainerManager (refactored; was containers.py)
├── docker.py            # DockerBackend
├── podman.py            # PodmanBackend
└── apple.py             # AppleContainersBackend
```

## 4. `ContainerBackend` ABC

```python
# night_brownie/containers/base.py

from abc import ABC, abstractmethod


class ContainerBackend(ABC):
    """Abstract interface for a container runtime."""

    @abstractmethod
    def image_exists(self, image: str) -> bool:
        """Return True if *image* is present in the local registry."""

    @abstractmethod
    def pull_image(self, image: str) -> None:
        """Pull *image* from the remote registry."""

    @abstractmethod
    def run_container(
        self,
        image: str,
        *,
        name: str,
        port: int,
        environment: dict[str, str] | None = None,
    ) -> str:
        """Start a container and return an opaque handle (ID or name) for later control.

        The container must:
        - Run detached
        - Bind container port 8000 to *port* on localhost
        - Be named *name*
        - Receive *environment* as env vars if provided
        - Auto-remove itself after it stops
        """

    @abstractmethod
    def stop_container(self, handle: str) -> None:
        """Stop the container identified by *handle*."""

    @abstractmethod
    def get_logs(self, handle: str) -> bytes:
        """Return the stdout+stderr log bytes for the container identified by *handle*."""
```

### Design notes

- `run_container` returns an opaque handle — callers must not assume it is a Docker ID or a name.
  `ContainerManager` stores it in `_handles: dict[str, str]` (keyed by `agent_type`).
- `_wait_for_health` is HTTP-based and remains in `ContainerManager` — backends never poll health.
- No `__init__` is prescribed; each backend constructs its client in its own `__init__`.

## 5. Config Extension

### New top-level section in `NightBrownieConfig`

```python
class ContainersConfig(BaseModel):
    backend: Literal["docker", "podman", "apple"] = "docker"
    socket_url: str | None = None
    """Override socket path for Docker or Podman (e.g. unix:///run/user/1000/podman/podman.sock).
    Ignored by the Apple backend."""
```

`NightBrownieConfig` gains:

```python
containers: ContainersConfig = ContainersConfig()
```

### Example YAML

```yaml
# Default — Docker, system socket
containers:
  backend: docker

# Rootless Podman
containers:
  backend: podman
  socket_url: "unix:///run/user/1000/podman/podman.sock"

# Apple Containers (macOS only)
containers:
  backend: apple
```

### Factory

```python
def backend_from_config(config: ContainersConfig) -> ContainerBackend:
    """Instantiate the correct backend from *config*."""
    if config.backend == "docker":
        return DockerBackend(socket_url=config.socket_url)
    if config.backend == "podman":
        return PodmanBackend(socket_url=config.socket_url)
    if config.backend == "apple":
        return AppleContainersBackend()
    raise ContainerError(f"Unknown container backend: {config.backend!r}")
```

## 6. Backend Implementations

### 6.1 `DockerBackend`

Extracted directly from the current `containers.py` logic.
No behaviour change.

```python
class DockerBackend(ContainerBackend):
    def __init__(self, socket_url: str | None = None) -> None:
        try:
            if socket_url:
                self._client = docker.DockerClient(base_url=socket_url)
            else:
                self._client = docker.from_env()
        except docker.errors.DockerException as exc:
            raise ContainerError(f"Docker socket unavailable: {exc}") from exc

    def image_exists(self, image: str) -> bool:
        try:
            self._client.images.get(image)
            return True
        except docker.errors.ImageNotFound:
            return False

    def pull_image(self, image: str) -> None:
        self._client.images.pull(image)

    def run_container(self, image, *, name, port, environment=None) -> str:
        container = self._client.containers.run(
            image,
            detach=True,
            ports={"8000/tcp": port},
            name=name,
            remove=True,
            environment=environment,
        )
        return container.id

    def stop_container(self, handle: str) -> None:
        self._client.containers.get(handle).stop()

    def get_logs(self, handle: str) -> bytes:
        return self._client.containers.get(handle).logs()
```

### 6.2 `PodmanBackend`

Podman exposes a Docker-compatible REST API.
The Docker SDK connects to it via a custom `base_url`.
No Podman-specific Python library is required.

```python
class PodmanBackend(DockerBackend):
    """Podman backend — identical to Docker but defaults to the Podman socket."""

    _DEFAULT_SOCKET = "unix:///run/user/{uid}/podman/podman.sock"

    def __init__(self, socket_url: str | None = None) -> None:
        import os
        url = socket_url or self._DEFAULT_SOCKET.format(uid=os.getuid())
        super().__init__(socket_url=url)
```

`PodmanBackend` is a thin subclass of `DockerBackend`.
If Podman's API diverges in a future version, the subclass is the right place to override individual methods.

### 6.3 `AppleContainersBackend`

Apple Containers has no Python SDK; all operations shell out to the `container` CLI.

```python
class AppleContainersBackend(ContainerBackend):
    """Apple Containers backend — uses the `container` CLI via subprocess."""

    def image_exists(self, image: str) -> bool:
        result = subprocess.run(
            ["container", "images", "list", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True, check=False,
        )
        return image in result.stdout

    def pull_image(self, image: str) -> None:
        subprocess.run(["container", "pull", image], check=True)

    def run_container(self, image, *, name, port, environment=None) -> str:
        cmd = ["container", "run", "--detach", "--rm", "--name", name, "-p", f"{port}:8000"]
        for key, value in (environment or {}).items():
            cmd += ["--env", f"{key}={value}"]
        cmd.append(image)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()  # container ID or name

    def stop_container(self, handle: str) -> None:
        subprocess.run(["container", "stop", handle], check=True)

    def get_logs(self, handle: str) -> bytes:
        result = subprocess.run(
            ["container", "logs", handle], capture_output=True, check=True,
        )
        return result.stdout + result.stderr
```

**Error mapping:** `subprocess.CalledProcessError` from any CLI call must be caught and re-raised
as `ContainerError` at the `ContainerManager` boundary (not inside the backend).

## 7. `ContainerManager` Refactor

The public API is **unchanged**.
Internal changes:

1. `__init__` accepts `backend: ContainerBackend` instead of constructing the Docker client.
2. `_containers` renamed to `_handles: dict[str, str]` (stores opaque handle strings).
3. All Docker SDK calls replaced by `self._backend.<method>()`.
4. `_ensure_image` inlined into `start_agent` as two backend calls (`image_exists` + `pull_image`).

```python
class ContainerManager:
    def __init__(self, backend: ContainerBackend) -> None:
        self._backend = backend
        self._handles: dict[str, str] = {}
        self._envs: dict[str, dict[str, str]] = {}
        self._failed: set[str] = set()
        self._restart_attempts: dict[str, int] = {}
```

`ContainerError` stays in `night_brownie/containers/__init__.py`
(or `base.py`) so it remains importable from `night_brownie.containers`.

## 8. Startup Integration

In `server.py` (or wherever `ContainerManager` is instantiated at startup):

```python
from night_brownie.containers import ContainerManager
from night_brownie.containers.base import backend_from_config

backend = backend_from_config(config.containers)
container_manager = ContainerManager(backend)
```

## 9. Testing Strategy

### Unit tests per backend

Each backend is tested in isolation by mocking its external dependency:

| Backend | Mock target |
|---------|-------------|
| `DockerBackend` | `docker.from_env` / `docker.DockerClient` |
| `PodmanBackend` | Same as Docker (inherits) |
| `AppleContainersBackend` | `subprocess.run` |

### `ContainerManager` tests

Existing `test_containers.py` tests are migrated to inject a `MagicMock` backend.
Tests no longer import `docker`; they only verify
that the manager calls the right backend methods with the right arguments.

### `backend_from_config` tests

Parameterised: for each `backend` value, assert the correct class is instantiated.

### Integration tests (optional)

If Docker is available in CI, a separate `tests/integration/test_docker_backend.py` runs a real container pull + start +
health-check + stop cycle.
Skipped when Docker is unavailable (`pytest.importorskip("docker")` + socket check).

## 10. Dependencies

| Backend | New dependency | Required? |
|---------|---------------|-----------|
| Docker | `docker` (already in `pyproject.toml`) | Yes |
| Podman | None — reuses Docker SDK | No |
| Apple Containers | None — stdlib `subprocess` only | No |

No new packages are added to `pyproject.toml`.

## 11. Backward Compatibility

- `from night_brownie.containers import ContainerManager, ContainerError` continues to work.
- Code that constructs `ContainerManager()` with no arguments **breaks** — it now requires a backend.
  All call sites are within the harness (one location in `server.py`); update them as part of this feature.
- The `containers.py` file is deleted; its content lives in the new package.

## 12. Open Questions

| Question | Decision needed by |
|----------|--------------------|
| Should `PodmanBackend` attempt to auto-discover the socket path on Linux vs. macOS? | Before implementation |
| Does Apple Containers `container run --rm` work the same as Docker? | Validate against CLI docs |
| Should `ContainerError` move to `base.py` or stay in `__init__.py`? | Convention — match `LLMBackend` pattern |
