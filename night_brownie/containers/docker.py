"""Docker SDK-based container backend."""

from __future__ import annotations

import docker
import docker.errors

from night_brownie.containers.base import ContainerBackend, ContainerError


class DockerBackend(ContainerBackend):
    """ContainerBackend implementation using the Docker SDK.

    Attributes:
        backend_name: Name of the backend, used for error messages.

    Args:
        socket_url: Optional Docker socket URL. When omitted, uses `docker.from_env()`.

    Raises:
        ContainerError: If the Docker socket is unavailable at construction time.
    """

    backend_name = "Docker"

    def __init__(self, socket_url: str | None = None) -> None:
        try:
            if socket_url is not None:
                self._client = docker.DockerClient(base_url=socket_url)
            else:
                self._client = docker.from_env()
        except docker.errors.DockerException as exc:
            raise ContainerError(
                f"{self.backend_name} socket unavailable — is {self.backend_name} running? ({exc})"
            ) from exc

    def image_exists(self, image: str) -> bool:
        """Return True if `image` is present in the local Docker registry.

        Args:
            image: Image name/tag to check.

        Returns:
            True if the image exists locally, False otherwise.
        """
        try:
            self._client.images.get(image)
            return True
        except docker.errors.ImageNotFound:
            return False

    def pull_image(self, image: str) -> None:
        """Pull `image` from the registry.

        Args:
            image: Image name/tag to pull.
        """
        self._client.images.pull(image)

    def run_container(
        self,
        image: str,
        *,
        name: str,
        port: int,
        environment: dict[str, str] | None = None,
    ) -> str:
        """Start a container and return its ID as an opaque handle.

        Args:
            image: Image name/tag to run.
            name: Container name.
            port: Host port to bind to the container's port 8000.
            environment: Optional environment variables.

        Returns:
            The Docker container ID string.

        Raises:
            ContainerError: If the container fails to start.
        """
        container = self._client.containers.run(
            image,
            detach=True,
            ports={"8000/tcp": port},
            name=name,
            environment=environment,
        )
        if container:
            return container.id
        else:
            raise ContainerError(f"Failed to start container {name!r} with image {image!r}")

    def stop_container(self, handle: str) -> None:
        """Stop the container identified by `handle`.

        Args:
            handle: Container ID returned by `run_container`.

        Raises:
            ContainerError: If the container cannot be found or stopped.
        """
        try:
            container = self._client.containers.get(handle)
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            pass  # already gone — treat as success
        except docker.errors.DockerException as exc:
            raise ContainerError(f"Failed to stop container {handle!r}: {exc}") from exc

    def get_logs(self, handle: str) -> bytes:
        """Return logs for the container identified by `handle`.

        Args:
            handle: Container ID returned by `run_container`.

        Returns:
            Container log output as bytes.

        Raises:
            ContainerError: If the container cannot be found.
        """
        try:
            container = self._client.containers.get(handle)
            logs = container.logs()
            return logs if isinstance(logs, bytes) else b"".join(logs)
        except docker.errors.DockerException as exc:
            raise ContainerError(f"Failed to get logs for container {handle!r}: {exc}") from exc
