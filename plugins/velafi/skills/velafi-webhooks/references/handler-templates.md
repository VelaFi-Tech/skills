# Webhook handler templates

Minimal receivers derived from the verification code in https://docs.velafi.com/api-reference/webhooks/webhook-setup.md. Adapt names, storage and routing to the developer's codebase; keep the order of operations:

1. Read the **raw body bytes**.
2. Verify the hex `signature` header: RSA-SHA256 (`SHA256withRSA`, PKCS#1 v1.5) over the raw bytes, with the webhook `publicKey` (Base64 X.509 SubjectPublicKeyInfo).
3. Bad or missing signature: `{"callbackStatus":"FAIL"}`, nothing stored.
4. Store the event (unique on event type + record id + status). A duplicate is fine.
5. Return HTTP `200`, `Content-Type: application/json`, body exactly `{"callbackStatus":"SUCCESS"}`. If storage failed, return a non-2xx so VelaFi retries.
6. Process stored events in a background worker that reads the current record state from the API.

The public key comes from configuration per environment (for example `VELAFI_WEBHOOK_PUBLIC_KEY`), never from source. If you register several event types, each webhook has its own `publicKey`: either give each event type its own path and key, or try the keys configured for your webhooks.

## Shared pieces

Dedupe key per event type:

| `eventType` | Record id field | Status field |
|---|---|---|
| `ORDER_WEBHOOK` | `orderId` | `orderStatus` |
| `GLOBAL_PAYMENT_WEBHOOK` | `orderId` | `orderStatus` |
| `FUNDING_WEBHOOK` | `txId` | `status` |
| `ON_RAMP_WITHDRAW_WEBHOOK` | `orderId` | `status` (always `succeeded`) |
| `STABLE_COIN_PAYMENT_WEBHOOK` | `orderId` | `status` |
| `CRYPTO_WITHDRAW_WEBHOOK` | `withdrawId` | `status` |

Never include `timestamp` (new on every attempt) in the key.

Storage table (adjust types to your database):

```sql
CREATE TABLE velafi_webhook_events (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  event_type    VARCHAR(64)  NOT NULL,
  record_id     VARCHAR(64)  NOT NULL,
  status        VARCHAR(32)  NOT NULL,
  merchant_id   VARCHAR(32),
  raw_body      TEXT         NOT NULL,
  received_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processed_at  TIMESTAMP    NULL,
  UNIQUE (event_type, record_id, status)
);
```

The worker picks rows with `processed_at IS NULL`, re-reads the record from VelaFi (`GET /v2/order/detail`, `GET /v2/merchant/funding/records`, `GET /v2/assets/withdrawalOrders`), applies the change idempotently, then sets `processed_at`.

## Node.js / Express

The route must receive the raw body. Mount it with `express.raw()` and register it **before** any global `app.use(express.json())`, or the body is already parsed.

```javascript
const express = require("express");
const crypto = require("crypto");

const ACK = '{"callbackStatus":"SUCCESS"}';
const NACK = '{"callbackStatus":"FAIL"}';

const KEY_FIELDS = {
  ORDER_WEBHOOK: ["orderId", "orderStatus"],
  GLOBAL_PAYMENT_WEBHOOK: ["orderId", "orderStatus"],
  FUNDING_WEBHOOK: ["txId", "status"],
  ON_RAMP_WITHDRAW_WEBHOOK: ["orderId", "status"],
  STABLE_COIN_PAYMENT_WEBHOOK: ["orderId", "status"],
  CRYPTO_WITHDRAW_WEBHOOK: ["withdrawId", "status"],
};

// Base64 X.509 (SPKI DER) public key from POST /v2/webhook, per environment.
const publicKey = crypto.createPublicKey({
  key: Buffer.from(process.env.VELAFI_WEBHOOK_PUBLIC_KEY, "base64"),
  format: "der",
  type: "spki",
});

function verifySignature(rawBody, signatureHex) {
  if (typeof signatureHex !== "string" || !/^[0-9a-fA-F]+$/.test(signatureHex) || signatureHex.length % 2 !== 0) {
    return false;
  }
  try {
    return crypto.verify("sha256", rawBody, publicKey, Buffer.from(signatureHex, "hex"));
  } catch {
    return false;
  }
}

const app = express();

app.post("/webhooks/velafi", express.raw({ type: "*/*", limit: "1mb" }), async (req, res) => {
  const raw = req.body; // Buffer with the exact bytes VelaFi signed
  res.type("application/json");

  if (!Buffer.isBuffer(raw) || !verifySignature(raw, req.get("signature"))) {
    return res.status(200).send(NACK);
  }

  let event;
  try {
    event = JSON.parse(raw.toString("utf8"));
  } catch {
    return res.status(400).send(NACK);
  }
  const fields = KEY_FIELDS[event.eventType];
  if (!fields) {
    return res.status(200).send(ACK); // verified but unknown type: acknowledge, log, ignore
  }

  try {
    // INSERT ... ; treat a unique-constraint violation as "already stored".
    await storeEvent({
      eventType: event.eventType,
      recordId: String(event[fields[0]]),
      status: String(event[fields[1]] ?? ""),
      merchantId: event.merchantId ?? null,
      rawBody: raw.toString("utf8"),
    });
  } catch (err) {
    console.error("velafi webhook store failed", err.message); // no payload, no secrets
    return res.status(500).send(NACK); // VelaFi retries
  }

  return res.status(200).send(ACK); // processing happens in a worker
});

async function storeEvent(row) {
  // Replace with your database insert. Ignore duplicate-key errors.
}

app.listen(process.env.PORT || 3000);
```

## Python / Flask

```python
import base64
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from flask import Flask, Response, request

ACK = '{"callbackStatus":"SUCCESS"}'
NACK = '{"callbackStatus":"FAIL"}'
KEY_FIELDS = {
    "ORDER_WEBHOOK": ("orderId", "orderStatus"),
    "GLOBAL_PAYMENT_WEBHOOK": ("orderId", "orderStatus"),
    "FUNDING_WEBHOOK": ("txId", "status"),
    "ON_RAMP_WITHDRAW_WEBHOOK": ("orderId", "status"),
    "STABLE_COIN_PAYMENT_WEBHOOK": ("orderId", "status"),
    "CRYPTO_WITHDRAW_WEBHOOK": ("withdrawId", "status"),
}

PUBLIC_KEY = serialization.load_der_public_key(
    base64.b64decode(os.environ["VELAFI_WEBHOOK_PUBLIC_KEY"])
)

app = Flask(__name__)


def verify_signature(raw: bytes, signature_hex) -> bool:
    try:
        PUBLIC_KEY.verify(bytes.fromhex(signature_hex), raw, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:  # bad hex, missing header, wrong signature
        return False


def reply(body: str, status: int = 200) -> Response:
    return Response(body, status=status, mimetype="application/json")


@app.post("/webhooks/velafi")
def velafi_webhook():
    raw = request.get_data(cache=False)  # exact bytes; do not use request.json first
    if not verify_signature(raw, request.headers.get("signature")):
        return reply(NACK)

    try:
        event = json.loads(raw)
    except ValueError:
        return reply(NACK, 400)
    fields = KEY_FIELDS.get(event.get("eventType"))
    if fields is None:
        return reply(ACK)

    try:
        store_event(  # INSERT; ignore unique-constraint violations
            event_type=event["eventType"],
            record_id=str(event.get(fields[0])),
            status=str(event.get(fields[1], "")),
            merchant_id=event.get("merchantId"),
            raw_body=raw.decode("utf-8"),
        )
    except Exception:
        app.logger.exception("velafi webhook store failed")
        return reply(NACK, 500)

    return reply(ACK)


def store_event(**row):
    """Replace with your database insert."""
```

## Python / FastAPI

```python
import base64
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import FastAPI, Request, Response

ACK = '{"callbackStatus":"SUCCESS"}'
NACK = '{"callbackStatus":"FAIL"}'
KEY_FIELDS = {
    "ORDER_WEBHOOK": ("orderId", "orderStatus"),
    "GLOBAL_PAYMENT_WEBHOOK": ("orderId", "orderStatus"),
    "FUNDING_WEBHOOK": ("txId", "status"),
    "ON_RAMP_WITHDRAW_WEBHOOK": ("orderId", "status"),
    "STABLE_COIN_PAYMENT_WEBHOOK": ("orderId", "status"),
    "CRYPTO_WITHDRAW_WEBHOOK": ("withdrawId", "status"),
}
PUBLIC_KEY = serialization.load_der_public_key(
    base64.b64decode(os.environ["VELAFI_WEBHOOK_PUBLIC_KEY"])
)

app = FastAPI()


def verify_signature(raw: bytes, signature_hex) -> bool:
    try:
        PUBLIC_KEY.verify(bytes.fromhex(signature_hex), raw, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


@app.post("/webhooks/velafi")
async def velafi_webhook(request: Request) -> Response:
    raw = await request.body()  # do not declare a Pydantic body model for this route
    if not verify_signature(raw, request.headers.get("signature")):
        return Response(NACK, media_type="application/json")
    try:
        event = json.loads(raw)
    except ValueError:
        return Response(NACK, status_code=400, media_type="application/json")
    fields = KEY_FIELDS.get(event.get("eventType"))
    if fields is None:
        return Response(ACK, media_type="application/json")
    try:
        await store_event(  # INSERT; ignore unique-constraint violations
            event_type=event["eventType"],
            record_id=str(event.get(fields[0])),
            status=str(event.get(fields[1], "")),
            merchant_id=event.get("merchantId"),
            raw_body=raw.decode("utf-8"),
        )
    except Exception:
        return Response(NACK, status_code=500, media_type="application/json")
    return Response(ACK, media_type="application/json")


async def store_event(**row):
    """Replace with your database insert."""
```

## Java / Spring Boot (Java 11+)

`@RequestBody byte[]` keeps the exact bytes. Do not bind the body to a DTO on this route.

```java
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import java.util.Map;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class VelafiWebhookController {

    private static final String ACK = "{\"callbackStatus\":\"SUCCESS\"}";
    private static final String NACK = "{\"callbackStatus\":\"FAIL\"}";
    private static final Map<String, String[]> KEY_FIELDS = Map.of(
            "ORDER_WEBHOOK", new String[]{"orderId", "orderStatus"},
            "GLOBAL_PAYMENT_WEBHOOK", new String[]{"orderId", "orderStatus"},
            "FUNDING_WEBHOOK", new String[]{"txId", "status"},
            "ON_RAMP_WITHDRAW_WEBHOOK", new String[]{"orderId", "status"},
            "STABLE_COIN_PAYMENT_WEBHOOK", new String[]{"orderId", "status"},
            "CRYPTO_WITHDRAW_WEBHOOK", new String[]{"withdrawId", "status"});

    private final PublicKey publicKey;
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper = new ObjectMapper();

    public VelafiWebhookController(@Value("${velafi.webhook.public-key}") String publicKeyB64,
                                   JdbcTemplate jdbc) throws Exception {
        byte[] der = Base64.getDecoder().decode(publicKeyB64);
        this.publicKey = KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(der));
        this.jdbc = jdbc;
    }

    @PostMapping(value = "/webhooks/velafi", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> receive(@RequestBody byte[] raw,
                                          @RequestHeader(value = "signature", required = false) String signature) {
        if (!verify(raw, signature)) {
            return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(NACK);
        }
        JsonNode event;
        try {
            event = mapper.readTree(raw);
        } catch (Exception e) {
            return ResponseEntity.badRequest().contentType(MediaType.APPLICATION_JSON).body(NACK);
        }
        String eventType = event.path("eventType").asText();
        String[] fields = KEY_FIELDS.get(eventType);
        if (fields == null) {
            return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(ACK);
        }
        try {
            jdbc.update("INSERT INTO velafi_webhook_events (event_type, record_id, status, merchant_id, raw_body) "
                            + "VALUES (?, ?, ?, ?, ?)",
                    eventType, event.path(fields[0]).asText(), event.path(fields[1]).asText(),
                    event.path("merchantId").asText(null), new String(raw, StandardCharsets.UTF_8));
        } catch (DuplicateKeyException duplicate) {
            // Already stored: acknowledge again.
        } catch (Exception e) {
            return ResponseEntity.status(500).contentType(MediaType.APPLICATION_JSON).body(NACK);
        }
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(ACK);
    }

    private boolean verify(byte[] raw, String signatureHex) {
        if (signatureHex == null || signatureHex.length() % 2 != 0) {
            return false;
        }
        try {
            Signature sig = Signature.getInstance("SHA256withRSA");
            sig.initVerify(publicKey);
            sig.update(raw);
            return sig.verify(decodeHex(signatureHex));
        } catch (Exception e) {
            return false;
        }
    }

    private static byte[] decodeHex(String hex) {
        byte[] out = new byte[hex.length() / 2];
        for (int i = 0; i < out.length; i++) {
            int hi = Character.digit(hex.charAt(2 * i), 16);
            int lo = Character.digit(hex.charAt(2 * i + 1), 16);
            if (hi < 0 || lo < 0) {
                throw new IllegalArgumentException("signature is not hex");
            }
            out[i] = (byte) ((hi << 4) | lo);
        }
        return out;
    }
}
```

Configure `velafi.webhook.public-key` from an environment variable or secrets manager, not in a committed `application.yml`.

## Self-test

Run `scripts/check_webhook_endpoint.py` against the running handler. It prints a throwaway public key; set it temporarily as `VELAFI_WEBHOOK_PUBLIC_KEY` (or the Spring property) in the dev environment, restart, and let the script send signed samples.
