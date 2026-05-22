"""Tests for the backend_from_config factory function."""

from __future__ import annotations

import pytest

from night_brownie.config import ContainersConfig
from night_brownie.containers.apple import AppleContainersBackend
from night_brownie.containers.base import ContainerError, backend_from_config
from night_brownie.containers.docker import DockerBackend
from night_brownie.containers.podman import PodmanBackend


class TestBackendFromConfigDocker:
    """backend_from_config with backend='docker'."""

    def test_returns_docker_backend(self, mocker):
        """Returns a DockerBackend instance."""
        mocker.patch.object(DockerBackend, "__init__", return_value=None)
        result = backend_from_config(ContainersConfig(backend="docker"))
        assert isinstance(result, DockerBackend)

    def test_passes_socket_url(self, mocker):
        """socket_url from config is forwarded to DockerBackend."""
        init_mock = mocker.patch.object(DockerBackend, "__init__", return_value=None)
        backend_from_config(ContainersConfig(backend="docker", socket_url="unix:///var/run/docker.sock"))
        init_mock.assert_called_once_with(socket_url="unix:///var/run/docker.sock")

    def test_passes_none_socket_url(self, mocker):
        """None socket_url is forwarded (DockerBackend falls back to from_env)."""
        init_mock = mocker.patch.object(DockerBackend, "__init__", return_value=None)
        backend_from_config(ContainersConfig(backend="docker"))
        init_mock.assert_called_once_with(socket_url=None)


class TestBackendFromConfigPodman:
    """backend_from_config with backend='podman'."""

    def test_returns_podman_backend(self, mocker):
        """Returns a PodmanBackend instance."""
        mocker.patch.object(PodmanBackend, "__init__", return_value=None)
        result = backend_from_config(ContainersConfig(backend="podman"))
        assert isinstance(result, PodmanBackend)

    def test_passes_socket_url(self, mocker):
        """Explicit socket_url is forwarded to PodmanBackend."""
        init_mock = mocker.patch.object(PodmanBackend, "__init__", return_value=None)
        url = "unix:///run/user/1000/podman/podman.sock"
        backend_from_config(ContainersConfig(backend="podman", socket_url=url))
        init_mock.assert_called_once_with(socket_url=url)

    def test_passes_none_socket_url(self, mocker):
        """None socket_url lets PodmanBackend derive the uid-based default."""
        init_mock = mocker.patch.object(PodmanBackend, "__init__", return_value=None)
        backend_from_config(ContainersConfig(backend="podman"))
        init_mock.assert_called_once_with(socket_url=None)


class TestBackendFromConfigApple:
    """backend_from_config with backend='apple'."""

    def test_returns_apple_backend(self, mocker):
        """Returns an AppleContainersBackend instance."""
        mocker.patch.object(AppleContainersBackend, "__init__", return_value=None)
        result = backend_from_config(ContainersConfig(backend="apple"))
        assert isinstance(result, AppleContainersBackend)


class TestBackendFromConfigErrors:
    """backend_from_config raises ContainerError for unsupported backends."""

    def test_raises_for_unknown_backend(self):
        """ContainerError is raised when backend value is unrecognised."""
        config = ContainersConfig.model_construct(backend="unknown")
        with pytest.raises(ContainerError, match="Unsupported"):
            backend_from_config(config)
