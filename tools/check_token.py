#!/usr/bin/env python3
"""Check that VelaFi API credentials can get a business token.

Reads VELAFI_API_KEY and VELAFI_API_SECRET from the environment, signs
`timestamp=<ms>` with HMAC-SHA256 (lowercase hex) exactly as documented in
https://docs.velafi.com/api-reference/generate-token.md, and calls
GET /v2/token/generate.

Python 3 standard library only. The API secret and the full token are never
printed.
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SANDBOX_URL = "https://api-test.velafi.com"
SANDBOX_HOST = "api-test.velafi.com"
PRODUCTION_HOST = "api.velafi.com"

# Meanings from api-reference/generate-token.mdx, api-reference/authentication.mdx
# and docs/error-codes.mdx.
ERROR_MEANINGS = {
    -1002: "The X-BH-APIKEY header is missing or is not a valid API key format.",
    -1004: "The signature query parameter is missing, or timestamp is missing "
           "while other query parameters are sent. The msg names the missing parameter.",
    -1103: "The request has no query parameters, or signature is the only one.",
    -1022: "The signature does not match, or the API key does not exist. Check that the "
           "key and secret belong to the environment you are calling (sandbox keys only "
           "work on https://api-test.velafi.com, production keys only on "
           "https://api.velafi.com) and that the secret has no extra spaces or newlines.",
    -1023: "The API key has no IP whitelist. Add the public IP address of this server on "
           "the API Management page (Whitelist): up to 5 IPv4/IPv6 addresses per key, "
           "no CIDR ranges.",
    -2015: "The API key or your account is disabled, or the request IP address is not on "
           "the key's whitelist. Check the key's whitelist contains this server's public "
           "egress IP.",
    -5033: "API access is not enabled on your account. Contact VelaFi.",
    -1000: "The credentials could not be verified for another reason.",
    -1001: "Internal error. Try again later.",
    -1006: "Execution status unknown (backend error or rate limit). Back off and retry.",
    -1007: "Timeout waiting for response from backend server. Retry.",
    30012: "Network busy (too many concurrent requests). Back off and retry.",
}


def mask(value, keep=6):
    if not value:
        return "(empty)"
    return value[:keep] + "…"


def build_parser():
    p = argparse.ArgumentParser(
        description=(
            "Check VelaFi API credentials by calling GET /v2/token/generate. "
            "Reads VELAFI_API_KEY and VELAFI_API_SECRET from the environment and the "
            "base URL from VELAFI_BASE_URL (default %s). Refuses the production URL "
            "(https://api.velafi.com) unless --production is passed. Never prints the "
            "secret or the full token." % SANDBOX_URL
        ),
        epilog=(
            "Example: VELAFI_API_KEY=... VELAFI_API_SECRET=... python3 check_token.py\n"
            "Exit code 0 = token received, 1 = API returned an error, 2 = usage/config error, "
            "3 = network error."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--base-url",
        help="Override VELAFI_BASE_URL (default %s)." % SANDBOX_URL,
    )
    p.add_argument(
        "--production",
        action="store_true",
        help="Allow calling https://api.velafi.com. Only use with the developer's "
             "explicit approval and production credentials.",
    )
    p.add_argument(
        "--timeout", type=float, default=15.0, help="HTTP timeout in seconds (default 15)."
    )
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    api_key = os.environ.get("VELAFI_API_KEY", "")
    api_secret = os.environ.get("VELAFI_API_SECRET", "")
    base_url = (args.base_url or os.environ.get("VELAFI_BASE_URL") or SANDBOX_URL).rstrip("/")

    missing = [n for n, v in (("VELAFI_API_KEY", api_key), ("VELAFI_API_SECRET", api_secret)) if not v]
    if missing:
        print("ERROR: missing environment variable(s): %s" % ", ".join(missing), file=sys.stderr)
        return 2

    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        print("ERROR: base URL must be an https:// URL, got %r" % base_url, file=sys.stderr)
        return 2
    host = parsed.hostname.lower().rstrip(".")
    if host != SANDBOX_HOST and not args.production:
        print(
            "REFUSED: %s is not the sandbox (%s). Any other host may be production. Re-run "
            "with --production only if the developer explicitly approved a production check."
            % (base_url, SANDBOX_HOST),
            file=sys.stderr,
        )
        return 2
    if host not in (PRODUCTION_HOST, SANDBOX_HOST):
        print("WARNING: %s is not a documented VelaFi base URL." % base_url, file=sys.stderr)

    for name, value in (("VELAFI_API_KEY", api_key), ("VELAFI_API_SECRET", api_secret)):
        if value != value.strip():
            print("WARNING: %s has leading/trailing whitespace; it is used as-is." % name,
                  file=sys.stderr)

    timestamp = str(int(time.time() * 1000))
    message = "timestamp=%s" % timestamp
    signature = hmac.new(api_secret.encode("utf-8"), message.encode("utf-8"),
                         hashlib.sha256).hexdigest()
    # Only timestamp and signature, in this order: the server verifies the signature
    # against the query string without the signature parameter.
    url = "%s/v2/token/generate?timestamp=%s&signature=%s" % (base_url, timestamp, signature)

    env_label = "PRODUCTION" if host == PRODUCTION_HOST else "sandbox"
    print("Calling GET %s/v2/token/generate (%s)" % (base_url, env_label))

    req = urllib.request.Request(url, method="GET", headers={
        "X-BH-APIKEY": api_key,
        "Accept": "application/json",
        "User-Agent": "velafi-skills-check-token/1.0",
    })
    status = None
    raw = b""
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read() or b""
    except (urllib.error.URLError, OSError) as e:
        print("NETWORK ERROR: could not reach %s: %s" % (base_url, e), file=sys.stderr)
        return 3

    try:
        body = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        print("FAILED: HTTP %s with a non-JSON body (%d bytes)." % (status, len(raw)))
        if status in (404, 405):
            print("The path or method was not accepted; check the base URL.")
        return 1

    code = body.get("code") if isinstance(body, dict) else None
    msg = body.get("msg") if isinstance(body, dict) else None
    data = body.get("data") if isinstance(body, dict) else None

    if status == 200 and code in (200, 0) and isinstance(data, dict) and data.get("token"):
        token = str(data.get("token"))
        expire_raw = data.get("expireTime")
        print("OK: token received.")
        print("  token:      %s" % mask(token))
        print("  expireTime: %s" % expire_raw)
        try:
            expire_ms = int(expire_raw)
            when = datetime.fromtimestamp(expire_ms / 1000.0, tz=timezone.utc)
            remaining = (expire_ms - int(time.time() * 1000)) / 60000.0
            print("              = %s UTC (in %.1f minutes)" % (when.strftime("%Y-%m-%d %H:%M:%S"), remaining))
        except (TypeError, ValueError):
            pass
        print("Send the token in the X-BH-TOKEN header and request a new one before expireTime.")
        return 0

    print("FAILED: HTTP %s, code=%s, msg=%s" % (status, code, msg))
    try:
        meaning = ERROR_MEANINGS.get(int(code))
    except (TypeError, ValueError):
        meaning = None
    if meaning:
        print("Meaning: %s" % meaning)
    else:
        print("Meaning: not a documented token error. See https://docs.velafi.com/docs/error-codes.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())
