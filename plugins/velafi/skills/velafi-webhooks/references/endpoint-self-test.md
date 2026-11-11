# Webhook endpoint self-test

Proves that the developer's webhook handler verifies signatures, acknowledges correctly, handles duplicates and responds fast, before any real VelaFi delivery arrives. Webhooks are not sent in the sandbox, so this is how the handler is tested before going live. Build the test in the developer's own project and language (for example an integration test), next to the handler.

## Rules

- **Never contact VelaFi.** The test signs its own sample events with a throwaway key and sends them only to the developer's handler.
- **Local only.** Send to `localhost`, `127.0.0.1` or `::1`. Use any other address only if the developer confirms it is a development environment they own.
- **Throwaway key.** Generate a new RSA-2048 key pair for the test. Configure its public key as the webhook verification key in the **development** environment only, for the duration of the test. Never commit the private key: keep it in memory or in a git-ignored file, and add any key files to `.gitignore`.
- **Restore the real key.** When the test is done, remind the developer to put the real `publicKey` back in the development config.

## How to sign a test event

VelaFi signs the raw request body with RSA-SHA256 (PKCS#1 v1.5) and sends the signature as hex in the `signature` header. The webhook `publicKey` is a Base64 X.509 SubjectPublicKeyInfo (DER) key. The test must match this exactly:

1. Generate an RSA-2048 key pair. Export the public key as Base64 X.509 SubjectPublicKeyInfo (DER), the same format as VelaFi's `publicKey`, and configure it in the dev environment.
2. Serialize the event to bytes once. Add a fresh `timestamp` (Unix milliseconds, as a string) to every delivery attempt.
3. Sign those exact bytes with RSA-SHA256, PKCS#1 v1.5, and hex-encode the signature (lowercase).
4. `POST` the same bytes with headers `Content-Type: application/json` and `signature: <hex>`.

Send one event with compact JSON and one with spaced JSON. A handler that verifies a re-serialized body instead of the raw bytes fails on one of them.

## Sample events

Placeholder data based on the documented example payloads (https://docs.velafi.com/api-reference/webhooks/webhook-setup.md). Replace the IDs with fresh random values for each run.

`FUNDING_WEBHOOK` deposit (status `2`):

```json
{"webhookId":"00000000000000000000000000000000","eventType":"FUNDING_WEBHOOK","txId":"<random>","clientId":"selftest-<random>","userId":"100000","merchantId":"100001","merchantName":"Example Merchant","fiat":"ARS","totalAmount":"22","amount":"20","fee":"2","refundedAmount":"0","paymentId":"63","userPaymentId":"91","type":"DEPOSIT","status":"2","completedTime":"<ms>","createTime":"<ms>","updateTime":"<ms>","cardNo":"0000000001","taxId":"20000000001","payerName":"José Pérez","payerAccount":"0000000000000000000005","depositAlias":"alias","bankWebhookInfo":"{}","timestamp":"<ms>"}
```

`ORDER_WEBHOOK` sell order (`orderStatus` `60`):

```json
{"webhookId":"00000000000000000000000000000000","eventType":"ORDER_WEBHOOK","orderId":"<random>","clientId":"selftest-<random>","userId":"100000","merchantId":"100001","settingsId":"12","orderType":"SELL","fiat":"MXN","fiatAmount":"99","arriveFiatAmount":"99","fiatFee":"0","crypto":"USDT","cryptoAmount":"5","orderPrice":"19.8158","orderStatus":"60","createTime":"<ms>","updateTime":"<ms>","fiatCurrency":"MXN","orderAmount":"99","arriveOrderAmount":"99","mcSettingsId":"12","cryptoCurrency":"USDT","quantity":"5","timestamp":"<ms>"}
```

`CRYPTO_WITHDRAW_WEBHOOK` (`SUCCESS`):

```json
{"webhookId":"00000000000000000000000000000000","eventType":"CRYPTO_WITHDRAW_WEBHOOK","withdrawId":"<random>","clientId":"selftest-<random>","userId":"100000","merchantId":"100001","crypto":"USDT","network":"TRC20","address":"YOUR_DESTINATION_ADDRESS","amount":"100","fee":"1","netAmount":"99","status":"SUCCESS","statusCode":"6","txHash":"4a7f0c3e2b1d9f8e7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f","createTime":"<ms>","completeTime":"<ms>","timestamp":"<ms>"}
```

Send only the event types the developer's handler subscribes to. The `FUNDING_WEBHOOK` sample contains a non-ASCII payer name on purpose.

## Checks

For each event, report PASS, WARN or FAIL:

| Check | PASS | FAIL |
|---|---|---|
| (a) Valid signature | HTTP 2xx and a body that is exactly `{"callbackStatus":"SUCCESS"}` | Any other status or body. Extra keys, different casing or `{"status":"ok"}` count as failures. |
| (b) Duplicate | The same event sent again (new `timestamp`, new signature) is acknowledged again with SUCCESS, and the handler does not process it twice | Not acknowledged, or processed twice |
| (c) Tampered signature | Not acknowledged with SUCCESS | Acknowledged with SUCCESS: the handler is not verifying signatures |
| (c) Missing `signature` header | Not acknowledged with SUCCESS | Acknowledged with SUCCESS |
| (d) Response time | Under 5 seconds | 30 seconds or more (VelaFi waits 60 seconds, then counts a failed attempt). Between 5 and 30 seconds is WARN: move slow work out of the request path. |

If the valid event itself failed (a) and a tampered or unsigned request gets exactly the same response, report WARN (inconclusive): signature checking cannot be confirmed until (a) passes.

## Run it yourself

Developers who prefer a ready-made script can run `tools/check_webhook_endpoint.py` from https://github.com/VelaFi-Tech/skills themselves. It sends the same events and checks, only to localhost unless `--allow-remote` is passed, and never contacts VelaFi.
