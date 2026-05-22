"""Tests for night_brownie.containers.docker — DockerBackend."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from night_brownie.containers.base import ContainerError
from night_brownie.containers.docker import DockerBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_backend(mocker, *, socket_url: str | None = None) -> tuple[DockerBackend, MagicMock]:
    """Return a (DockerBackend, client_mock) pair with docker patched."""
    client = MagicMock()
    if socket_url is not None:
        mocker.patch("docker.DockerClient", return_value=client)
    else:
        mocker.patch("docker.from_env", return_value=client)
    return DockerBackend(socket_url=socket_url), client


# ---------------------------------------------------------------------------
# TestDockerBackendInit
# ---------------------------------------------------------------------------


class TestDockerBackendInit:
    """DockerBackend construction."""

    def test_uses_from_env_when_no_socket_url(self, mocker):
        """DockerBackend() with no socket_url calls docker.from_env()."""
        client = MagicMock()
        mock_from_env = mocker.patch("docker.from_env", return_value=client)
        backend = DockerBackend()
        mock_from_env.assert_called_once()
        assert backend is not None

    def test_uses_docker_client_when_socket_url_given(self, mocker):
        """DockerBackend(socket_url=...) calls docker.DockerClient(base_url=...)."""
        client = MagicMock()
        mock_client_cls = mocker.patch("docker.DockerClient", return_value=client)
        DockerBackend(socket_url="unix:///var/run/docker.sock")
        mock_client_cls.assert_called_once_with(base_url="unix:///var/run/docker.sock")

    def test_raises_container_error_when_socket_unavailable(self, mocker):
        """ContainerError is raised if Docker socket is not reachable."""
        import docker.errors

        mocker.patch("docker.from_env", side_effect=docker.errors.DockerException("no socket"))
        with pytest.raises(ContainerError, match="Docker"):
            DockerBackend()

    def test_raises_container_error_when_socket_url_unavailable(self, mocker):
        """ContainerError is raised if explicit socket URL is not reachable."""
        import docker.errors

        mocker.patch("docker.DockerClient", side_effect=docker.errors.DockerException("refused"))
        with pytest.raises(ContainerError, match="Docker"):
            DockerBackend(socket_url="unix:///bad/path.sock")


# ---------------------------------------------------------------------------
# TestDockerBackendImageExists
# ---------------------------------------------------------------------------


class TestDockerBackendImageExists:
    """DockerBackend.image_exists."""

    def test_returns_true_when_image_present(self, mocker):
        """Returns True when docker.images.get() succeeds."""
        backend, client = _make_backend(mocker)
        client.images.get.return_value = MagicMock()
        assert backend.image_exists("myimage:latest") is True
        client.images.get.assert_called_once_with("myimage:latest")

    def test_returns_false_when_image_not_found(self, mocker):
        """Returns False when docker.images.get() raises ImageNotFound."""
        import docker.errors

        backend, client = _make_backend(mocker)
        client.images.get.side_effect = docker.errors.ImageNotFound("not found")
        assert backend.image_exists("missing:tag") is False


# ---------------------------------------------------------------------------
# TestDockerBackendPullImage
# ---------------------------------------------------------------------------


class TestDockerBackendPullImage:
    """DockerBackend.pull_image."""

    def test_calls_images_pull(self, mocker):
        """pull_image delegates to client.images.pull."""
        backend, client = _make_backend(mocker)
        backend.pull_image("myimage:latest")
        client.images.pull.assert_called_once_with("myimage:latest")


# ---------------------------------------------------------------------------
# TestDockerBackendRunContainer
# ---------------------------------------------------------------------------


class TestDockerBackendRunContainer:
    """DockerBackend.run_container."""

    def test_calls_containers_run_with_correct_kwargs(self, mocker):
        """run_container passes detach, ports, name, remove, environment to containers.run."""
        backend, client = _make_backend(mocker)
        container = MagicMock()
        container.id = "abc123"
        client.containers.run.return_value = container

        result = backend.run_container(
            "myimage:latest",
            name="night-brownie-triage",
            port=9001,
            environment={"FOO": "bar"},
        )

        client.containers.run.assert_called_once_with(
            "myimage:latest",
            detach=True,
            ports={"8000/tcp": 9001},
            name="night-brownie-triage",
            remove=True,
            environment={"FOO": "bar"},
        )
        assert result == "abc123"

    def test_returns_container_id(self, mocker):
        """run_container returns the container's id string."""
        backend, client = _make_backend(mocker)
        container = MagicMock()
        container.id = "deadbeef"
        client.containers.run.return_value = container
        result = backend.run_container("img:tag", name="n", port=8000)
        assert result == "deadbeef"

    def test_no_environment_by_default(self, mocker):
        """run_container passes environment=None when not specified."""
        backend, client = _make_backend(mocker)
        container = MagicMock()
        container.id = "xyz"
        client.containers.run.return_value = container
        backend.run_container("img:tag", name="n", port=8000)
        _, kwargs = client.containers.run.call_args
        assert kwargs["environment"] is None


# ---------------------------------------------------------------------------
# TestDockerBackendStopContainer
# ---------------------------------------------------------------------------


class TestDockerBackendStopContainer:
    """DockerBackend.stop_container."""

    def test_calls_stop_on_container(self, mocker):
        """stop_container fetches the container by handle and calls .stop()."""
        backend, client = _make_backend(mocker)
        container = MagicMock()
        client.containers.get.return_value = container

        backend.stop_container("abc123")

        client.containers.get.assert_called_once_with("abc123")
        container.stop.assert_called_once()


# ---------------------------------------------------------------------------
# TestDockerBackendGetLogs
# ---------------------------------------------------------------------------


class TestDockerBackendStopContainerErrors:
    """DockerBackend.stop_container error handling."""

    def test_wraps_not_found_as_container_error(self, mocker):
        """stop_container raises ContainerError when container is not found."""
        import docker.errors

        backend, client = _make_backend(mocker)
        client.containers.get.side_effect = docker.errors.NotFound("not found")
        with pytest.raises(ContainerError, match="stop"):
            backend.stop_container("gone123")

    def test_wraps_docker_exception_as_container_error(self, mocker):
        """stop_container raises ContainerError for generic DockerException."""
        import docker.errors

        backend, client = _make_backend(mocker)
        client.containers.get.side_effect = docker.errors.DockerException("connection reset")
        with pytest.raises(ContainerError):
            backend.stop_container("abc123")


class TestDockerBackendGetLogs:
    """DockerBackend.get_logs."""

    def test_returns_bytes_from_container_logs(self, mocker):
        """get_logs fetches container by handle and returns .logs() output."""
        backend, client = _make_backend(mocker)
        container = MagicMock()
        container.logs.return_value = b"hello logs"
        client.containers.get.return_value = container

        result = backend.get_logs("abc123")

        client.containers.get.assert_called_once_with("abc123")
        assert result == b"hello logs"
        assert isinstance(result, bytes)

    def test_wraps_not_found_as_container_error(self, mocker):
        """get_logs raises ContainerError when container is not found."""
        import docker.errors

        backend, client = _make_backend(mocker)
        client.containers.get.side_effect = docker.errors.NotFound("not found")
        with pytest.raises(ContainerError, match="logs"):
            backend.get_logs("gone123")

    def test_wraps_docker_exception_as_container_error(self, mocker):
        """get_logs raises ContainerError for generic DockerException."""
        import docker.errors

        backend, client = _make_backend(mocker)
        client.containers.get.side_effect = docker.errors.DockerException("connection reset")
        with pytest.raises(ContainerError):
            backend.get_logs("abc123")
