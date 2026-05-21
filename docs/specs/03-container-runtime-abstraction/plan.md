# Container Runtime Abstraction — Implementation Plan

> Spec: [SPEC.md](./SPEC.md) Branch: `container-management`

## Resolved Decisions

| Open question | Decision |
|--------------|----------|
| `PodmanBackend` socket discovery | Single XDG default `unix:///run/user/{uid}/podman/podman.sock` (works rootless on Linux + macOS). Rootful Podman requires explicit `socket_url`. |
| Apple Containers `--rm` | Confirmed supported by Apple Containers CLI. Spec is correct. |
| `ContainerError` location | Lives in `base.py`; re-exported from `__init__.py`. Matches `LLMBackend` pattern. |

## Migration Notes

Current `containers.py` → package.
Breaking changes in the refactor:

- `ContainerManager()` (no args) becomes `ContainerManager(backend)` — update `server.py`.
- `mgr._containers` (dict of Docker container objects) → `mgr._handles` (dict of opaque strings).
    Tests reference `mgr._containers` and must be updated.
- `stop_all` currently calls `container.stop()` on Docker objects → becomes `self._backend.stop_container(handle)`.
- `start_agent` currently `print(self._containers[agent_type].logs())` on health failure → becomes
    `self._backend.get_logs(handle)`.
- `_ensure_image` (private helper) is removed;
    both `start_agent` and `handle_container_exit` inline `image_exists` + `pull_image` backend calls directly.

---

## Phase 1 — Package Scaffold + ABC

**Goal:** Create the `containers/` package with the `ContainerBackend` ABC, `ContainerError`, and factory.
The old `containers.py` stays intact; nothing breaks yet.

- [x] Create directory `night_brownie/containers/`
- [x] Write `night_brownie/containers/base.py`:
    - `ContainerError(Exception)`
    - `ContainerBackend` ABC with five abstract methods: `image_exists`, `pull_image`, `run_container`,
      `stop_container`, `get_logs`
    - `ContainersConfig(BaseModel)` — `backend: Literal["docker","podman","apple"] = "docker"`,
      `socket_url: str | None = None`
    - `backend_from_config(config: ContainersConfig) -> ContainerBackend` factory stub
      (raises `NotImplementedError` for now)
- [x] Write `night_brownie/containers/__init__.py`:
    - Re-exports: `ContainerManager`, `ContainerError`, `ContainerBackend`
    - Import `ContainerManager` from `.manager` (moved early — RUF067 requires **init** be re-exports only)
- [x] Delete `night_brownie/containers.py` and replace with the package

**Acceptance criteria:**

- [x] `from night_brownie.containers import ContainerError, ContainerBackend` works
- [x] `uv run pytest --agent-digest=term --no-cov` passes
    (existing tests still import `ContainerManager` and `ContainerError`)

---

## Phase 2 — `DockerBackend` + `PodmanBackend`

**Goal:** Extract Docker SDK logic into `DockerBackend`; add `PodmanBackend` thin subclass.

- [x] Write `night_brownie/containers/docker.py`:
    - `DockerBackend(ContainerBackend)` — extracted from current `containers.py`
    - `__init__(self, socket_url: str | None = None)` —
      calls `docker.DockerClient(base_url=socket_url)` or `docker.from_env()`;
      wraps `DockerException` → `ContainerError`
    - `image_exists` — `client.images.get(image)` → bool; catches `ImageNotFound`
    - `pull_image` — `client.images.pull(image)`
    - `run_container` — `client.containers.run(...)` with
      `detach=True, ports={"8000/tcp": port}, name=name, remove=True, environment=environment`; returns `container.id`
    - `stop_container` — `client.containers.get(handle).stop()`
    - `get_logs` — `client.containers.get(handle).logs()` → `bytes`
- [x] Write `night_brownie/containers/podman.py`:
    - `PodmanBackend(DockerBackend)` — `_DEFAULT_SOCKET = "unix:///run/user/{uid}/podman/podman.sock"`
    - `__init__(self, socket_url: str | None = None)` — fills in uid-based default;
      calls `super().__init__(socket_url=url)`
- [x] Wire backends into `backend_from_config` in `base.py`
- [x] Write `tests/test_docker_backend.py`:
    - Mock `docker.from_env` / `docker.DockerClient`
    - `TestDockerBackendInit` — socket unavailable → `ContainerError`; `socket_url` → uses `DockerClient`;
      no args → uses `from_env`
    - `TestDockerBackendImageExists` — found → True; `ImageNotFound` → False
    - `TestDockerBackendPullImage` — calls `client.images.pull`
    - `TestDockerBackendRunContainer` — correct kwargs
      (detach, ports, name, remove, environment); returns `container.id`
    - `TestDockerBackendStopContainer` — calls `client.containers.get(handle).stop()`
    - `TestDockerBackendGetLogs` — returns `bytes`
- [x] Write `tests/test_podman_backend.py`:
    - Inherits from Docker tests or patches at the same level
    - Asserts default socket includes uid when no `socket_url` provided
    - Asserts explicit `socket_url` is passed through

**Acceptance criteria:**

- [x] All `test_docker_backend.py` tests pass
- [x] All `test_podman_backend.py` tests pass
- [x] `uv run pytest --agent-digest=term --no-cov` still passes overall

---

## Phase 3 — `AppleContainersBackend`

**Goal:** Subprocess-based backend for the `container` CLI (macOS only).

- [ ] Write `night_brownie/containers/apple.py`:
    - `AppleContainersBackend(ContainerBackend)`
    - `image_exists` —
      `subprocess.run(["container","images","list","--format","{{.Repository}}:{{.Tag}}"], capture_output=True, text=True, check=False)`;
      returns `image in result.stdout`
    - `pull_image` — `subprocess.run(["container","pull",image], check=True)`
    - `run_container` — builds `["container","run","--detach","--rm","--name",name,"-p",f"{port}:8000"]` + env flags;
      `check=True`; returns `result.stdout.strip()`
    - `stop_container` — `subprocess.run(["container","stop",handle], check=True)`
    - `get_logs` — `subprocess.run(["container","logs",handle], capture_output=True, check=True)`;
      returns `result.stdout + result.stderr`
- [ ] Wire `apple` case into `backend_from_config`
- [ ] Write `tests/test_apple_backend.py`:
    - Mock `subprocess.run` throughout
    - `TestAppleContainersBackendImageExists` — image in stdout → True; not in stdout → False
    - `TestAppleContainersBackendPullImage` — calls `container pull <image>`
    - `TestAppleContainersBackendRunContainer` — correct argv (name, port mapping, env flags); returns stripped stdout
    - `TestAppleContainersBackendRunContainerEnv` — each env var emits `["--env","KEY=VALUE"]`
    - `TestAppleContainersBackendStopContainer` — calls `container stop <handle>`
    - `TestAppleContainersBackendGetLogs` — returns `stdout + stderr` bytes
    - `TestAppleContainersBackendRunContainerFailure` — `CalledProcessError` propagates (not swallowed)

**Acceptance criteria:**

- [ ] All `test_apple_backend.py` tests pass
- [ ] `backend_from_config` instantiates correct class for all three `backend` values
- [ ] `uv run pytest --agent-digest=term --no-cov` still passes overall

---

## Phase 4 — `ContainerManager` Refactor

**Goal:** Move `ContainerManager` to `manager.py`; accept injected backend;
replace all Docker SDK calls with backend calls.

- [ ] Write `night_brownie/containers/manager.py` (replaces flat `containers.py` logic):
    - `ContainerManager.__init__(self, backend: ContainerBackend)`:
        - Stores `self._backend = backend`
        - `self._handles: dict[str, str] = {}` (was `_containers: dict[str, Container]`)
        - `self._envs: dict[str, dict[str, str]] = {}`
        - `self._failed: set[str] = set()`
        - `self._restart_attempts: dict[str, int] = {}`
    - `start_agent`:
        - Replace `_ensure_image(image)` with:
          `if not self._backend.image_exists(image): self._backend.pull_image(image)`
        - Replace `self._client.containers.run(...)` with
          `self._backend.run_container(image, name=f"night-brownie-{agent_type}", port=port, environment=environment)`
        - Store returned handle in `self._handles[agent_type]`
        - On health failure: `logger.error(..., logs=self._backend.get_logs(self._handles[agent_type]))`
          (remove `print`)
    - `stop_all`:
        - Iterate `self._handles.items()`; call `self._backend.stop_container(handle)` (was `container.stop()`)
        - Clear `self._handles = {}` (was `self._containers = {}`)
    - `handle_container_exit`:
        - Same restart logic; replace SDK calls with backend calls (image_exists + pull_image + run_container)
        - Store new handle in `self._handles`
    - Remove `_ensure_image` (inlined above)
    - Keep `_wait_for_health` unchanged (HTTP-based, backend-agnostic)
- [ ] Update `night_brownie/containers/__init__.py` — import `ContainerManager` from `.manager`

**Acceptance criteria:**

- [ ] `from night_brownie.containers import ContainerManager, ContainerError, ContainerBackend` works
- [ ] `ContainerManager` can be constructed with a `MagicMock()` backend (no Docker import required)

---

## Phase 5 — Config Extension

**Goal:** Add `ContainersConfig` to `config.py` and wire it into `NightBrownieConfig`.

- [ ] In `night_brownie/config.py`, add after `LLMConfig`:

    ```python
    class ContainersConfig(BaseModel):
      backend: Literal["docker", "podman", "apple"] = "docker"
      socket_url: str | None = None
    ```

- [ ] Add `Literal` to the `typing` import
- [ ] Add to `NightBrownieConfig`:

    ```python
    containers: ContainersConfig = ContainersConfig()
    ```

- [ ] Update `config.example.yaml` with the three example snippets from SPEC.md §5
- [ ] Add tests to `test_config.py`:
    - Default `containers` section → `ContainersConfig(backend="docker", socket_url=None)`
    - Explicit `backend: podman` + `socket_url` → parsed correctly
    - Explicit `backend: apple` → parsed correctly

**Acceptance criteria:**

- [ ] `NightBrownieConfig` loads with no `containers:` key (default docker)
- [ ] `NightBrownieConfig` loads with all three backend values
- [ ] `uv run pytest --agent-digest=term --no-cov` passes

---

## Phase 6 — Migrate `test_containers.py` → `test_manager.py`

**Goal:** Replace Docker-coupled `test_containers.py` with backend-agnostic `test_manager.py`.

- [ ] Create `tests/test_manager.py` — all `ContainerManager` tests inject a `MagicMock()` backend:
    - `@pytest.fixture` `mock_backend()` — `MagicMock(spec=ContainerBackend)`
    - `TestContainerManagerInit` — `ContainerManager(mock_backend)` succeeds; no Docker import
    - `TestStartAgentImageHandling` — mock `backend.image_exists` return value; assert `pull_image` called or not
    - `TestStartAgentContainer` — assert `run_container` called with correct args; `_handles` populated; URL returned
    - `TestStopAll` — assert `stop_container` called for each handle; `_handles` cleared after
    - `TestWaitForHealth` — unchanged logic; mock `httpxyz.get` (already backend-agnostic)
    - `TestContainerRestartOnExit` — assert `run_container` called twice; `_handles` updated;
      `_failed` populated on second exit
    - `TestRestartPreservesEnvironment` — env stored in `_envs` passed to second `run_container` call
- [ ] Write `tests/test_backend_from_config.py`:
    - Parametrize over `("docker", DockerBackend)`, `("podman", PodmanBackend)`, `("apple", AppleContainersBackend)`
    - Mock each backend's `__init__` to avoid real socket/subprocess calls
    - Assert correct class returned
    - Assert `ContainerError` raised for unknown backend string
- [ ] Delete `tests/test_containers.py` (replaced by `test_manager.py`)

**Acceptance criteria:**

- [ ] `test_manager.py` has ≥ same coverage as old `test_containers.py`
- [ ] `test_backend_from_config.py` covers all factory branches
- [ ] No test imports `docker` or calls `docker.from_env` (backend tests excluded)
- [ ] `uv run pytest --agent-digest=term` passes with coverage ≥ 85% line / ≥ 80% branch

---

## Phase 7 — Startup Integration + Final Checks

**Goal:** Wire the backend factory into wherever `ContainerManager` is instantiated; run all checks.

- [ ] In `server.py` (or equivalent startup path), update to:

    ```python
    from night_brownie.containers import ContainerManager
    from night_brownie.containers.base import backend_from_config

    backend = backend_from_config(config.containers)
    container_manager = ContainerManager(backend)
    ```

- [ ] Run `pre-commit run --all-files` — fix any ruff/mypy/interrogate issues
- [ ] Run `uv run pytest --agent-digest=term` — confirm ≥ 85% line / ≥ 80% branch coverage
- [ ] Update `docs/specs/index.md` to mark feature 03 as implemented
- [ ] Confirm `containers.py` is deleted (not lingering alongside the package)

**Acceptance criteria:**

- [ ] `from night_brownie.containers import ContainerManager, ContainerError` still works
- [ ] All pre-commit hooks pass
- [ ] Full test suite green with coverage targets met

---

## Human Review Checkpoint

- [ ] Review complete
- [ ] Approved to merge
