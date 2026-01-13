from __future__ import annotations

from pathlib import Path
from typing import BinaryIO


class HttpUtils:
    @staticmethod
    def _guess_mime_type(path: Path) -> str:
        """Guess MIME type from file extension.

        Args:
            path: File path

        Returns:
            MIME type string
        """
        import mimetypes

        mime_type, _ = mimetypes.guess_type(str(path))
        return mime_type or "application/octet-stream"

    @staticmethod
    def open_multipart_files(
        files: dict[str, Path],
    ) -> dict[str, tuple[str, BinaryIO, str]]:
        multipart: dict[str, tuple[str, BinaryIO, str]] = {}

        for field, path in files.items():
            multipart[field] = (
                path.name,
                path.open("rb"),  # BinaryIO
                HttpUtils._guess_mime_type(path),
            )

        return multipart

    @staticmethod
    def close_multipart_files(multipart: dict[str, tuple[str, BinaryIO, str]]) -> None:
        # Close file handles
        for _name, file_tuple in multipart.items():
            file_handle = file_tuple[1]
            if hasattr(file_handle, "close"):
                _ = file_handle.close()  # type: ignore[union-attr]
        pass

    @staticmethod
    def build_form_data(
        params: dict[str, object] | None,
        priority: int,
    ):
        form_data: dict[str, object] = {"priority": str(priority)}
        if params:
            # Flatten params into form fields
            for key, value in params.items():
                form_data[key] = str(value) if value is not None else ""
