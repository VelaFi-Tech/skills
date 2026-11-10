# Errors and idempotency

Source: https://docs.velafi.com/docs/error-codes.md, https://docs.velafi.com/api-reference/authentication.md, https://docs.velafi.com/docs/use-cases/go-live-checklist.md

## Response shapes

| HTTP | Body |
|---|---|
| `200` | `{"code":200,"msg":"SUCCESS","data":...}` (some endpoints: `code` `0`, `msg` `success`) |
| `400` | `{"code":<error>,"msg":"..."}`, optional `message` and `fields`. Most errors repeat the code in the `error_code` response header (`30012` does not). |
| `404` / `405` | Not the VelaFi envelope: `{"timestamp":...,"status":404,"error":"Not Found","message":"","path":"..."}` |
| `500` | `{"code":-1001,"msg":"Internal error."}` |

Error codes are negative, except `30012`. Error bodies have no `data`.

## Authentication and request errors

| Code | Where | Meaning | Action |
|---|---|---|---|
| `-1002` | Token request | `X-BH-APIKEY` missing or malformed | Fix config |
| `-1002` | API call | `X-BH-TOKEN` missing | Fix client |
| `-1004` | Any | Malformed request; on the token request, `signature` missing (or `timestamp` missing while other params are sent). `msg` names the parameter. | Fix request |
| `-1103` | Token request | No query parameters, or only `signature` | Fix request |
| `-1022` | Token request | Signature mismatch or unknown API key | Check key/secret pair and environment |
| `-1022` | API call | Token invalid or expired | Get a new token, resend once |
| `-1023` | Any | Key has no IP whitelist | Add server IPs on API Management |
| `-2015` | Token request | Key or account disabled, or IP not whitelisted | Check key status and whitelist |
| `-2015` | API call | Key disabled or deleted, or account disabled | Alert |
| `-2019` | API call | IP not on the key's whitelist | Add the egress IP |
| `-5033` | Token request | API access not enabled | Contact VelaFi |
| `-1000` | Any | Credentials could not be verified for another reason | Alert |
| `-1005` | Any | Account type not allowed to call this endpoint | Contact VelaFi |
| `-1130` | Any | A field is missing or invalid (`msg` names it; spelled `paramter`) | Fix input |
| `-1189` | Any | Body could not be converted to expected types | Fix input |

## Outcome unknown: look up before you retry

These codes do not say whether the request was carried out:

| Code | `msg` |
|---|---|
| `-1001` | `Internal error.` |
| `-1006` | `Execution status unknown.` (also rate-limit rejections and some invalid input on read-only endpoints) |
| `-1007` | `Timeout waiting for response from backend server.` |
| `30012` | `Network busy, Try again later` (no `error_code` header) |

Treat a network timeout or dropped connection on a create call the same way.

On a call that creates or changes something:

1. Do not create a new `clientId`.
2. Look the record up with the endpoint in the table below.
3. Found: use it; do not retry.
4. Not found: retry with the **same** `clientId`. A `-1174` (or `Duplicate withdrawal request`) on that retry means the first request went through; look it up again.

On read-only `GET` calls: check input, back off, retry.

## clientId rules and lookups

| Create call | `clientId` | Unique across | Reused value | Look up with |
|---|---|---|---|---|
| `POST /v2/order/fiat_to_crypto`, `POST /v2/order/crypto_to_fiat` | Optional, up to 40 chars | All ramp orders on the account | `-1174` | `GET /v2/order/detail?orderType=<type>&clientId=<id>` |
| `POST /v2/order/fiat_to_fiat` | Optional, up to 40 chars | All `fiat_to_fiat` orders on the account | `-1174` | `GET /v2/orders?orderType=fiat_to_fiat` for the time window, match `clientId` |
| `POST /v2/merchant/claimfunds`, `POST /v2/merchant/transfer` | Send on every request | All funding records on the account | `-1174` | `GET /v2/merchant/funding/records` with `clientId` |
| `POST /v2/assets/withdraw` | Required | Withdrawals of the same kind (external or VelaFi destination) for that merchant | `Duplicate withdrawal request` | `GET /v2/assets/withdrawalOrders` with `clientId` |
| `POST /v2/assets/internalTransfer` | Optional | Internal transfers sent by that merchant | `-4040` `Duplicate withdrawal request` | `GET /v2/assets/internalTransferOrders` with `clientId` |
| `POST /v2/merchants` | None | — | — | `GET /v2/merchants?status=-1`, match `email` |

Rules:

- Generate a fresh `clientId` per operation (for example a UUID or a prefixed ID from your own database). Never use a constant, a timestamp alone, or a value derived only from amount/beneficiary.
- Persist it with your pending record before sending the request.
- A `clientId` stays bound to its record forever, including after cancellation. A new attempt after a **final failure** gets a new `clientId`.
- Even when the field is optional, always send one, or you cannot safely resolve an outcome-unknown response.

## Common business errors worth handling explicitly

| Code | Meaning |
|---|---|
| `-1131` | Balance insufficient |
| `-5050` / `-5060` | Below minimum / above maximum order amount |
| `-5029`, `-5030`, `-5081` | Monthly / monthly-with-merchant / daily-with-merchant limit exceeded |
| `-5200` | Quote expired or invalid |
| `-5026` | Too many orders under review; wait |
| `-1173` | Crypto address not valid for the network |

For failed orders, read `failCode` and `failReason` from `GET /v2/order/detail`. `failReason` can be empty or the provider's raw text: log it and act on the order status.
