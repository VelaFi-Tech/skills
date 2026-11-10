---
name: velafi-webhooks
description: Build and test a VelaFi webhook receiver - register webhooks per event type (POST /v2/webhook), verify the RSA-SHA256 hex `signature` header over the raw body with the webhook publicKey, acknowledge with exactly {"callbackStatus":"SUCCESS"}, store-then-process asynchronously, dedupe on event type + record id + status, handle duplicates, out-of-order and skipped statuses, and reconcile after the 3 delivery attempts. Covers ORDER_WEBHOOK, GLOBAL_PAYMENT_WEBHOOK, FUNDING_WEBHOOK, ON_RAMP_WITHDRAW_WEBHOOK, STABLE_COIN_PAYMENT_WEBHOOK and CRYPTO_WITHDRAW_WEBHOOK. Use when adding a VelaFi webhook endpoint, when VelaFi keeps retrying or events go missing, or to self-test a local handler.
license: Apache-2.0
---

# VelaFi webhooks

## Overview

VelaFi pushes status changes to your server as signed HTTP POSTs. This skill builds one receiver that verifies every delivery, acknowledges it in the exact format VelaFi expects, stores it, and processes it asynchronously and idempotently. It also ships a local self-test, `scripts/check_webhook_endpoint.py`.

Related skills:

- `velafi-api-setup` — token and HTTP client (needed to register webhooks and to query records when reconciling). Build it first.
- The flow skills decide which events matter and what to do with each status: `velafi-onboard-merchants`, `velafi-collect-virtual-accounts`, `velafi-payouts-from-balance`, `velafi-onramp`, `velafi-offramp-payouts`, `velafi-global-payments`, `velafi-crypto-wallet`.
- `velafi-go-live-check` — runs this skill's self-test as part of the production review.

**Webhooks are not sent in the sandbox.** In the sandbox, poll the query endpoints instead, and test the handler locally with the self-test script. Production is the first place real deliveries arrive.

## Before you start

Ask the developer:

1. Which flows they run, to pick event types (table below).
2. Language/framework, and how the framework exposes the **raw request body** (many JSON middlewares discard it).
3. Where events are stored (database table, queue) and what runs the async processing.
4. The public HTTPS URL VelaFi will call, per environment.

## Event types

Register one webhook per event type. A create is rejected while an active webhook already exists for that type. Webhooks belong to the account, so each one receives events for every merchant under it: route by `merchantId` where present.

| Event | Sent when | Dedupe key | Page |
|---|---|---|---|
| `ORDER_WEBHOOK` | API-created on/off-ramp order enters `10, 11, 12, 31, 32, 40, 50, 60, 70, 72`. Rejections and timeouts are sent as `70` (polling shows `80`/`81`). | `orderId` + `orderStatus` | https://docs.velafi.com/api-reference/webhooks/fiat-crypto-order-message-push.md |
| `GLOBAL_PAYMENT_WEBHOOK` | API-created fiat-to-fiat order enters `10, 31, 41, 51, 60, 71, 72` | `orderId` + `orderStatus` | https://docs.velafi.com/api-reference/webhooks/fiat-fiat-order-message-push.md |
| `FUNDING_WEBHOOK` | Funding record `DEPOSIT`, `WITHDRAW` or `BUY_CRYPTO` reaches `2` completed, `3` canceled, `4` refunded. Not sent for pending records or merchant-to-merchant transfers. | `txId` + `status` | https://docs.velafi.com/api-reference/webhooks/funding-records-message-push.md |
| `ON_RAMP_WITHDRAW_WEBHOOK` | Automatic withdrawal of a completed API on-ramp order to its destination address succeeded (`status` always `succeeded`) | `orderId` | https://docs.velafi.com/api-reference/webhooks/on-ramp-withdraw-message-push.md |
| `STABLE_COIN_PAYMENT_WEBHOOK` | A stablecoin payment order is confirmed (only event; `status` normally `CONFIRMED`) | `orderId` + `status` | https://docs.velafi.com/api-reference/webhooks/stablecoin-payment-order-message-push.md |
| `CRYPTO_WITHDRAW_WEBHOOK` | A merchant-wallet crypto withdrawal reaches a final status `SUCCESS`, `FAILED`, `REFUNDED`, `CANCELLED` (API, dashboard, mass payout, automatic on-ramp withdrawals) | `withdrawId` + `status` | https://docs.velafi.com/api-reference/webhooks/crypto-withdraw-message-push.md |

Read `references/events.md` for per-event fields and handling notes.

## Workflow

### 1. Build the endpoint

Read `references/handler-templates.md` for Node/Express, Python (Flask, FastAPI) and Java/Spring templates. Each one does, in order:

1. **Read the raw body bytes** before any JSON parsing.
2. **Verify** the `signature` header: hex-decode it, verify RSA-SHA256 (`SHA256withRSA`, PKCS#1 v1.5) over the exact raw bytes with the webhook's `publicKey` (Base64 X.509 / SubjectPublicKeyInfo DER). Never verify re-serialized JSON.
3. Invalid or missing signature: return `{"callbackStatus":"FAIL"}`; do not process.
4. **Store** the raw event with a unique constraint on the dedupe key (event type + record id + status). A duplicate insert is not an error.
5. **Acknowledge**: HTTP `200`, `Content-Type: application/json`, body exactly `{"callbackStatus":"SUCCESS"}`. If storing failed, return a non-2xx so VelaFi retries.
6. **Process asynchronously** (worker, queue, job): read the record's current state from the API and update your system.

The acknowledgement is strict. Each of these counts as a failed delivery and triggers retries and duplicates: plain `SUCCESS`/`success`/`OK`, `{"callbackStatus":"success"}`, `{"received":true}`, `{"status":"ok"}`, an empty body, whitespace or a BOM before `{`, your own error JSON, any non-2xx status, or no response within 60 seconds.

Docs: https://docs.velafi.com/api-reference/webhooks/webhook-setup.md, https://docs.velafi.com/docs/guides/webhooks.md

### 2. Process events safely

- **Treat a webhook as a signal.** Deliveries can arrive out of order, and for order, global payment, funding and on-ramp withdrawal events VelaFi discards a queued event if the record's status changed before the attempt, so intermediate statuses can be skipped. Before acting, read the current state: `GET /v2/order/detail` (orders), `GET /v2/merchant/funding/records` (funding), `GET /v2/assets/withdrawalOrders` (crypto withdrawals).
- **Never move a record backwards.** Ignore an event whose status is older than what you already hold, except documented transitions such as ramp `60` → `72` (refund after completion).
- **Every payload value is a JSON string**, including IDs, amounts and timestamps. Parse amounts as decimals, not floats. The `timestamp` field changes on every attempt, so never include it in the dedupe key.
- Ignore unknown fields; payloads gain fields over time.

### 3. Register the webhooks — `POST /v2/webhook`

With the token from `velafi-api-setup`:

```json
POST /v2/webhook
{"eventType": "FUNDING_WEBHOOK", "url": "https://yourapp.example/webhooks/velafi"}
```

Store `data.webhookId` and `data.publicKey` per event type (secrets manager or config, per environment). Lost keys: `GET /v2/webhooks` returns them. Change the URL or enable/disable with `PUT /v2/webhook/{webhookId}` (`url`, `status` `10`/`20`); `DELETE /v2/webhook/{webhookId}` is permanent. Webhook statuses: `10` active, `20` disabled, `30` deleted.

- Register before the first live transaction: events that occur while no webhook is active for their type are never delivered.
- For `CRYPTO_WITHDRAW_WEBHOOK`, change URLs with `PUT` rather than delete-and-recreate: queued events go only to the webhook they were queued for.
- Registering, updating or deleting production webhooks changes live configuration: get the developer's explicit confirmation first.

Docs: https://docs.velafi.com/api-reference/webhooks/create-webhook-endpoints.md, https://docs.velafi.com/api-reference/webhooks/get-webhook-endpoints.md, https://docs.velafi.com/api-reference/webhooks/update-a-webhook.md, https://docs.velafi.com/api-reference/webhooks/delete-a-webhook.md

### 4. Reconcile what webhooks miss

A failed delivery is attempted 3 times in total (second about 5–10 minutes after the first failure, third about 60–65 minutes after the second), then dropped. There is no redelivery endpoint. Run a scheduled job that re-checks every record you hold in a non-final state against the query endpoints, and alerts on records stuck longer than expected. See https://docs.velafi.com/docs/use-cases/go-live-checklist#reconciliation.

## Rules

- Verify the signature on every delivery, over the raw body bytes, before parsing or acting. Never skip it "for now".
- Return exactly `{"callbackStatus":"SUCCESS"}` with HTTP 2xx for every verified delivery you stored, including duplicates.
- Respond fast: verify, store, acknowledge; do slow work asynchronously.
- Dedupe on event type + record id + status. Never on `timestamp`.
- Never treat a webhook as the ledger or assume you receive every status; confirm the current state through the API before moving money or marking success.
- Never claim an operation succeeded before a final status confirms it.
- Keep `publicKey`, API key, secret and tokens out of source, logs and commits. Store them per environment.
- Do not log full payloads in plain text if they contain payer names or account numbers (`FUNDING_WEBHOOK` deposits do).
- Default to the sandbox and local testing; get explicit confirmation before touching production webhooks.

## Verify

1. Run the local self-test against the developer's running handler (needs `pip install cryptography`):

   ```bash
   python3 scripts/check_webhook_endpoint.py http://localhost:3000/webhooks/velafi \
     --key-file .velafi-selftest-key.pem --public-key-out .velafi-selftest-pub.txt
   ```

   It prints a throwaway public key. Configure it **temporarily** as the verification key in the dev environment, then let the script continue. It POSTs signed `FUNDING_WEBHOOK` (DEPOSIT), `ORDER_WEBHOOK` and `CRYPTO_WITHDRAW_WEBHOOK` samples and checks: 2xx + exact acknowledgement, duplicates still acknowledged, tampered or missing signatures not acknowledged, response time well under 60 s. It only targets localhost unless `--allow-remote`, never contacts VelaFi, and exits non-zero on failure. Add the key files to `.gitignore` and restore the real `publicKey` afterwards.
2. Unit-test the verifier with a known key pair and a body containing non-ASCII characters.
3. In the sandbox, exercise flows by polling, since no webhooks fire. Deposit simulators: https://docs.velafi.com/docs/sandbox#sandbox-testing-tools.
4. In production, after the developer approves, register the webhooks and run a low-value transaction end to end.
5. Run `velafi-go-live-check` before launch.

## Reference links

- Webhook setup (verification, delivery and retries): https://docs.velafi.com/api-reference/webhooks/webhook-setup.md
- Webhooks guide: https://docs.velafi.com/docs/guides/webhooks.md
- Order statuses (polling vs webhook codes): https://docs.velafi.com/docs/order-statuses.md
- Go-live checklist: https://docs.velafi.com/docs/use-cases/go-live-checklist.md
- Sandbox: https://docs.velafi.com/docs/sandbox.md
