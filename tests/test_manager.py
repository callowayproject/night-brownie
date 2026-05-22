"""Tests for ContainerManager with injected ContainerBackend."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from night_brownie.containers import ContainerBackend, ContainerError, ContainerManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_backend():
    """Return a MagicMock that satisfies the ContainerBackend interface."""
    backend = MagicMock(spec=ContainerBackend)
    backend.image_exists.return_value = True
    backend.run_container.return_value = "handle-abc123"
    return backend


# ---------------------------------------------------------------------------
# ContainerManager.__init__
# ---------------------------------------------------------------------------


class TestContainerManagerInit:
    """ContainerManager accepts an injected backend; no Docker import required."""

    def test_initializes_with_backend(self, mock_backend):
        """ContainerManager(backend) stores the backend and initialises empty state."""
        mgr = ContainerManager(mock_backend)
        assert mgr is not None
        assert mgr._handles == {}
        assert mgr._envs == {}
        assert mgr._failed == set()
        assert mgr._restart_attempts == {}

    def test_no_docker_import_needed(self, mock_backend):
        """ContainerManager can be constructed without any Docker connectivity."""
        # If this test runs, Docker is irrelevant — the mock is enough.
        mgr = ContainerManager(mock_backend)
        assert mgr._backend is mock_backend


# ---------------------------------------------------------------------------
# start_agent — image handling
# ---------------------------------------------------------------------------


class TestStartAgentImageHandling:
    """start_agent delegates image checks to the backend."""

    def test_pulls_image_when_not_present(self, mock_backend, mocker):
        """pull_image is called when image_exists returns False."""
        mock_backend.image_exists.return_value = False

        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)

        mgr.start_agent("issue-triage", image="night-brownie-issue-triage:latest", port=9001)

        mock_backend.pull_image.assert_called_once_with("night-brownie-issue-triage:latest")

    def test_skips_pull_when_image_present(self, mock_backend, mocker):
        """pull_image is NOT called when image_exists returns True."""
        mock_backend.image_exists.return_value = True

        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)

        mgr.start_agent("issue-triage", image="night-brownie-issue-triage:latest", port=9001)

        mock_backend.pull_image.assert_not_called()


# ---------------------------------------------------------------------------
# start_agent — container startup and URL return
# ---------------------------------------------------------------------------


class TestStartAgentContainer:
    """start_agent returns the container URL and stores the handle internally."""

    def test_returns_container_url(self, mock_backend, mocker):
        """start_agent returns http://localhost:<port>."""
        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)

        url = mgr.start_agent("issue-triage", image="night-brownie-issue-triage:latest", port=9001)

        assert url == "http://localhost:9001"

    def test_handle_registered_internally(self, mock_backend, mocker):
        """The opaque handle returned by run_container is stored in _handles."""
        mock_backend.run_container.return_value = "handle-xyz"

        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)

        mgr.start_agent("issue-triage", image="night-brownie-issue-triage:latest", port=9001)

        assert mgr._handles["issue-triage"] == "handle-xyz"

    def test_run_container_called_with_correct_args(self, mock_backend, mocker):
        """run_container receives image, name, port, and environment."""
        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)
        env = {"FOO": "bar"}

        mgr.start_agent("issue-triage", image="img:latest", port=9001, environment=env)

        mock_backend.run_container.assert_called_once_with(
            "img:latest",
            name="night-brownie-issue-triage",
            port=9001,
            environment=env,
        )

    def test_waits_for_health_before_returning(self, mock_backend, mocker):
        """_wait_for_health is called with the container URL."""
        mgr = ContainerManager(mock_backend)
        wait_mock = mocker.patch.object(mgr, "_wait_for_health")

        mgr.start_agent("issue-triage", image="img:latest", port=9001)

        wait_mock.assert_called_once_with("http://localhost:9001")

    def test_get_logs_on_health_failure(self, mock_backend, mocker):
        """get_logs is called (not print) when health check fails."""
        mock_backend.run_container.return_value = "handle-abc"
        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", side_effect=ContainerError("unhealthy"))

        with pytest.raises(ContainerError):
            mgr.start_agent("issue-triage", image="img:latest", port=9001)

        mock_backend.get_logs.assert_called_once_with("handle-abc")

    def test_passes_environment_to_run_container(self, mock_backend, mocker):
        """environment dict is forwarded to run_container."""
        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)
        env = {"SECRET": "value"}

        mgr.start_agent("issue-triage", image="img", port=9001, environment=env)

        assert mock_backend.run_container.call_args.kwargs["environment"] == env


# ---------------------------------------------------------------------------
# stop_all
# ---------------------------------------------------------------------------


class TestStopAll:
    """stop_all delegates to backend.stop_container for every tracked handle."""

    def test_stops_all_managed_containers(self, mock_backend, mocker):
        """stop_container is called for every handle in _handles."""
        mock_backend.run_container.return_value = "handle-abc"

        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)
        mgr.start_agent("issue-triage", image="img:latest", port=9001)

        mgr.stop_all()

        mock_backend.stop_container.assert_called_once_with("handle-abc")

    def test_stop_all_is_idempotent(self, mock_backend, mocker):
        """Calling stop_all twice does not raise an error."""
        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)
        mgr.start_agent("issue-triage", image="img:latest", port=9001)

        mgr.stop_all()
        mgr.stop_all()  # should not raise

    def test_stop_all_clears_handles(self, mock_backend, mocker):
        """After stop_all, _handles is empty."""
        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)
        mgr.start_agent("issue-triage", image="img:latest", port=9001)

        mgr.stop_all()

        assert mgr._handles == {}


# ---------------------------------------------------------------------------
# _wait_for_health — health polling (backend-agnostic, unchanged logic)
# ---------------------------------------------------------------------------


class TestWaitForHealth:
    """_wait_for_health polls /health until the container responds."""

    def test_returns_immediately_when_healthy(self, mock_backend, mocker):
        """No retry when /health returns 200 on first attempt."""
        import httpxyz

        mock_response = MagicMock(spec=httpxyz.Response)
        mock_response.status_code = 200
        mocker.patch("httpxyz.get", return_value=mock_response)

        mgr = ContainerManager(mock_backend)
        mgr._wait_for_health("http://localhost:9001")  # should not raise

    def test_raises_container_error_when_never_healthy(self, mock_backend, mocker):
        """ContainerError is raised when /health never responds within timeout."""
        mocker.patch("httpxyz.get", side_effect=Exception("connection refused"))
        mocker.patch("time.sleep")

        mgr = ContainerManager(mock_backend)
        with pytest.raises(ContainerError, match="health"):
            mgr._wait_for_health("http://localhost:9001", retries=2, delay=0)


# ---------------------------------------------------------------------------
# Unexpected container exit — restart logic
# ---------------------------------------------------------------------------


class TestContainerRestartOnExit:
    """Unexpected container exit triggers one restart attempt via the backend."""

    def test_logs_error_and_restarts_once_on_exit(self, mock_backend, mocker):
        """When a container exits unexpectedly, run_container is called again."""
        mock_backend.run_container.side_effect = ["handle-first", "handle-restarted"]

        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)
        mgr.start_agent("issue-triage", image="img:latest", port=9001)

        mock_logger = mocker.patch("night_brownie.containers.manager.logger")

        mgr.handle_container_exit("issue-triage", image="img:latest", port=9001)

        mock_logger.error.assert_called_once()
        assert mock_backend.run_container.call_count == 2

    def test_handle_updated_after_restart(self, mock_backend, mocker):
        """After restart, _handles holds the new container handle."""
        mock_backend.run_container.side_effect = ["handle-first", "handle-second"]

        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)
        mgr.start_agent("issue-triage", image="img:latest", port=9001)
        mocker.patch("night_brownie.containers.manager.logger")

        mgr.handle_container_exit("issue-triage", image="img:latest", port=9001)

        assert mgr._handles["issue-triage"] == "handle-second"

    def test_marks_failed_after_second_exit(self, mock_backend, mocker):
        """If the restarted container exits again, it is marked failed."""
        mock_backend.run_container.side_effect = ["handle-first", "handle-second"]

        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)
        mgr.start_agent("issue-triage", image="img:latest", port=9001)
        mocker.patch("night_brownie.containers.manager.logger")

        mgr.handle_container_exit("issue-triage", image="img:latest", port=9001)
        mgr.handle_container_exit("issue-triage", image="img:latest", port=9001)

        assert "issue-triage" in mgr._failed

    def test_no_restart_when_already_failed(self, mock_backend, mocker):
        """No run_container call when agent is already in _failed."""
        mgr = ContainerManager(mock_backend)
        mgr._failed.add("issue-triage")
        mock_logger = mocker.patch("night_brownie.containers.manager.logger")

        mgr.handle_container_exit("issue-triage", image="img:latest", port=9001)

        mock_backend.run_container.assert_not_called()
        mock_logger.critical.assert_called_once()


# ---------------------------------------------------------------------------
# Restart preserves environment
# ---------------------------------------------------------------------------


class TestRestartPreservesEnvironment:
    """Environment vars stored at start_agent time are re-used on restart."""

    def test_restart_passes_original_env(self, mock_backend, mocker):
        """The env from start_agent is passed to the restart run_container call."""
        mock_backend.run_container.side_effect = ["handle-first", "handle-second"]

        mgr = ContainerManager(mock_backend)
        mocker.patch.object(mgr, "_wait_for_health", return_value=None)
        env = {"FOO": "bar"}

        mgr.start_agent("issue-triage", image="img", port=9001, environment=env)
        mocker.patch("night_brownie.containers.manager.logger")
        mgr.handle_container_exit("issue-triage", image="img", port=9001)

        restart_call = mock_backend.run_container.call_args_list[1]
        assert restart_call.kwargs["environment"] == env
