# Container Runtime Abstraction — Code Review

> Branch: `container-management` | Reviewed: 2026-05-22
> Verdict: **Request Changes**

The abstraction design is sound and the core implementation is spec-compliant.
Several issues — one security concern, two correctness bugs, a test gap, and a blocking async hazard —
should be addressed before merge.

---

## Critical Issues

None.

---

## Important Issues

### 1. `apple.py:65` — Env var values not sanitised before subprocess injection

`--env KEY=VALUE` args are built from `environment: dict[str, str]` without validation.
A key or value containing `\n` or `\0`
(e.g. a malformed LLM API key) silently corrupts the subprocess argument list in ways that are hard to diagnose.

**Fix:** Validate keys and values before building the argument list.

```python
for key, val in environment.items():
    if "\n" in key or "\n" in val or "\0" in key or "\0" in val:
        raise ContainerError(
            f"Invalid environment variable {key!r}: contains control character"
        )
    cmd += ["--env", f"{key}={val}"]
```

### 2. `docker.py:88-89` — `stop_container` / `get_logs` let `NotFound` propagate unwrapped

`self._client.containers.get(handle)` raises `docker.errors.NotFound` when a container was removed with `remove=True`.
This propagates as an unhandled SDK exception rather than the `ContainerError` the ABC contract implies.
Callers in `manager.py:91` catch bare `Exception` as a workaround, masking the inconsistency.

**Fix:** Wrap both methods in `try/except docker.errors.DockerException` the same way `__init__` does.

### 3. `apple.py:27-33` — `image_exists` returns `False` on any CLI failure

`subprocess.run(..., check=False)` means a missing CLI binary, permission error,
or any other failure silently returns `False`, triggering a pull attempt rather than surfacing the root cause.

**Fix:** Raise `ContainerError` on non-zero exit, or at minimum log a warning.

### 4. `tests/test_backend_from_config.py:72` — "unknown backend" test exercises an unreachable path

`ContainersConfig.model_construct(backend="unknown")` bypasses Pydantic validation,
testing a path that is unreachable at runtime —
Pydantic's `Literal["docker", "podman", "apple"]` rejects `"unknown"` before `backend_from_config` is ever called.

**Fix:** Either add a comment explaining this tests defensive code,
or replace with a test that verifies Pydantic itself rejects the invalid value.

### 5. `tests/test_backend_from_config.py` — No test for `socket_url` set with `backend="apple"`

`AppleContainersBackend` silently ignores `socket_url`.
The behaviour (silently drop, warn, or raise) is unspecified and untested.

**Fix:** Add a test and make the behaviour explicit — either a `ContainerError` or a logged warning.

### 6. `manager.py:96` — `handle_container_exit` silently restarts without credentials after crash recovery

`self._envs.get(agent_type)` returns `None` if `start_agent` was never called (e.g. harness restarted after a crash).
The container restarts without credentials; no error is raised.

**Fix:** Either document clearly that this method must only be called after `start_agent`,
or accept `environment` as an explicit parameter.

### 7. `manager.py` — `_wait_for_health` uses `time.sleep` in an async context

`handle_container_exit` is intended to be called reactively from the running asyncio loop.
A worst-case 30-second `time.sleep` inside `_wait_for_health` will block the entire event loop.

**Fix:** Make `_wait_for_health` async (`asyncio.sleep`) and `await` it,
or document this as a known limitation to address before reactive use is wired in.

---

## Suggestions

| Location | Finding |
|---|---|
| `base.py:8-9` | Add a comment explaining the `TYPE_CHECKING` guard is intentional, not a missing import. |
| `__init__.py:3` | Remove `ContainersConfig` from `night_brownie.containers.__all__`; config types should be imported from `config.py`. |
| `docker.py:99-100` | Remove the unreachable `isinstance(logs, bytes)` branch — `stream=True` is never passed, so `logs` is always `bytes`. |
| `podman.py:9` | Rename `_DEFAULT_SOCKET` → `_DEFAULT_SOCKET_TEMPLATE` to signal it requires `.format()` before use. |
| `apple.py:1` | Remove the spurious `# apple.py` filename comment (no other module does this). |
| `config.example.yaml` | The rootless Podman example hardcodes `uid=1000`, contradicting `PodmanBackend`'s auto-detection via `os.getuid()`. Use `${UID}` or note the default. |

---

## Security Note

The LLM API key (`SecretStr`) is passed as a container environment variable via `__main__.py:200`.
For Docker and Podman, this is standard practice and reasonably safe.
For `AppleContainersBackend` the secret lands in `--env KEY=VALUE` subprocess arguments,
which are **visible in `ps` output and process argument list on macOS** — a meaningful exposure difference.
This should be documented or mitigated before `AppleContainersBackend` is used in production.

---

## What's Done Well

- The five-method ABC with opaque handle semantics is the right abstraction
  level; it works uniformly across Docker (container ID), Podman (container ID),
  and Apple Containers (name string).
- Lazy imports inside `backend_from_config` mean the Docker SDK is never
  imported for non-Docker users — no import cost, no import errors.
- `PodmanBackend(DockerBackend)` as a thin subclass is clean; only `__init__`
  changes and all five methods are inherited for free.
- `stop_all()` is correctly idempotent.
- Test isolation via `mocker.patch.object(DockerBackend, "__init__", return_value=None)`
  avoids real socket connections while still exercising factory dispatch.

---

## Verification Checklist

- [x] Change matches spec requirements
- [x] Core happy-path tests pass
- [ ] `apple.py` — env var sanitisation added
- [ ] `docker.py` — `NotFound` wrapped as `ContainerError`
- [ ] `apple.py` — `image_exists` CLI failure raises / warns
- [ ] `test_backend_from_config.py` — "unknown backend" test clarified or replaced
- [ ] `test_backend_from_config.py` — `apple` + `socket_url` case tested
- [ ] `manager.py` — `handle_container_exit` precondition documented or fixed
- [ ] `manager.py` — `_wait_for_health` async hazard resolved or documented
- [ ] Security note on Apple Containers env var exposure documented
