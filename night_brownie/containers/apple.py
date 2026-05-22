"""Apple Containers CLI-based container backend (macOS only)."""

from __future__ import annotations

import subprocess

from night_brownie.containers.base import ContainerBackend, ContainerError


class AppleContainersBackend(ContainerBackend):
    """ContainerBackend implementation using the Apple Containers CLI.

    Invokes the ``container`` CLI tool available on macOS.
    """

    def image_exists(self, image: str) -> bool:
        """Return True if *image* is present in the local Apple Containers registry.

        Args:
            image: Image name/tag to check.

        Returns:
            True if the image exists locally, False otherwise.
        """
        try:
            result = subprocess.run(
                ["container", "images", "list", "--format", "{{.Repository}}:{{.Tag}}"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise ContainerError(f"Apple Containers CLI failed: {exc.stderr.strip()}") from exc
        return image in result.stdout

    def pull_image(self, image: str) -> None:
        """Pull *image* from the registry using the Apple Containers CLI.

        Args:
            image: Image name/tag to pull.
        """
        subprocess.run(["container", "pull", image], check=True)  # noqa: S603 S607

    def run_container(
        self,
        image: str,
        *,
        name: str,
        port: int,
        environment: dict[str, str] | None = None,
    ) -> str:
        """Start a container and return its name as an opaque handle.

        Args:
            image: Image name/tag to run.
            name: Container name.
            port: Host port to bind to the container's port 8000.
            environment: Optional environment variables.

        Returns:
            The container name (stripped stdout) as the handle.
        """
        cmd = ["container", "run", "--detach", "--rm", "--name", name, "-p", f"{port}:8000"]
        if environment:
            for key, val in environment.items():
                if "\n" in key or "\n" in val or "\0" in key or "\0" in val:
                    raise ContainerError(f"Invalid environment variable {key!r}: contains control character")
                cmd += ["--env", f"{key}={val}"]
        cmd.append(image)
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
        return result.stdout.strip()

    def stop_container(self, handle: str) -> None:
        """Stop the container identified by *handle*.

        Args:
            handle: Container name returned by :meth:`run_container`.
        """
        subprocess.run(["container", "stop", handle], check=True)  # noqa: S603 S607

    def get_logs(self, handle: str) -> bytes:
        """Return logs for the container identified by *handle*.

        Args:
            handle: Container name returned by :meth:`run_container`.

        Returns:
            Combined stdout and stderr bytes from ``container logs``.
        """
        result = subprocess.run(["container", "logs", handle], capture_output=True, check=True)  # noqa: S603 S607
        return result.stdout + result.stderr
