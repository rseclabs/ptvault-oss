"""Per-request body limits (L-19).

MAX_CONTENT_LENGTH is the 250 MB file-upload limit; it used to be the only limit
on every request, so a JSON body or form post could be just as large. Requests
other than multipart uploads get Config.MAX_JSON_SIZE instead; Werkzeug answers
413 when a body is larger.
"""

import io

from flask import Request, request

from config import Config


def limit_request_body():
    """before_request hook: only multipart file uploads may use the upload limit."""
    if request.mimetype != 'multipart/form-data':
        request.max_content_length = Config.MAX_JSON_SIZE


class JSONFileTooLarge(ValueError):
    """An uploaded JSON file is larger than Config.MAX_JSON_SIZE."""


class InvalidJSONFile(ValueError):
    """An uploaded JSON file does not parse (or nests too deeply)."""


def load_json_upload(file_storage):
    """Parse an uploaded JSON file under the JSON body limit (M-18).

    Multipart requests keep the 250 MB upload limit, so a JSON document sent as
    a file used to be read and parsed whole (about 25x its size in memory). At
    most MAX_JSON_SIZE + 1 bytes are read here, before anything is parsed.
    """
    import json
    data = file_storage.read(Config.MAX_JSON_SIZE + 1)
    if len(data) > Config.MAX_JSON_SIZE:
        raise JSONFileTooLarge(f'JSON files are limited to {Config.MAX_JSON_SIZE // (1024 * 1024)} MB')
    try:
        return json.loads(data)
    except (ValueError, RecursionError) as e:          # RecursionError: nesting too deep
        raise InvalidJSONFile(str(e)[:200]) from None


class PrivateUploadRequest(Request):
    """Keep uploaded files in memory instead of a plaintext temp file (L-29).

    Werkzeug spools uploads over 500 KB to an unlinked file in the system temp
    folder, so evidence that is stored encrypted (M-14) passed through the disk
    in plaintext. The upload is read whole to be encrypted anyway, and its size
    is capped by MAX_CONTENT_LENGTH.
    """

    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        return io.BytesIO()
