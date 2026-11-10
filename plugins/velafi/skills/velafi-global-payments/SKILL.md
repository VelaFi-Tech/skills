---
name: velafi-global-payments
description: Build VelaFi global payments, cross-border fiat-to-fiat transfers over stablecoin rails with fiat_to_fiat orders. Covers listing supported corridors (fiat/fiat pairs), payment methods per side, locking a rate with a fiat/fiat quoteId, registering the recipient beneficiary, creating the order with on-ramp and off-ramp merchants, showing pay-in instructions, global payment status codes (41, 51, 60, 71, 72, 90) and GLOBAL_PAYMENT_WEBHOOK. Use when a developer wants to send MXN to a USD bank account, pay ARS or COP from MXN, move BRL to USD in Hong Kong, build cross-border or remittance payments, or handle fiat_to_fiat order statuses.
license: Apache-2.0
---

# VelaFi global payments (fiat_to_fiat)

## Overview

A global payment collects fiat in one country (on-ramp leg) and pays fiat out in another (off-ramp leg). VelaFi bridges the two through stablecoins internally; neither side handles crypto. You will build server-side code that checks the corridor, optionally locks a rate, creates the order with `POST /v2/order/fiat_to_fiat`, shows the sender the pay-in instructions, and tracks the order with the **global payment status codes**, which differ from ramp order codes.

Sibling skills:

- `velafi-api-setup`: API key, IP whitelist, token (`X-BH-TOKEN`). Do this first.
- `velafi-webhooks`: register `GLOBAL_PAYMENT_WEBHOOK`, verify signatures, exact acknowledgement.
- `velafi-offramp-payouts`: pay fiat out of a **stablecoin** balance (`crypto_to_fiat`); also covers beneficiary registration in depth.
- `velafi-onramp`: convert local currency to stablecoins.
- `velafi-onboard-merchants`: creating merchants and activating currency accounts on both sides.
- `velafi-go-live-check`: run before production.

Main doc: https://docs.velafi.com/docs/guides/global-payments.md

## Before you start

**Ask first, then build.** Before you write or change any code, ask the developer the questions in this section and wait for their answers. If you have a tool for asking the developer multiple-choice questions, use it for questions with a few clear choices, such as environment, corridor, amount mode or funding crypto, and ask them in rounds if there are more than the tool takes at once. Ask open questions, such as merchant IDs, IP addresses or file paths, as text. Without such a tool, ask all the questions together in one message. If the developer's request already answers a question, state your understanding in one line and ask them to confirm it instead of asking again. Do not assume a country, currency, channel, merchant ID, amount mode or environment. Only skip a question the developer explicitly tells you to skip, and say which default you are using.

Every global payment involves two merchants:

- **On-ramp (sender) merchant** with an activated account for the sending country and currency.
- **Off-ramp (recipient) merchant** with an activated account for the receiving country and currency.
- **Beneficiary** registered on the off-ramp merchant. Its `userPaymentId` is the order's `offRampPaymentId`.

Ask the developer:

1. Sending country/currency and receiving country/currency? Check the corridor exists (step 1). Pairs are directional.
2. Which merchant IDs act as on-ramp and off-ramp merchants, and are both accounts activated? See https://docs.velafi.com/docs/guides/activating-merchant-account.md
3. Fix what the sender pays (`onRampFiatAmount`) or what the recipient receives (`offRampFiatAmount`)?
4. Does each sender get a virtual account (`depositAlias`)?
5. Language and framework; sandbox credentials available?

## Workflow

Base URLs: production `https://api.velafi.com`, sandbox `https://api-test.velafi.com`. Send `X-BH-TOKEN`. Default to the sandbox.

1. **Check the corridor.** `GET /v2/base/fiat/symbols` returns `onRampCountry`, `onRampFiat`, `offRampCountry`, `offRampFiat`, `accuracy` (decimal places for amounts). Verify the exact direction you need is listed. Known pairs: `references/statuses-and-pairs.md`.
   - https://docs.velafi.com/api-reference/basic-configuration/get-fiat-fiat-pairs.md
2. **Get payment methods per side.** `GET /v2/base/fiat/payments?onRampCountry=...&onRampFiat=...&offRampCountry=...&offRampFiat=...` returns `paymentListFrom` (pay-in methods: `paymentId`, `fiatFee`, `paymentType` `0` manual / `1` automatic) and `paymentListTo` (payout methods).
   - https://docs.velafi.com/api-reference/basic-configuration/get-fiat-fiat-payment-methods.md
3. **Register the recipient beneficiary** on the off-ramp merchant: `GET /v2/payments/templates?paymentId=...` then `POST /v2/payments` with `merchantId` (the off-ramp merchant), `paymentId`, `country`, `fiat`, `realName`, `fieldJson`. Use `data.id` only when `status` is `1`.
   - https://docs.velafi.com/docs/guides/managing-beneficiaries.md
4. **Optional: lock the rate.** `GET /v2/user/fiat-quote?onRampCountry=Mexico&onRampFiat=MXN&offRampCountry=Argentina&offRampFiat=ARS&createQuoteId=true`. `price` = units of off-ramp fiat per 1 unit of on-ramp fiat. `quoteId` is valid **20 s** in production (300 s sandbox), single-use, bound to the corridor. Request it right before creating the order. Limit: 500 requests per minute.
   - https://docs.velafi.com/api-reference/quote/get-user-quote-for-fiat-fiat.md
5. **Create the order.** `POST /v2/order/fiat_to_fiat` with:
   - On-ramp leg: `onRampCountry`, `onRampFiat`, `onRampPaymentId` (pay-in channel), `onRampMerchantId`, `onRampFiatAmount`, optional `depositAlias`, `inFieldJson.bank` when `onRampPaymentId` is `141`.
   - Off-ramp leg: `offRampCountry`, `offRampFiat`, `offRampPaymentId` (the beneficiary's `userPaymentId`), `offRampMerchantId`, `offRampFiatAmount` (used only when `onRampFiatAmount` is not sent).
   - Shared: unique `clientId` (max 40 chars, unique across all `fiat_to_fiat` orders), optional `quoteId`, `remark`.
   - Response `data.orderId`. Store it with your `clientId`.
   - https://docs.velafi.com/api-reference/order/create-a-fiat-to-fiat-order.md
6. **Show pay-in instructions.** `GET /v2/order/detail?orderType=fiat_to_fiat&orderId=...` (orderId is **required** for fiat_to_fiat). While the order is in `41`, show the sender `onRampPaymentInfo` and the exact `onRampFiatAmount`. The detail also returns `offRampFiatAmount`, `offArriveRampFiatAmount` (net to the recipient), fees per leg and `orderPrice`.
   - https://docs.velafi.com/api-reference/order/retrieve-a-specific-order.md
7. **Documents.** In `11` or `31`, upload with `POST /v2/order/invoice` (`orderType=fiat_to_fiat`, up to 5 files, 5 MB each). `11` moves to `12`; after a `31` upload the order shows `41` or `51` again.
   - https://docs.velafi.com/api-reference/order/upload-invoice-documents-for-a-specific-order.md
8. **Track to completion.** Handle `GLOBAL_PAYMENT_WEBHOOK` and poll Get Order. `60` = payout complete. `71`, `72`, `90` = failed and final. Read `references/statuses-and-pairs.md`.
   - https://docs.velafi.com/api-reference/webhooks/fiat-fiat-order-message-push.md
9. **Reconcile.** A scheduled job re-reads every order open on your side by `orderId`. For lists use `GET /v2/orders?orderType=fiat_to_fiat` (time range matches the last update time). The `orderStatus` filter for fiat_to_fiat matches the stored status: only `10`, `11`, `12`, `60`, `72` match exactly, so filter in your own code on the returned `orderStatus`.

### Retries and idempotency

- Reused `clientId` is rejected with `-1174`; no second order is created.
- Get Order does **not** accept `clientId` for fiat_to_fiat. After a timeout or outcome-unknown error (for example `-1007`), list recent orders with `GET /v2/orders?orderType=fiat_to_fiat` and match `clientId`. Found: do not create again. Not found: retry with the same `clientId` and a new quote (a rejected create can consume a `quoteId`).

## Rules

- Never hardcode, log or commit the API key, secret or tokens; use env vars or a secrets manager; add `.env*` to `.gitignore`.
- All VelaFi calls are server-side only.
- Default to the sandbox. Get explicit developer confirmation before any production call or money movement.
- Never report a payment as delivered before `orderStatus` `60` is confirmed (webhook or Get Order).
- **Always interpret `orderStatus` with `orderType`.** For fiat_to_fiat, `71` = pay-in cancelled (final), `72` = payout cancelled (final), `90` = risk review rejected. For ramp orders `71` means "Cancelling" and `72` "Refunded". Never share one status mapper across order types.
- Review rejections and review timeouts are reported as `71`, not as a separate rejected code.
- Deduplicate `GLOBAL_PAYMENT_WEBHOOK` on `orderId` + `orderStatus`. It is sent only for API-created orders and only for `10`, `31`, `41`, `51`, `60`, `71`, `72`; statuses can be skipped. It does not send `11`, `12` or `90`, so poll for those.
- Use the beneficiary's `userPaymentId` as `offRampPaymentId`, not a payment method ID. `onRampPaymentId` is a payment method ID.
- Verify the corridor in `GET /v2/base/fiat/symbols` before quoting; do not assume the reverse direction exists.

## Verify

- Sandbox: `https://api-test.velafi.com`. **Webhooks are not sent**: poll `GET /v2/order/detail?orderType=fiat_to_fiat&orderId=...`.
- Create an order with on-ramp and off-ramp merchants in different currencies and confirm the status progresses. The fiat deposit simulator is documented for merchant fiat accounts (https://docs.velafi.com/docs/sandbox#sandbox-testing-tools); confirm with VelaFi how to pay a fiat_to_fiat pay-in in the sandbox.
- Test duplicate `clientId`, timeout lookup through List Orders, and handling of `71`, `72`, `90`.
- Test the webhook handler with a recorded payload: signature verified, HTTP 2xx with exactly `{"callbackStatus":"SUCCESS"}`.
- Before production run `velafi-go-live-check` (https://docs.velafi.com/docs/use-cases/go-live-checklist.md) and register a production `GLOBAL_PAYMENT_WEBHOOK`.

## Reference links

- `references/statuses-and-pairs.md`: global payment status table, webhook mapping, supported pairs.
- Order Statuses: https://docs.velafi.com/docs/order-statuses.md
- List Orders: https://docs.velafi.com/api-reference/order/retrieve-a-list-of-orders.md
- Payment Methods: https://docs.velafi.com/docs/payment-methods.md
- Error Codes: https://docs.velafi.com/docs/error-codes.md
