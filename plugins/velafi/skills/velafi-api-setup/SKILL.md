---
name: velafi-api-setup
description: Set up a server-side VelaFi API client - sandbox vs production base URLs, API key and secret handling, signing GET /v2/token/generate (HMAC-SHA256), caching and refreshing the X-BH-TOKEN business token, IP whitelist, error handling on negative codes, outcome-unknown codes (-1001, -1006, -1007, 30012) that need a lookup before retrying, rate limits, clientId idempotency rules per endpoint, and merchant IDs. Use first for any VelaFi integration, when a token request fails (-1022, -1023, -2015, -5033) or API calls fail with -2019, or when writing the shared HTTP client other VelaFi skills build on.
license: Apache-2.0
---

# VelaFi API setup

## Overview

This skill builds the foundation every VelaFi integration needs: a small server-side client that gets and refreshes a business token, sends authenticated JSON requests, and turns VelaFi errors into decisions (fix input, refresh token, back off, or look up before retrying).

It is the entry point for the other VelaFi skills. Build this first, then:

- `velafi-webhooks` for receiving and verifying webhook events.
- The flow skills: `velafi-onboard-merchants`, `velafi-collect-virtual-accounts`, `velafi-payouts-from-balance`, `velafi-onramp`, `velafi-offramp-payouts`, `velafi-global-payments`, `velafi-crypto-wallet`.
- `velafi-go-live-check` before switching to production.

`scripts/check_token.py` checks the developer's credentials against the sandbox without writing any code.

## Before you start

**Ask first, then build.** Before you write or change any code, ask the developer the questions in this section and wait for their answers. Ask them together in one message. If the developer's request already answers a question, state your understanding in one line and ask them to confirm it instead of asking again. Do not assume a country, currency, channel, merchant ID, amount mode or environment. Only skip a question the developer explicitly tells you to skip, and say which default you are using.

Ask the developer:

1. **Which environment do you have credentials for?** Sandbox keys come from VelaFi (contact@velafi.com) and only work on `https://api-test.velafi.com`. Production keys are created on the **API Management** page of the dashboard and only work on `https://api.velafi.com`. The two sets are not interchangeable.
2. **Is API access enabled on the account?** Until VelaFi enables it, token requests fail with `-5033`.
3. **Which public IP addresses will call the API?** Every key needs an IP whitelist (up to 5 IPv4/IPv6 addresses per key, no CIDR ranges). Laptops behind changing IPs and serverless platforms without a fixed egress IP will fail.
4. **Language and framework**, and where secrets live (env vars, a secrets manager).
5. **Which merchant(s) the integration acts for** (merchant IDs, see below).

Default to the sandbox. Do not call production or move money without the developer's explicit confirmation.

## Workflow

### 1. Configuration

Read from the environment (or the developer's secrets manager), never from source:

| Variable | Value |
|---|---|
| `VELAFI_BASE_URL` | `https://api-test.velafi.com` (sandbox) or `https://api.velafi.com` (production) |
| `VELAFI_API_KEY` | API key for that environment |
| `VELAFI_API_SECRET` | API secret for that environment |

Add `.env*` to `.gitignore`. Keep sandbox and production values in separate configs. Check credentials before writing code:

```bash
VELAFI_API_KEY=... VELAFI_API_SECRET=... python3 scripts/check_token.py
```

It defaults to the sandbox and refuses `https://api.velafi.com` unless `--production` is passed (only with the developer's approval). It prints a masked token and `expireTime`, or the error code and what it means.

### 2. Get a token — `GET /v2/token/generate`

Docs: https://docs.velafi.com/api-reference/generate-token.md, https://docs.velafi.com/api-reference/authentication.md

1. `timestamp` = current Unix time in **milliseconds**.
2. `signature` = HMAC-SHA256 of the exact string `timestamp=<timestamp>`, keyed with the API secret, encoded as 64-char **lowercase hex**.
3. `GET {base}/v2/token/generate?timestamp=<ts>&signature=<sig>` with header `X-BH-APIKEY: <api key>`. Send only these two query parameters.
4. Success: `{"code":200,"msg":"SUCCESS","data":{"token":"...","expireTime":"1740568725231"}}`. `expireTime` is a string of Unix milliseconds.

The secret is never sent in any header or parameter. Only the token request is signed; other calls carry just the token.

### 3. Cache and refresh the token

- Cache the token with its `expireTime` and request a new one before that time (refresh with a safety margin, and use one in-flight refresh per process so concurrent requests do not stampede the token endpoint).
- If any call returns `-1022`, the token expired or is unknown: get a new token and resend the call once.
- Never log the token or put it in URLs.

### 4. Send authenticated requests

- Header `X-BH-TOKEN: <token>` on every authenticated call. The API key never goes in `X-BH-TOKEN`.
- Request bodies are JSON with `Content-Type: application/json`.
- All calls are server-side. Never call VelaFi from browser or mobile code.
- Success envelope: HTTP `200` with `code` `200` (a few endpoints, such as `POST /v2/upgrade/limits`, return `code` `0`). Treat `200` or `0` as success.

### 5. Handle errors by `code`, not HTTP status

Docs: https://docs.velafi.com/docs/error-codes.md

Errors return HTTP `400` (or `500` with `-1001`) and `{"code": <negative>, "msg": "..."}`. There is no `401` or `429`. Do not match on `msg`; it can contain runtime values or placeholders. Map codes to actions:

| Codes | Action |
|---|---|
| `-1022` | Refresh the token, resend once. |
| `-1002`, `-1023`, `-2015`, `-2019`, `-5033` | Configuration problem (missing header, no whitelist, IP not whitelisted, disabled key, API access off). Alert; do not retry in a loop. |
| `-1001`, `-1006`, `-1007`, `30012` on a call that creates or changes something | **Outcome unknown.** The operation may have completed. Look it up by `clientId` first (table below); retry with the **same** `clientId` only if nothing exists. |
| `-1006` on a rate-limited endpoint, `30012` | Back off before retrying. |
| `-1006` on a read-only `GET` | Check input (for example an unsupported corridor) and retry. |
| `-1174` on a retry | The first request went through. Look the record up. |
| Other negative codes | Business or validation error. Surface it; fix input before retrying. |

Read `references/errors-and-idempotency.md` for the full handling rules and the lookup endpoint for each create call.

### 6. Idempotency with `clientId`

Generate a new unique `clientId` for every create call, **store it before sending**, and reuse it only to retry that same request. A reused `clientId` is rejected, and the rejection does not return the original record.

| Call | `clientId` | Reused value |
|---|---|---|
| `POST /v2/order/fiat_to_crypto`, `POST /v2/order/crypto_to_fiat` | Optional, max 40 chars, unique across both | `-1174` |
| `POST /v2/order/fiat_to_fiat` | Optional, max 40 chars | `-1174` |
| `POST /v2/merchant/claimfunds`, `POST /v2/merchant/transfer` | Send on every request | `-1174` |
| `POST /v2/assets/withdraw` | Required | `Duplicate withdrawal request` |
| `POST /v2/assets/internalTransfer` | Optional | `-4040` `Duplicate withdrawal request` |

A `clientId` stays bound to its record forever, even after cancellation. `POST /v2/merchants` has no `clientId`: before retrying it, look for the merchant by `email` with `GET /v2/merchants?status=-1`.

### 7. Merchant IDs

- `userId` is your VelaFi account. A **merchant ID (MID, `merchantId`)** identifies each verified merchant under the account; transaction, account and settlement calls take a `merchantId`.
- Webhooks belong to the account, so one webhook receives events for every merchant: route events by `merchantId`.
- `GET /v2/merchants` lists merchants; pass `status=-1` to include ones not yet approved. Merchant statuses: `1` authenticating, `2` normal, `3` failed, `4` incomplete. Docs: https://docs.velafi.com/docs/merchants.md

### 8. Rate limits

Counted per account and per endpoint, in a one-minute window. Over the limit returns HTTP `400` with `-1006`, not `429`.

| Endpoint | Limit/min |
|---|---|
| `GET /v2/user/crypto-quote`, `GET /v2/user/fiat-quote` | 500 |
| `POST /v2/order/fiat_to_crypto`, `/crypto_to_fiat`, `/fiat_to_fiat` | 500 each |
| `GET /v2/merchant/check/alias`, `GET /v2/merchant/check/cvu` | 100 each |
| Sandbox deposit simulators | 20 |

Any endpoint can return `30012` under too many concurrent requests. Docs: https://docs.velafi.com/api-reference/overview#rate-limits

## Rules

- Never hardcode, log, print or commit the API key, API secret or tokens. Use env vars or a secrets manager; add `.env*` to `.gitignore`.
- All VelaFi calls are server-side only.
- Never send the API secret anywhere; it only computes the signature.
- Never mix sandbox credentials with the production URL or the reverse.
- Default to the sandbox. Get the developer's explicit confirmation before calling production or moving money.
- Branch on `code`; never on `msg` and never on HTTP status alone.
- Never blindly retry a create call after `-1001`, `-1006`, `-1007`, `30012` or a network timeout. Look up by `clientId` first, then retry with the same `clientId`.
- Never claim an operation succeeded before its final status (webhook or polled status) confirms it. A `200` on a create call means accepted, not completed.

## Verify

1. `python3 scripts/check_token.py` returns `OK: token received` against the sandbox.
2. Call `GET /v2/user/account` with the token; a `200` confirms key, secret, IP whitelist and API access.
3. Unit-test the signer against a fixed timestamp and secret (HMAC-SHA256 of `timestamp=<ts>`, lowercase hex).
4. Force a `-1022` (send a bogus token) and check the client refreshes once and does not loop.
5. Simulate a timeout on an order create and check the code looks up the `clientId` before retrying.
6. Before production, run `velafi-go-live-check`.

Sandbox notes: https://docs.velafi.com/docs/sandbox.md (no KYC, no real funds, no webhooks; deposit simulators at https://docs.velafi.com/docs/sandbox#sandbox-testing-tools).

## Reference links

- Authentication: https://docs.velafi.com/api-reference/authentication.md
- Generate token: https://docs.velafi.com/api-reference/generate-token.md
- API overview (envelope, HTTP statuses, rate limits): https://docs.velafi.com/api-reference/overview.md
- Error codes: https://docs.velafi.com/docs/error-codes.md
- Create your API key: https://docs.velafi.com/docs/guides/creating-api-key.md
- Sandbox: https://docs.velafi.com/docs/sandbox.md
- Go-live checklist: https://docs.velafi.com/docs/use-cases/go-live-checklist.md
- Docs MCP server for agents: https://docs.velafi.com/docs/developer-tools/build-with-ai.md
