"""Encode a canonical location name into Google's `uule` parameter.

The uule value is a protobuf-style envelope: a fixed prefix, one character
encoding the byte length of the location string (looked up in the base64
alphabet), then the location itself base64-encoded.
"""

import base64

_LENGTH_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


def encode_uule(location: str) -> str:
    raw = location.encode("utf-8")
    if len(raw) >= len(_LENGTH_ALPHABET):
        raise ValueError("location string too long to encode as uule")
    key = _LENGTH_ALPHABET[len(raw)]
    encoded = base64.b64encode(raw).decode("ascii").rstrip("=")
    return f"w+CAIQICI{key}{encoded}"
