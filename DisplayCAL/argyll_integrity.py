# ruff: noqa: E501  (SHA-256 digests are long single tokens)
"""Pinned integrity data for the ArgyllCMS binaries the application downloads.

The download code obtains the expected SHA-256 of an ``argyllcms-binaries``
release asset from the GitHub API. If that lookup fails (offline API, rate
limit, missing ``digest`` field) the file used to be installed *unverified*.
This module closes that gap: known versions are pinned here, so a download
can be verified without the API, and a download whose hash cannot be
established at all is refused instead of trusted.

Provenance of the pinned values (ArgyllCMS 3.5.0): they equal the digests
published by the GitHub API for ``eoyilmaz/argyllcms-binaries`` release
``3.5.0`` and, for the macOS arm64, Windows x64 and Windows arm64 archives,
the SHA-256 of the files served by the official site
https://www.argyllcms.com/ (verified byte-identical on 2026-10-19). ArgyllCMS
is licensed under the AGPL-3.0; its licence text ships inside each archive.
"""

from __future__ import annotations

PINNED_SHA256: dict[str, dict[str, str]] = {
    "3.5.0": {
        "Argyll_V3.5.0_linux_x86_64_bin.tgz": "0d1da052de22396f4141c5ca3ee0c17a434bc142048a327dd86565a9f20d0c13",
        "Argyll_V3.5.0_linux_x86_bin.tgz": "b3ddd567a4e752645b7927f669c4c5171df8d0a9020a038fea35b505238afd83",
        "Argyll_V3.5.0_macOS11_arm64_bin.tgz": "b1f27d638ddca054db3f5ff866410d5b36f179770cee5591f116352b1853d957",
        "Argyll_V3.5.0_osx10.4_i86_bin.tgz": "32739ab21d9856fe5981970a28458a89ac85ae0739c6b48ddbd46753b3a0a0f4",
        "Argyll_V3.5.0_osx10.6_x86_64_bin.tgz": "69fcab29d555890434e90c91f7a2b86f0a21551f194dd816a8681d0f7e99a01d",
        "Argyll_V3.5.0_win32_exe.zip": "54848d3ffdaef7436e25c80ac3edd08db4d085586b709ed7293cbe1454941a31",
        "Argyll_V3.5.0_win64_exe.zip": "c80f78ba30e715079a00a14c2e7c9f533c58e6c8fdbc27f2d32b3d7813f9d132",
        "Argyll_V3.5.0_win_arm64_exe.zip": "e154c7e4db8e25ad1720280190edd344a16ce89c48ac8af52878221cce1ce787",
    }
}


class HashConflictError(ValueError):
    """The pinned hash and the hash reported by the server disagree."""


def resolve_expected_hash(
    version: str, filename: str, api_digest: str | None
) -> str | None:
    """Return the SHA-256 (hex, lower case) a download must match.

    Args:
        version: Release tag, e.g. ``"3.5.0"``.
        filename: Asset name.
        api_digest: Hash reported by the GitHub API (hex, without the
            ``sha256:`` prefix), or ``None`` when the lookup failed.

    Returns:
        The expected hash, or ``None`` when none can be established -- the
        caller must then refuse the download.

    Raises:
        HashConflictError: Both sources exist but differ (a re-uploaded or
            tampered asset); the download must be refused.
    """
    pinned = PINNED_SHA256.get(version, {}).get(filename)
    api = api_digest.lower() if api_digest else None
    if pinned and api and pinned != api:
        raise HashConflictError(filename)
    return pinned or api
