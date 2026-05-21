"""Abstract base classes and types for container runtime backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


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


class ContainersConfig(BaseModel):
    """Configuration for the container runtime backend."""

    backend: Literal["docker", "podman", "apple"] = "docker"
    socket_url: str | None = None


def backend_from_config(config: ContainersConfig) -> ContainerBackend:
    """Instantiate the appropriate backend from *config*.

    Args:
        config: Container runtime configuration.

    Returns:
        A concrete :class:`ContainerBackend` instance.

    Raises:
        NotImplementedError: Always — backends are wired in later phases.
    """
    raise NotImplementedError(f"backend_from_config not yet implemented for {config.backend!r}")
