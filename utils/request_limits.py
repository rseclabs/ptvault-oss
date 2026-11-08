"""Per-request body limits (L-19).

MAX_CONTENT_LENGTH is the 250 MB file-upload limit; it used to be the only limit
on every request, so a JSON body or form post could be just as large. Requests
other than multipart uploads get Config.MAX_JSON_SIZE instead; Werkzeug answers
413 when a body is larger.
"""

from flask import request

from config import Config


def limit_request_body():
    """before_request hook: only multipart file uploads may use the upload limit."""
    if request.mimetype != 'multipart/form-data':
        request.max_content_length = Config.MAX_JSON_SIZE
