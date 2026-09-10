#!/usr/bin/env python3
"""Publish an APK/AAB to CafeBazaar through the Developer API v2.

The script performs the two steps CafeBazaar requires for a CI upload:

1. Exchange a long-lived OAuth refresh token for a short-lived access token.
2. Upload the built package file for the given application id.

Credentials are read from environment variables so that nothing sensitive is
ever passed on the command line (and therefore never shows up in process
listings or CI logs):

    CAFEBAZAAR_CLIENT_ID       OAuth client id      (required)
    CAFEBAZAAR_CLIENT_SECRET   OAuth client secret  (required)
    CAFEBAZAAR_REFRESH_TOKEN   OAuth refresh token  (required)

The endpoints can be overridden, which is primarily useful for testing the
script against a mock server:

    CAFEBAZAAR_TOKEN_URL        default: https://pardakht.cafebazaar.ir/devapi/v2/auth/token/
    CAFEBAZAAR_UPLOAD_URL_TMPL  default: https://pardakht.cafebazaar.ir/devapi/v2/api/upload/{package}/

How to obtain the credentials (one-time, done by the app owner):
  * Create an API client in the CafeBazaar developer panel
    (https://pardakht.cafebazaar.ir/panel/developer-api/) to get the
    client id and client secret.
  * Complete the OAuth "authorize" flow once with access_type=offline to
    receive a refresh token, then store the three values as GitHub secrets.
"""

from __future__ import annotations

import argparse
import os
import sys

import requests

TOKEN_URL = os.environ.get(
    "CAFEBAZAAR_TOKEN_URL",
    "https://pardakht.cafebazaar.ir/devapi/v2/auth/token/",
)
UPLOAD_URL_TMPL = os.environ.get(
    "CAFEBAZAAR_UPLOAD_URL_TMPL",
    "https://pardakht.cafebazaar.ir/devapi/v2/api/upload/{package}/",
)

TOKEN_TIMEOUT_SECONDS = 60
# Uploads can be large (the release APK is a few hundred MB), so allow a long
# window before giving up on the request.
UPLOAD_TIMEOUT_SECONDS = 30 * 60


def fail(message: str) -> "None":
    """Print a GitHub-Actions-formatted error and exit non-zero."""
    print(f"::error::{message}", file=sys.stderr)
    sys.exit(1)


def _short(text: str, limit: int = 800) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "…"


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
            timeout=TOKEN_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        fail(f"Could not reach CafeBazaar token endpoint: {exc}")

    if not response.ok:
        fail(
            "Failed to refresh CafeBazaar access token "
            f"(HTTP {response.status_code}): {_short(response.text)}"
        )

    try:
        payload = response.json()
    except ValueError:
        fail(f"Token endpoint returned non-JSON response: {_short(response.text)}")

    access_token = payload.get("access_token")
    if not access_token:
        fail(f"Token endpoint response did not contain an access_token: {payload}")

    print("Successfully obtained a CafeBazaar access token.")
    return access_token


def upload_package(package: str, file_path: str, access_token: str) -> dict:
    if not os.path.isfile(file_path):
        fail(f"Package file not found: {file_path}")

    url = UPLOAD_URL_TMPL.format(package=package)
    file_name = os.path.basename(file_path)
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    print(f"Uploading {file_name} ({size_mb:.1f} MB) to {url}")

    try:
        with open(file_path, "rb") as package_file:
            response = requests.post(
                url,
                data={"access_token": access_token},
                files={"file": (file_name, package_file, "application/octet-stream")},
                timeout=UPLOAD_TIMEOUT_SECONDS,
            )
    except requests.RequestException as exc:
        fail(f"Upload request to CafeBazaar failed: {exc}")

    if not response.ok:
        fail(
            f"CafeBazaar rejected the upload (HTTP {response.status_code}): "
            f"{_short(response.text)}"
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    print(f"CafeBazaar upload succeeded: {payload}")
    return payload


def parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload an APK/AAB to CafeBazaar via the Developer API v2.",
    )
    parser.add_argument(
        "--package",
        required=True,
        help="Application id to publish to, e.g. org.kiwix.kiwixmobile",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the .apk or .aab file to upload",
    )
    return parser.parse_args(argv)


def main(argv: "list[str] | None" = None) -> int:
    args = parse_args(argv)

    client_id = os.environ.get("CAFEBAZAAR_CLIENT_ID")
    client_secret = os.environ.get("CAFEBAZAAR_CLIENT_SECRET")
    refresh_token = os.environ.get("CAFEBAZAAR_REFRESH_TOKEN")

    missing = [
        name
        for name, value in (
            ("CAFEBAZAAR_CLIENT_ID", client_id),
            ("CAFEBAZAAR_CLIENT_SECRET", client_secret),
            ("CAFEBAZAAR_REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing:
        fail(
            "Missing required CafeBazaar credential(s): "
            + ", ".join(missing)
            + ". Add them as repository secrets."
        )

    access_token = get_access_token(client_id, client_secret, refresh_token)
    upload_package(args.package, args.file, access_token)
    print("Done. New version submitted to CafeBazaar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
