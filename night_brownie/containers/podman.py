"""Podman container backend (Docker-compatible API via rootless socket)."""

from __future__ import annotations

import os

from night_brownie.containers.docker import DockerBackend

_DEFAULT_SOCKET_TEMPLATE = "unix:///run/user/{uid}/podman/podman.sock"


class PodmanBackend(DockerBackend):
    """ContainerBackend for Podman using the Docker-compatible socket API.

    Defaults to the XDG rootless socket path for the current user.
    Pass *socket_url* explicitly for rootful Podman or non-standard paths.

    Attributes:
        backend_name: Name of the backend, used for error messages.

    Args:
        socket_url: Optional Podman socket URL. Defaults to the uid-based XDG path.

    Raises:
        ContainerError: If the Podman socket is unavailable at construction time.
    """

    backend_name = "Podman"

    def __init__(self, socket_url: str | None = None) -> None:
        url = socket_url if socket_url is not None else _DEFAULT_SOCKET_TEMPLATE.format(uid=os.getuid())
        super().__init__(socket_url=url)
