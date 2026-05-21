# test_apple_backend.py

"""Tests for night_brownie.containers.apple — AppleContainersBackend."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from night_brownie.containers.apple import AppleContainersBackend


def _make_backend() -> AppleContainersBackend:
    return AppleContainersBackend()


class TestAppleContainersBackendImageExists:
    """AppleContainersBackend.image_exists."""

    def test_returns_true_when_image_in_stdout(self, mocker):
        """image_exists returns True when image name appears in container images list output."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout="myrepo/myimage:latest\nother:v1\n")
        backend = _make_backend()
        assert backend.image_exists("myrepo/myimage:latest") is True

    def test_returns_false_when_image_not_in_stdout(self, mocker):
        """image_exists returns False when image name is absent from output."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout="other:v1\n")
        backend = _make_backend()
        assert backend.image_exists("myrepo/myimage:latest") is False

    def test_calls_container_images_list(self, mocker):
        """image_exists invokes `container images list --format ...`."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout="")
        backend = _make_backend()
        backend.image_exists("any:tag")
        mock_run.assert_called_once_with(
            ["container", "images", "list", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            check=False,
        )


class TestAppleContainersBackendPullImage:
    """AppleContainersBackend.pull_image."""

    def test_calls_container_pull(self, mocker):
        """pull_image runs `container pull <image>`."""
        mock_run = mocker.patch("subprocess.run")
        backend = _make_backend()
        backend.pull_image("myrepo/myimage:latest")
        mock_run.assert_called_once_with(["container", "pull", "myrepo/myimage:latest"], check=True)


class TestAppleContainersBackendRunContainer:
    """AppleContainersBackend.run_container — basic invocation."""

    def test_returns_stripped_stdout(self, mocker):
        """run_container returns the stripped stdout of the container run command."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout="container-handle-abc\n")
        backend = _make_backend()
        result = backend.run_container("img:tag", name="night-brownie-triage", port=9001)
        assert result == "container-handle-abc"

    def test_correct_argv_without_env(self, mocker):
        """run_container builds the correct argv: detach, rm, name, port mapping, image."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout="handle\n")
        backend = _make_backend()
        backend.run_container("img:tag", name="night-brownie-triage", port=9001)
        expected_cmd = [
            "container",
            "run",
            "--detach",
            "--rm",
            "--name",
            "night-brownie-triage",
            "-p",
            "9001:8000",
            "img:tag",
        ]
        mock_run.assert_called_once_with(expected_cmd, check=True, capture_output=True, text=True)


class TestAppleContainersBackendRunContainerEnv:
    """AppleContainersBackend.run_container — environment variable handling."""

    def test_each_env_var_emits_env_flag(self, mocker):
        """Each env var produces --env KEY=VALUE in the argv."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout="handle\n")
        backend = _make_backend()
        backend.run_container("img:tag", name="n", port=8000, environment={"FOO": "bar", "BAZ": "qux"})
        cmd = mock_run.call_args[0][0]
        # Both env vars must appear as --env KEY=VALUE pairs before the image
        assert "--env" in cmd
        assert "FOO=bar" in cmd
        assert "BAZ=qux" in cmd
        env_foo_idx = cmd.index("FOO=bar")
        assert cmd[env_foo_idx - 1] == "--env"

    def test_no_env_flags_when_environment_none(self, mocker):
        """No --env flags appear when environment is None."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout="handle\n")
        backend = _make_backend()
        backend.run_container("img:tag", name="n", port=8000, environment=None)
        cmd = mock_run.call_args[0][0]
        assert "--env" not in cmd

    def test_image_is_last_arg(self, mocker):
        """The image name is always the last element of the command."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout="handle\n")
        backend = _make_backend()
        backend.run_container("img:tag", name="n", port=8000, environment={"KEY": "val"})
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == "img:tag"


class TestAppleContainersBackendStopContainer:
    """AppleContainersBackend.stop_container."""

    def test_calls_container_stop(self, mocker):
        """stop_container runs `container stop <handle>`."""
        mock_run = mocker.patch("subprocess.run")
        backend = _make_backend()
        backend.stop_container("container-handle-abc")
        mock_run.assert_called_once_with(["container", "stop", "container-handle-abc"], check=True)


class TestAppleContainersBackendGetLogs:
    """AppleContainersBackend.get_logs."""

    def test_returns_stdout_plus_stderr(self, mocker):
        """get_logs returns stdout + stderr bytes from container logs."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout=b"out\n", stderr=b"err\n")
        backend = _make_backend()
        result = backend.get_logs("container-handle-abc")
        assert result == b"out\nerr\n"

    def test_calls_container_logs(self, mocker):
        """get_logs runs `container logs <handle>` with capture_output=True."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(stdout=b"", stderr=b"")
        backend = _make_backend()
        backend.get_logs("container-handle-abc")
        mock_run.assert_called_once_with(
            ["container", "logs", "container-handle-abc"],
            capture_output=True,
            check=True,
        )


class TestAppleContainersBackendRunContainerFailure:
    """AppleContainersBackend error propagation."""

    def test_called_process_error_propagates_from_run(self, mocker):
        """CalledProcessError from run_container is not swallowed."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["container", "run"]),
        )
        backend = _make_backend()
        with pytest.raises(subprocess.CalledProcessError):
            backend.run_container("img:tag", name="n", port=8000)

    def test_called_process_error_propagates_from_pull(self, mocker):
        """CalledProcessError from pull_image is not swallowed."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["container", "pull"]),
        )
        backend = _make_backend()
        with pytest.raises(subprocess.CalledProcessError):
            backend.pull_image("img:tag")

    def test_called_process_error_propagates_from_stop(self, mocker):
        """CalledProcessError from stop_container is not swallowed."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["container", "stop"]),
        )
        backend = _make_backend()
        with pytest.raises(subprocess.CalledProcessError):
            backend.stop_container("handle")
