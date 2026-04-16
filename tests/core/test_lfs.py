import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

from ctfcli.core.lfs import HttpArtifactHandler, S3ArtifactHandler, fetch_artifact


class TestHttpArtifactHandler(unittest.TestCase):
    @staticmethod
    def _response_with_body(content: bytes):
        response = mock.MagicMock()
        response.read.side_effect = [content, b""]
        context = mock.MagicMock()
        context.__enter__.return_value = response
        context.__exit__.return_value = False
        return context

    @mock.patch("ctfcli.core.lfs.time.sleep")
    @mock.patch("ctfcli.core.lfs.urlopen")
    def test_retries_transient_errors_with_default_backoff(self, mock_urlopen: mock.MagicMock, mock_sleep: mock.MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "artifact.bin"

            mock_urlopen.side_effect = [
                URLError("temporary"),
                self._response_with_body(b"ok"),
            ]

            HttpArtifactHandler.fetch("https://downloads.invalid/artifact.bin", destination)

            self.assertEqual(destination.read_bytes(), b"ok")
            self.assertEqual(mock_urlopen.call_count, 2)
            mock_urlopen.assert_has_calls(
                [
                    mock.call("https://downloads.invalid/artifact.bin", timeout=300.0),
                    mock.call("https://downloads.invalid/artifact.bin", timeout=300.0),
                ]
            )
            mock_sleep.assert_called_once_with(1.0)

    @mock.patch("ctfcli.core.lfs.time.sleep")
    @mock.patch("ctfcli.core.lfs.urlopen")
    def test_does_not_retry_non_retryable_http_4xx(
        self, mock_urlopen: mock.MagicMock, mock_sleep: mock.MagicMock
    ):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "artifact.bin"

            mock_urlopen.side_effect = HTTPError(
                "https://downloads.invalid/artifact.bin",
                404,
                "not found",
                hdrs=None,
                fp=None,
            )

            with self.assertRaises(HTTPError):
                HttpArtifactHandler.fetch("https://downloads.invalid/artifact.bin", destination)

            self.assertEqual(mock_urlopen.call_count, 1)
            mock_sleep.assert_not_called()

    @mock.patch("ctfcli.core.lfs.time.sleep")
    @mock.patch("ctfcli.core.lfs.urlopen")
    def test_uses_env_config_for_timeout_retries_and_backoff(
        self, mock_urlopen: mock.MagicMock, mock_sleep: mock.MagicMock
    ):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "artifact.bin"

            mock_urlopen.side_effect = [
                URLError("temporary"),
                self._response_with_body(b"ok"),
            ]

            with mock.patch.dict(
                os.environ,
                {
                    "CTFCLI_LFS_HTTP_TIMEOUT_SECONDS": "7",
                    "CTFCLI_LFS_HTTP_RETRIES": "1",
                    "CTFCLI_LFS_HTTP_BACKOFF_SECONDS": "0.25",
                },
                clear=False,
            ):
                HttpArtifactHandler.fetch("https://downloads.invalid/artifact.bin", destination)

            self.assertEqual(destination.read_bytes(), b"ok")
            mock_urlopen.assert_has_calls(
                [
                    mock.call("https://downloads.invalid/artifact.bin", timeout=7.0),
                    mock.call("https://downloads.invalid/artifact.bin", timeout=7.0),
                ]
            )
            mock_sleep.assert_called_once_with(0.25)

    @mock.patch("ctfcli.core.lfs.urlopen")
    def test_streams_response_in_chunks(self, mock_urlopen: mock.MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "artifact.bin"
            response = mock.MagicMock()
            response.read.side_effect = [b"abc", b"def", b""]
            context = mock.MagicMock()
            context.__enter__.return_value = response
            context.__exit__.return_value = False
            mock_urlopen.return_value = context

            with mock.patch.dict(os.environ, {"CTFCLI_LFS_HTTP_CHUNK_SIZE": "3"}, clear=False):
                HttpArtifactHandler.fetch("https://downloads.invalid/artifact.bin", destination)

            self.assertEqual(destination.read_bytes(), b"abcdef")
            response.read.assert_has_calls([mock.call(3), mock.call(3), mock.call(3)])


class TestS3ArtifactHandler(unittest.TestCase):
    def test_supports_s3_scheme(self):
        self.assertTrue(S3ArtifactHandler.supports("s3://bucket/key"))
        self.assertFalse(S3ArtifactHandler.supports("https://downloads.invalid/file.bin"))

    def test_rejects_invalid_s3_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "artifact.bin"
            with self.assertRaises(ValueError):
                S3ArtifactHandler.fetch("s3://bucket", destination)

    @mock.patch("ctfcli.core.lfs.import_module")
    def test_downloads_s3_object_in_chunks(self, mock_import_module: mock.MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "artifact.bin"

            body = mock.MagicMock()
            body.read.side_effect = [b"abc", b"def", b""]
            s3_client = mock.MagicMock()
            s3_client.get_object.return_value = {"Body": body, "ContentLength": 6}

            boto3 = mock.MagicMock()
            boto3.client.return_value = s3_client
            mock_import_module.return_value = boto3

            with mock.patch.dict(os.environ, {"CTFCLI_LFS_S3_CHUNK_SIZE": "3"}, clear=False):
                S3ArtifactHandler.fetch("s3://my-bucket/path/to/object.bin", destination)

            mock_import_module.assert_called_once_with("boto3")
            boto3.client.assert_called_once_with("s3")
            s3_client.get_object.assert_called_once_with(Bucket="my-bucket", Key="path/to/object.bin")
            body.read.assert_has_calls([mock.call(3), mock.call(3), mock.call(3)])
            self.assertEqual(destination.read_bytes(), b"abcdef")

    @mock.patch("ctfcli.core.lfs.import_module", side_effect=ModuleNotFoundError("boto3"))
    def test_errors_if_boto3_is_missing(self, _mock_import_module: mock.MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "artifact.bin"
            with self.assertRaises(RuntimeError):
                S3ArtifactHandler.fetch("s3://my-bucket/path/to/object.bin", destination)

    @mock.patch("ctfcli.core.lfs.S3ArtifactHandler.fetch")
    def test_dispatches_s3_to_s3_handler(self, mock_s3_fetch: mock.MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "artifact.bin"
            fetch_artifact("s3://my-bucket/path/to/object.bin", destination)
            mock_s3_fetch.assert_called_once_with("s3://my-bucket/path/to/object.bin", destination)
