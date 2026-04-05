import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import click


class ArtifactHandler(ABC):
    @staticmethod
    @abstractmethod
    def supports(source: str) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def fetch(source: str, destination: Path) -> None:
        pass


class HttpArtifactHandler(ArtifactHandler):
    @staticmethod
    def _get_env_float(name: str, default: float) -> float:
        value = os.getenv(name)
        if value is None:
            return default

        try:
            parsed = float(value)
            if parsed <= 0:
                return default
            return parsed
        except ValueError:
            return default

    @staticmethod
    def _get_env_int(name: str, default: int) -> int:
        value = os.getenv(name)
        if value is None:
            return default

        try:
            parsed = int(value)
            if parsed < 0:
                return default
            return parsed
        except ValueError:
            return default

    @staticmethod
    def supports(source: str) -> bool:
        parsed = urlparse(source)
        return parsed.scheme in {"http", "https"}

    @staticmethod
    def fetch(source: str, destination: Path) -> None:
        timeout_seconds = HttpArtifactHandler._get_env_float("CTFCLI_LFS_HTTP_TIMEOUT_SECONDS", 300.0)
        max_retries = HttpArtifactHandler._get_env_int("CTFCLI_LFS_HTTP_RETRIES", 2)
        backoff_seconds = HttpArtifactHandler._get_env_float("CTFCLI_LFS_HTTP_BACKOFF_SECONDS", 1.0)
        chunk_size = max(HttpArtifactHandler._get_env_int("CTFCLI_LFS_HTTP_CHUNK_SIZE", 1024 * 1024), 1)

        for attempt in range(max_retries + 1):
            try:
                with urlopen(source, timeout=timeout_seconds) as response, destination.open("wb") as out:
                    content_length = response.headers.get("Content-Length")
                    total_size = int(content_length) if content_length and content_length.isdigit() else None

                    if total_size is not None:
                        with click.progressbar(length=total_size, label=f"Downloading {source}") as progress:
                            while True:
                                chunk = response.read(chunk_size)
                                if not chunk:
                                    break
                                out.write(chunk)
                                progress.update(len(chunk))
                    else:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            out.write(chunk)
                return
            except HTTPError as e:
                non_retryable = 400 <= e.code < 500 and e.code not in [408, 429]
                if non_retryable or attempt == max_retries:
                    raise
            except (TimeoutError, URLError, OSError):
                if attempt == max_retries:
                    raise

            retry_backoff = backoff_seconds * (2**attempt)
            time.sleep(retry_backoff)


def fetch_artifact(source: str, destination: Path) -> None:
    handlers = [HttpArtifactHandler]

    for handler in handlers:
        if handler.supports(source):
            handler.fetch(source, destination)
            return

    parsed = urlparse(source)
    scheme = parsed.scheme or "unknown"
    raise ValueError(f"No artifact handler available for source scheme '{scheme}'")
