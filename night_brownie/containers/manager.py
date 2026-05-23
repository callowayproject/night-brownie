"""Container lifecycle management for agent containers."""

from __future__ import annotations

import asyncio

import httpxyz
import structlog

from night_brownie.containers.base import ContainerBackend, ContainerError

logger = structlog.get_logger(__name__)


class ContainerManager:
    """Manages container start/stop for configured agent types.

    On startup, pull (if needed) and start agent containers.
    On shutdown, call [`stop_all`][.] to stop them.
    The container lifecycle manager registers URLs with the router after each successful start.

    Args:
        backend: The container runtime backend to use.
    """

    def __init__(self, backend: ContainerBackend) -> None:
        self._backend = backend
        # agent_type → opaque handle string from backend.run_container
        self._handles: dict[str, str] = {}
        # agent_type → environment variables
        self._envs: dict[str, dict[str, str]] = {}
        # agent types that have permanently failed (after one restart attempt)
        self._failed: set[str] = set()
        # track restart attempts per agent_type
        self._restart_attempts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_agent(
        self, agent_type: str, *, image: str, port: int, environment: dict[str, str] | None = None
    ) -> str:
        """Pull (if needed), start the container, wait for health, return URL.

        Args:
            agent_type: Agent type identifier (e.g. `"issue-triage"`).
            image: Container image name/tag to run.
            port: Host port to bind the container's port 8000 to.
            environment: Optional dictionary of environment variables to pass to the container.

        Returns:
            The base URL of the running container (e.g. `"http://localhost:9001"`).

        Raises:
            ContainerError: If the container fails to become healthy.
        """
        if not self._backend.image_exists(image):
            logger.info("Pulling image", image=image)
            self._backend.pull_image(image)

        logger.info("Starting agent container", agent_type=agent_type, image=image)
        handle = self._backend.run_container(
            image,
            name=f"night-brownie-{agent_type}",
            port=port,
            environment=environment,
        )
        self._handles[agent_type] = handle
        if environment:
            self._envs[agent_type] = environment
        self._restart_attempts[agent_type] = 0

        url = f"http://localhost:{port}"
        try:
            await self._wait_for_health(url)
        except ContainerError:
            logger.error("Container failed health check", agent_type=agent_type, logs=self._backend.get_logs(handle))
            raise

        logger.info("Agent container started", agent_type=agent_type, url=url)
        return url

    def stop_all(self) -> None:
        """Stop all managed containers.

        Safe to call multiple times.
        """
        for agent_type, handle in list(self._handles.items()):
            try:
                self._backend.stop_container(handle)
                logger.info("Agent container stopped", agent_type=agent_type)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error stopping container", agent_type=agent_type, error=str(exc))
        self._handles = {}
        self._envs = {}

    async def handle_container_exit(
        self, agent_type: str, *, image: str, port: int, environment: dict[str, str] | None = None
    ) -> None:
        """Handle an unexpected container exit with one restart attempt.

        If the container has already been restarted once and exits again, it is
        marked as permanently failed and no further restart is attempted.

        Args:
            agent_type: Agent type identifier.
            image: Container image to restart.
            port: Host port for the restarted container.
            environment: Environment variables to inject into the restarted container.
                Callers must supply credentials explicitly; there is no implicit fallback.
        """
        if agent_type in self._failed:
            logger.critical("Agent already marked failed — not restarting", agent_type=agent_type)
            return

        attempts = self._restart_attempts.get(agent_type, 0)
        if attempts >= 1:
            logger.critical(
                "Agent container exited after restart — marking failed",
                agent_type=agent_type,
            )
            self._failed.add(agent_type)
            self._handles.pop(agent_type, None)
            return

        logger.error("Agent container exited unexpectedly — attempting restart", agent_type=agent_type)
        self._restart_attempts[agent_type] = attempts + 1

        if not self._backend.image_exists(image):
            self._backend.pull_image(image)

        handle = self._backend.run_container(
            image,
            name=f"night-brownie-{agent_type}",
            port=port,
            environment=environment,
        )
        self._handles[agent_type] = handle

        url = f"http://localhost:{port}"
        try:
            await self._wait_for_health(url)
        except ContainerError:
            logger.critical("Restarted container failed health check — marking failed", agent_type=agent_type)
            self._failed.add(agent_type)
            return

        logger.info("Agent container restarted successfully", agent_type=agent_type, url=url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _wait_for_health(self, url: str, *, retries: int = 30, delay: float = 1.0) -> None:
        """Poll *url*/health until a 200 response is received.

        Args:
            url: Base URL of the container (e.g. `"http://localhost:9001"`).
            retries: Maximum number of attempts before raising.
            delay: Seconds to wait between attempts.

        Raises:
            ContainerError: If the health endpoint does not respond within *retries* attempts.
        """
        health_url = f"{url}/health"
        for attempt in range(retries):
            try:
                response = httpxyz.get(health_url, timeout=2.0)
                if response.status_code == 200:
                    return
            except Exception as exc:  # noqa: BLE001
                logger.debug("Health check attempt failed", url=health_url, attempt=attempt, error=str(exc))
            if attempt < retries - 1:
                await asyncio.sleep(delay)

        raise ContainerError(f"Container at {url} did not pass health check after {retries} attempts")
