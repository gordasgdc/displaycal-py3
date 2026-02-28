"""Utility functions for HTTP multipart/form-data requests.

It includes functions to post fields and files to an HTTP host and to encode
data for multipart form submissions.
"""
# http://code.activestate.com/recipes/146306-http-client-to-post-using-multipartform-data/

from __future__ import annotations

import http.client
import mimetypes
import uuid


def post_multipart(
    host: str,
    selector: str,
    fields: list | tuple,
    files: list | tuple,
    charset: str = "utf-8",
) -> bytes:
    """Post fields and files to an http host as multipart/form-data.

    Args:
        host: The host to post to.
        selector: The URL path to post to.
        fields: A sequence of (name, value) elements for regular form fields.
        files: A sequence of (name, filename, value) elements for data to be
            uploaded as files.
        charset: The character set to use for encoding the fields and files.

    Returns:
        bytes: The server's response page.
    """
    content_type, body = encode_multipart_formdata(fields, files, charset)
    h = http.client.HTTPConnection(host)
    h.putrequest("POST", selector)
    h.putheader("Content-Type", content_type)
    h.putheader("Content-Length", str(len(body)))
    h.endheaders()
    h.send(body)
    resp = h.getresponse()
    return resp.read()


def encode_multipart_formdata(
    fields: tuple | list, files: tuple | list, charset: str = "utf-8"
) -> tuple[bytes, bytes]:
    """Encode fields and files for multipart/form-data.

    Args:
        fields (tuple | list): A sequence of (name, value) elements for regular
            form fields.
        files (tuple | list): A sequence of (name, filename, value) elements
            for data to be uploaded as files.
        charset (str): The character set to use for encoding the fields and
            files.

    Returns:
        tuple[bytes, bytes]: The content type and the body. Ready for
            http.client.HTTP instance.
    """
    boundary = b"----=_NextPart_" + uuid.uuid1().bytes
    crlf = b"\r\n"
    l = []
    for key, value in fields:
        if isinstance(key, str):
            key = key.encode(charset)
        if isinstance(value, str):
            value = value.encode(charset)

        l.append(b"--" + boundary)
        l.append(b'Content-Disposition: form-data; name="' + key + b'"')
        l.append(b"Content-Type: text/plain; charset=" + charset.encode(charset))
        l.append(b"")
        l.append(value)

    for key, filename, value in files:
        if isinstance(key, str):
            key = key.encode(charset)
        if isinstance(filename, str):
            filename = filename.encode(charset)
        if isinstance(value, str):
            value = value.encode(charset)

        l.append(b"--" + boundary)
        l.append(
            b'Content-Disposition: form-data; name="'
            + key
            + b'"; filename="'
            + filename
            + b'"'
        )
        l.append(b"Content-Type: " + get_content_type(filename).encode(charset))
        l.append(b"")
        l.append(value)

    l.append(b"--" + boundary + b"--")
    l.append(b"")
    body = crlf.join(l)
    content_type = b"multipart/form-data; boundary=" + boundary

    return content_type, body


def get_content_type(filename: str | bytes) -> str:
    """Get the content type of a file based on its filename.

    Args:
        filename (str | bytes): The filename to get the content type for.

    Returns:
        str: The content type of the file.
    """
    if isinstance(filename, bytes):
        filename = filename.decode("utf-8")
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
