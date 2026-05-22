"""Abstract base classes and types for container runtime backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from night_brownie.config import ContainersConfig


class ContainerError(Exception):
    """Raised when a container operation fails."""


class ContainerBackend(ABC):
    """Abstract interface for container runtime backends."""

    @abstractmethod
    def image_exists(self, image: str) -> bool:
        """Return True if *image* is present in the local registry.

        Args:
            image: Image name/tag to check.

        Returns:
            True if the image exists locally, False otherwise.
        """

    @abstractmethod
    def pull_image(self, image: str) -> None:
        """Pull *image* from the registry.

        Args:
            image: Image name/tag to pull.
        """

    @abstractmethod
    def run_container(
        self,
        image: str,
        *,
        name: str,
        port: int,
        environment: dict[str, str] | None = None,
    ) -> str:
        """Start a container and return an opaque handle.

        Args:
            image: Image name/tag to run.
            name: Container name.
            port: Host port to bind to the container's port 8000.
            environment: Optional environment variables.

        Returns:
            An opaque handle string identifying the running container.
        """

    @abstractmethod
    def stop_container(self, handle: str) -> None:
        """Stop the container identified by *handle*.

        Args:
            handle: Opaque handle returned by :meth:`run_container`.
        """

    @abstractmethod
    def get_logs(self, handle: str) -> bytes:
        """Return logs for the container identified by *handle*.

        Args:
            handle: Opaque handle returned by :meth:`run_container`.

        Returns:
            Container log output as bytes.
        """


def backend_from_config(config: ContainersConfig) -> ContainerBackend:
    """Instantiate the appropriate backend from *config*.

    Args:
        config: Container runtime configuration.

    Returns:
        A concrete :class:`ContainerBackend` instance.

    Raises:
        ContainerError: If the backend value is unrecognised.
    """
    if config.backend == "docker":
        from night_brownie.containers.docker import DockerBackend

        return DockerBackend(socket_url=config.socket_url)

    if config.backend == "podman":
        from night_brownie.containers.podman import PodmanBackend

        return PodmanBackend(socket_url=config.socket_url)

    if config.backend == "apple":
        from night_brownie.containers.apple import AppleContainersBackend

        return AppleContainersBackend()

    raise ContainerError(f"Unsupported container backend: {config.backend!r}")
