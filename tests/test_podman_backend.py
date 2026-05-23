"""Tests for night_brownie.containers.podman — PodmanBackend."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from night_brownie.containers.base import ContainerError
from night_brownie.containers.podman import PodmanBackend


class TestPodmanBackendInit:
    """PodmanBackend construction and socket URL resolution."""

    def test_default_socket_includes_uid(self, mocker):
        """PodmanBackend() with no socket_url uses the uid-based XDG default."""
        client = MagicMock()
        mock_docker_client = mocker.patch("docker.DockerClient", return_value=client)
        uid = os.getuid()
        PodmanBackend()
        mock_docker_client.assert_called_once_with(base_url=f"unix:///run/user/{uid}/podman/podman.sock")

    def test_explicit_socket_url_is_passed_through(self, mocker):
        """PodmanBackend(socket_url=...) passes the explicit URL to DockerClient."""
        client = MagicMock()
        mock_docker_client = mocker.patch("docker.DockerClient", return_value=client)
        PodmanBackend(socket_url="unix:///custom/podman.sock")
        mock_docker_client.assert_called_once_with(base_url="unix:///custom/podman.sock")

    def test_raises_container_error_when_socket_unavailable(self, mocker):
        """ContainerError is raised if Podman socket is not reachable."""
        import docker.errors

        mocker.patch("docker.DockerClient", side_effect=docker.errors.DockerException("no socket"))
        with pytest.raises(ContainerError, match="Podman"):
            PodmanBackend()


class TestPodmanBackendInheritsDockerMethods:
    """PodmanBackend inherits all DockerBackend methods."""

    def _make_backend(self, mocker) -> tuple[PodmanBackend, MagicMock]:
        client = MagicMock()
        mocker.patch("docker.DockerClient", return_value=client)
        return PodmanBackend(), client

    def test_image_exists_returns_true_when_found(self, mocker):
        """image_exists returns True when image is found."""
        backend, client = self._make_backend(mocker)
        client.images.get.return_value = MagicMock()
        assert backend.image_exists("img:tag") is True

    def test_image_exists_returns_false_when_not_found(self, mocker):
        """image_exists returns False when image is not found."""
        import docker.errors

        backend, client = self._make_backend(mocker)
        client.images.get.side_effect = docker.errors.ImageNotFound("not found")
        assert backend.image_exists("img:tag") is False

    def test_run_container_returns_container_id(self, mocker):
        """run_container returns the container ID."""
        backend, client = self._make_backend(mocker)
        container = MagicMock()
        container.id = "podman-abc"
        client.containers.run.return_value = container
        result = backend.run_container("img:tag", name="test", port=9001)
        assert result == "podman-abc"
