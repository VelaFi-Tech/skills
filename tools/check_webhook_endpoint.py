#!/usr/bin/env python3
"""Local self-test for a VelaFi webhook endpoint.

Signs sample VelaFi webhook payloads with a throwaway RSA-2048 key and POSTs
them to the developer's local endpoint, then checks:

  (a) HTTP 2xx and a body that is exactly {"callbackStatus":"SUCCESS"}
  (b) re-sending the same event returns SUCCESS again (idempotent)
  (c) a tampered or missing signature does NOT return SUCCESS
  (d) the response time is well under VelaFi's 60-second timeout

Requires the `cryptography` package (pip install cryptography). Never
contacts VelaFi. Only localhost / 127.0.0.1 / ::1 are allowed unless
--allow-remote is passed.
"""

import argparse
import base64
import http.client
import json
import os
import random
import socket
import ssl
import sys
import time
import urllib.parse

hashes = serialization = padding = rsa = None


def require_cryptography():
    """Import `cryptography` lazily so --help works without it."""
    global hashes, serialization, padding, rsa
    try:
        from cryptography.hazmat.primitives import hashes as _h, serialization as _s
        from cryptography.hazmat.primitives.asymmetric import padding as _p, rsa as _r
    except ImportError:
        sys.stderr.write(
            "This script needs the 'cryptography' package:\n"
            "  python3 -m pip install cryptography\n"
            "(use a virtualenv if your system Python is managed).\n"
        )
        sys.exit(2)
    hashes, serialization, padding, rsa = _h, _s, _p, _r

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
EXPECTED = {"callbackStatus": "SUCCESS"}
SLOW_WARN_S = 5.0
SLOW_FAIL_S = 30.0


# --------------------------------------------------------------------------- keys

def load_or_create_key(path):
    """Return (private_key, created). With no path, always creates an ephemeral key."""
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None), False
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    if path:
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
    return key, True


def public_key_b64(key):
    """Base64 X.509 SubjectPublicKeyInfo (DER): the same format as VelaFi's publicKey."""
    der = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return base64.b64encode(der).decode("ascii")


def sign_hex(key, raw_body):
    sig = key.sign(raw_body, padding.PKCS1v15(), hashes.SHA256())
    return sig.hex()


# ----------------------------------------------------------------------- payloads

def rand_id(n=18):
    return str(random.randint(1, 9)) + "".join(str(random.randint(0, 9)) for _ in range(n - 1))


def now_ms():
    return str(int(time.time() * 1000))


def build_events():
    """Sample events based on the documented example payloads, with placeholder data.

    Each entry: (label, dict payload, serializer). Different JSON formatting is used on
    purpose: a handler that verifies a re-serialized body instead of the raw bytes fails.
    """
    webhook_id = "00000000000000000000000000000000"
    t = int(time.time() * 1000)
    funding = {
        "webhookId": webhook_id,
        "eventType": "FUNDING_WEBHOOK",
        "txId": rand_id(),
        "clientId": "selftest-" + rand_id(8),
        "userId": "100000",
        "merchantId": "100001",
        "merchantName": "Example Merchant",
        "fiat": "ARS",
        "totalAmount": "22",
        "amount": "20",
        "fee": "2",
        "refundedAmount": "0",
        "paymentId": "63",
        "userPaymentId": "91",
        "type": "DEPOSIT",
        "status": "2",
        "completedTime": str(t - 1000),
        "createTime": str(t - 60000),
        "updateTime": str(t - 1000),
        "cardNo": "0000000001",
        "taxId": "20000000001",
        "payerName": "José Pérez",
        "payerAccount": "0000000000000000000005",
        "depositAlias": "alias",
        "bankWebhookInfo": "{}",
    }
    order = {
        "webhookId": webhook_id,
        "eventType": "ORDER_WEBHOOK",
        "orderId": rand_id(),
        "clientId": "selftest-" + rand_id(8),
        "userId": "100000",
        "merchantId": "100001",
        "settingsId": "12",
        "orderType": "SELL",
        "fiat": "MXN",
        "fiatAmount": "99",
        "arriveFiatAmount": "99",
        "fiatFee": "0",
        "crypto": "USDT",
        "cryptoAmount": "5",
        "orderPrice": "19.8158",
        "orderStatus": "60",
        "createTime": str(t - 600000),
        "updateTime": str(t - 1000),
        "fiatCurrency": "MXN",
        "orderAmount": "99",
        "arriveOrderAmount": "99",
        "mcSettingsId": "12",
        "cryptoCurrency": "USDT",
        "quantity": "5",
    }
    withdraw = {
        "webhookId": webhook_id,
        "eventType": "CRYPTO_WITHDRAW_WEBHOOK",
        "withdrawId": rand_id(),
        "clientId": "selftest-" + rand_id(8),
        "userId": "100000",
        "merchantId": "100001",
        "crypto": "USDT",
        "network": "TRC20",
        "address": "YOUR_DESTINATION_ADDRESS",
        "amount": "100",
        "fee": "1",
        "netAmount": "99",
        "status": "SUCCESS",
        "statusCode": "6",
        "txHash": "4a7f0c3e2b1d9f8e7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f",
        "createTime": str(t - 200000),
        "completeTime": str(t - 1000),
    }

    def compact(d):
        return json.dumps(d, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def spaced(d):
        return json.dumps(d, ensure_ascii=False).encode("utf-8")

    return [
        ("FUNDING_WEBHOOK (DEPOSIT, status 2)", funding, spaced),
        ("ORDER_WEBHOOK (SELL, orderStatus 60)", order, compact),
        ("CRYPTO_WITHDRAW_WEBHOOK (SUCCESS)", withdraw, compact),
    ]


def body_for_attempt(payload, serializer):
    # Every delivery attempt carries a fresh `timestamp` and a fresh signature.
    p = dict(payload)
    p["timestamp"] = now_ms()
    return serializer(p)


# ------------------------------------------------------------------------- HTTP

class Endpoint(object):
    def __init__(self, url, timeout, insecure):
        u = urllib.parse.urlparse(url)
        self.scheme = u.scheme
        self.host = u.hostname
        self.port = u.port
        self.path = (u.path or "/") + (("?" + u.query) if u.query else "")
        self.timeout = timeout
        self.insecure = insecure

    def post(self, raw_body, signature):
        if self.scheme == "https":
            ctx = ssl._create_unverified_context() if self.insecure else ssl.create_default_context()
            conn = http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout, context=ctx)
        else:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        headers = {"Content-Type": "application/json", "User-Agent": "velafi-webhook-selftest/1.0"}
        if signature is not None:
            headers["signature"] = signature
        start = time.monotonic()
        try:
            conn.request("POST", self.path, body=raw_body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, data, time.monotonic() - start, None
        except Exception as e:  # timeout, refused, reset
            return None, b"", time.monotonic() - start, e
        finally:
            conn.close()


# ----------------------------------------------------------------------- checks

def diagnose_ack(status, raw):
    """Return (ok, reason)."""
    if status is None:
        return False, "no HTTP response"
    if not (200 <= status < 300):
        return False, "HTTP %d is not 2xx; VelaFi counts any non-2xx as a failed attempt" % status
    if not raw:
        return False, "empty body; VelaFi needs the JSON body {\"callbackStatus\":\"SUCCESS\"}"
    if raw.startswith(b"\xef\xbb\xbf"):
        return False, "body starts with a UTF-8 byte-order mark before '{'"
    if raw[:1] != b"{":
        stripped = raw.strip()
        if stripped[:1] == b"{":
            return False, "whitespace before the opening '{' (counts as a failure)"
        text = stripped.decode("utf-8", "replace")
        if text.upper() in ("SUCCESS", "OK", "\"SUCCESS\""):
            return False, ("plain-text %r is not accepted; return the JSON object "
                           "{\"callbackStatus\":\"SUCCESS\"} with Content-Type application/json" % text)
        return False, "body is not a JSON object: %r" % text[:80]
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False, "body is not valid JSON: %r" % raw[:80]
    if not isinstance(obj, dict):
        return False, "body is JSON but not an object"
    val = obj.get("callbackStatus")
    if val is None:
        return False, ("JSON has no callbackStatus (%s); bodies like {\"received\":true} or "
                       "{\"status\":\"ok\"} count as failures" % json.dumps(obj)[:80])
    if val != "SUCCESS":
        if isinstance(val, str) and val.upper() == "SUCCESS":
            return False, "callbackStatus is %r; the value is case-sensitive and must be \"SUCCESS\"" % val
        return False, "callbackStatus is %r, not \"SUCCESS\"" % (val,)
    if obj != EXPECTED:
        return True, "accepted, but the body has extra keys; return exactly {\"callbackStatus\":\"SUCCESS\"}"
    return True, "exactly {\"callbackStatus\":\"SUCCESS\"}"


def is_success_ack(status, raw):
    ok, _ = diagnose_ack(status, raw)
    return ok


def tamper(sig_hex):
    i = len(sig_hex) // 2
    c = sig_hex[i]
    return sig_hex[:i] + ("0" if c != "0" else "1") + sig_hex[i + 1:]


class Report(object):
    def __init__(self):
        self.fails = 0
        self.warns = 0

    def line(self, level, msg):
        if level == "FAIL":
            self.fails += 1
        elif level == "WARN":
            self.warns += 1
        print("  [%s] %s" % (level, msg))


def is_timeout(err):
    return err is not None and (isinstance(err, (socket.timeout, TimeoutError)) or "timed out" in str(err))


def timing(report, label, elapsed, err):
    if is_timeout(err):
        report.line("FAIL", "%s: no response within the timeout (VelaFi waits 60 s, then counts a failed attempt)" % label)
        return
    if elapsed >= SLOW_FAIL_S:
        report.line("FAIL", "%s: %.2f s is too close to VelaFi's 60 s timeout; acknowledge first, process async" % (label, elapsed))
    elif elapsed >= SLOW_WARN_S:
        report.line("WARN", "%s: %.2f s; move slow work out of the request path" % (label, elapsed))
    else:
        report.line("PASS", "%s: responded in %.3f s" % (label, elapsed))


def run(endpoint, key, report):
    for label, payload, serializer in build_events():
        print("\n== %s" % label)

        # (a) correct signature
        raw = body_for_attempt(payload, serializer)
        status, data, elapsed, err = endpoint.post(raw, sign_hex(key, raw))
        if err is not None and status is None and not is_timeout(err):
            report.line("FAIL", "request failed: %s (is the server running at that URL?)" % err)
            continue
        ok, why = diagnose_ack(status, data)
        report.line("PASS" if ok and "extra keys" not in why else ("WARN" if ok else "FAIL"),
                    "(a) valid signature -> HTTP %s, %s" % (status, why))
        if not ok and status is not None and 200 <= status < 300:
            text = data.decode("utf-8", "replace")
            if "FAIL" in text:
                print("       Your handler rejected a correctly signed body. Check that it verifies the raw "
                      "request bytes (not re-serialized JSON), uses the public key printed above, "
                      "hex-decodes the signature header, and uses SHA256withRSA / PKCS#1 v1.5.")
        timing(report, "(d) response time", elapsed, err)

        # (b) duplicate delivery (new timestamp + signature, same event)
        raw2 = body_for_attempt(payload, serializer)
        status2, data2, elapsed2, err2 = endpoint.post(raw2, sign_hex(key, raw2))
        ok2, why2 = diagnose_ack(status2, data2)
        report.line("PASS" if ok2 else "FAIL",
                    "(b) duplicate delivery -> HTTP %s, %s%s" % (
                        status2, why2,
                        "" if ok2 else "; a duplicate must still be acknowledged (dedupe, then return SUCCESS)"))

        # (c) tampered signature
        raw3 = body_for_attempt(payload, serializer)
        status3, data3, _, _ = endpoint.post(raw3, tamper(sign_hex(key, raw3)))
        if is_success_ack(status3, data3):
            report.line("FAIL", "(c) tampered signature was acknowledged with SUCCESS: the handler is not verifying signatures")
        elif not ok and (status3, data3) == (status, data):
            report.line("WARN", "(c) inconclusive: the tampered request got the same response as the valid one "
                                "(HTTP %s, body %r), so signature verification cannot be confirmed" % (status3, data3[:60]))
        else:
            report.line("PASS", "(c) tampered signature rejected (HTTP %s, body %r)" % (status3, data3[:60]))

        # (c') missing signature header
        raw4 = body_for_attempt(payload, serializer)
        status4, data4, _, _ = endpoint.post(raw4, None)
        if is_success_ack(status4, data4):
            report.line("FAIL", "(c) request without a signature header was acknowledged with SUCCESS")
        elif not ok and (status4, data4) == (status, data):
            report.line("WARN", "(c) inconclusive: the unsigned request got the same response as the valid one")
        else:
            report.line("PASS", "(c) missing signature rejected (HTTP %s)" % status4)


# ------------------------------------------------------------------------- main

def build_parser():
    p = argparse.ArgumentParser(
        description=(
            "Self-test a local VelaFi webhook endpoint. Generates an RSA-2048 key pair "
            "(requires the 'cryptography' package: pip install cryptography), prints the "
            "Base64 X.509 public key for you to configure TEMPORARILY as the webhook "
            "verification key in your dev environment, then POSTs signed sample "
            "FUNDING_WEBHOOK (DEPOSIT), ORDER_WEBHOOK and CRYPTO_WITHDRAW_WEBHOOK payloads "
            "with a hex RSA-SHA256 'signature' header. Checks: 2xx + exactly "
            "{\"callbackStatus\":\"SUCCESS\"}; duplicates acknowledged; tampered/missing "
            "signatures NOT acknowledged; response time well under 60 s. Never contacts VelaFi."
        ),
        epilog=(
            "Examples:\n"
            "  python3 check_webhook_endpoint.py http://localhost:3000/webhooks/velafi\n"
            "  python3 check_webhook_endpoint.py http://127.0.0.1:8080/velafi \\\n"
            "      --key-file .velafi-selftest-key.pem --public-key-out .velafi-selftest-pub.txt\n"
            "Exit code 0 = all checks passed, 1 = a check failed, 2 = usage error."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("url", help="Your webhook endpoint, e.g. http://localhost:3000/webhooks/velafi")
    p.add_argument("--allow-remote", action="store_true",
                   help="Allow a non-local host (e.g. a dev tunnel or staging box you own).")
    p.add_argument("--key-file",
                   help="PEM file for the test private key. Created if missing, reused if present, "
                        "so you only configure the public key once. Do not commit it.")
    p.add_argument("--public-key-out", help="Also write the Base64 public key to this file.")
    p.add_argument("--no-prompt", action="store_true",
                   help="Do not wait for Enter after printing the public key.")
    p.add_argument("--timeout", type=float, default=60.0,
                   help="Per-request timeout in seconds (default 60, VelaFi's own timeout).")
    p.add_argument("--insecure", action="store_true",
                   help="Skip TLS certificate checks for a local https:// endpoint.")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    u = urllib.parse.urlparse(args.url)
    if u.scheme not in ("http", "https") or not u.hostname:
        print("ERROR: URL must be http:// or https:// with a host: %r" % args.url, file=sys.stderr)
        return 2
    host = u.hostname.lower()
    if host == "velafi.com" or host.endswith(".velafi.com"):
        print("REFUSED: this script never sends requests to VelaFi hosts.", file=sys.stderr)
        return 2
    if host not in LOCAL_HOSTS and not args.allow_remote:
        print("REFUSED: %s is not localhost/127.0.0.1/::1. Pass --allow-remote only for an "
              "endpoint you own and run in a dev environment." % host, file=sys.stderr)
        return 2

    require_cryptography()
    key, created = load_or_create_key(args.key_file)
    pub = public_key_b64(key)
    if args.public_key_out:
        with open(args.public_key_out, "w") as f:
            f.write(pub + "\n")

    print("Test public key (Base64 X.509, same format as VelaFi's webhook publicKey):\n")
    print(pub)
    print("\nConfigure it TEMPORARILY as the webhook verification key in your DEV environment "
          "(for example the env var your handler reads), restart the handler if needed, and "
          "switch back to the real publicKey from POST /v2/webhook or GET /v2/webhooks afterwards. "
          "Never use this key in production.")
    if created and not args.no_prompt:
        try:
            input("\nPress Enter when the endpoint uses this key... ")
        except EOFError:
            pass

    print("\nTarget: POST %s" % args.url)
    report = Report()
    run(Endpoint(args.url, args.timeout, args.insecure), key, report)

    print("\nResult: %d failure(s), %d warning(s)." % (report.fails, report.warns))
    if report.fails:
        print("Fix the failures above. Docs: https://docs.velafi.com/api-reference/webhooks/webhook-setup.md")
        return 1
    print("All checks passed. Remember: webhooks do not fire in the VelaFi sandbox; "
          "verify end-to-end in production with low-value transactions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
