---
name: velafi-onramp
description: Build a VelaFi on-ramp that converts local currency (MXN, ARS, COP, BRL and others) into USDT or USDC with fiat_to_crypto orders, prefunded from the Pending Fund balance (paymentId 70) or paid per order by a payer's bank transfer, with optional quoteId rate lock and automatic withdrawal to an external address. Use when a developer wants to buy USDT with MXN, buy stablecoins with local currency, build an on-ramp or fiat-to-crypto flow, show payment instructions (CLABE, Pix) for an order, handle expired unpaid orders, or handle ORDER_WEBHOOK and ON_RAMP_WITHDRAW_WEBHOOK for buy orders.
license: Apache-2.0
---

# VelaFi on-ramp (fiat_to_crypto)

## Overview

You will build a server-side flow that creates `fiat_to_crypto` orders with `POST /v2/order/fiat_to_crypto`, tracks them to a final status, and optionally sends the purchased crypto to an external wallet. When the order completes (`orderStatus` `60`), the crypto (`cryptoAmount`) is credited to the merchant's VelaFi wallet.

Use this skill for **local currency in, stablecoin out**. Use a sibling skill for anything else:

- `velafi-api-setup`: API key, IP whitelist, token generation (`X-BH-TOKEN`). Do this first.
- `velafi-webhooks`: registering webhooks, verifying the `signature` header, the exact acknowledgement body.
- `velafi-offramp-payouts`: stablecoin in, local currency paid to a beneficiary (`crypto_to_fiat`).
- `velafi-crypto-wallet`: balances, deposit addresses, whitelisted withdrawals, internal transfers.
- `velafi-global-payments`: fiat in one country, fiat out in another (`fiat_to_fiat`).
- `velafi-onboard-merchants`: creating merchants and activating currency accounts.
- `velafi-collect-virtual-accounts`: collecting payer deposits into the currency account (this fills the Pending Fund balance used by prefunded orders).
- `velafi-go-live-check`: run before switching to production.

Main doc: https://docs.velafi.com/docs/use-cases/convert-to-stablecoins.md

## Before you start

**Ask first, then build.** Before you write or change any code, ask the developer the questions in this section and wait for their answers. If you have a tool for asking the developer multiple-choice questions, use it for questions with a few clear choices, such as environment, corridor, amount mode or funding crypto, and ask them in rounds if there are more than the tool takes at once. Ask open questions, such as merchant IDs, IP addresses or file paths, as text. Without such a tool, ask all the questions together in one message. If the developer's request already answers a question, state your understanding in one line and ask them to confirm it instead of asking again. Do not assume a country, currency, channel, merchant ID, amount mode or environment. Only skip a question the developer explicitly tells you to skip, and say which default you are using.

Confirm these prerequisites (doc: Convert to Stablecoins, "Before you start"):

- API access works (key, whitelisted server IPs, token). If not, run `velafi-api-setup`.
- The order's `merchantId` is a verified merchant under the account.
- The merchant has an **activated currency account** for the fiat. See https://docs.velafi.com/docs/guides/activating-merchant-account.md
- Webhooks: `ORDER_WEBHOOK`, plus `FUNDING_WEBHOOK` if prefunded and `CRYPTO_WITHDRAW_WEBHOOK` if withdrawing (use `velafi-webhooks`).

Ask the developer:

1. Which country, fiat and crypto (for example Mexico / MXN / USDT)?
2. **Can the business hold a local-currency balance?** If yes, recommend the prefunded model. If the payer must pay each order directly, use pay-per-order.
3. Pay-per-order only: one payer or many payers on the same currency account? (Many payers means one virtual account per payer, via `depositAlias`.)
4. Where should the crypto end up: stay in the VelaFi wallet, automatic withdrawal per order (only if VelaFi enabled it for the account), or a manual withdrawal?
5. Language and framework of their backend, and do they have sandbox credentials?

### Choose a funding model

| | Prefunded (recommended) | Pay-per-order |
| --- | --- | --- |
| How it is paid | From the merchant's Pending Fund balance for that currency | Payer sends a bank transfer to the order's `paymentInfo` |
| `paymentId` | `70` (VelaFi Pending Fund) | The currency account's channel, for example `105` (SPEI, Finco Pay) |
| Balance check | At creation; rejected with an insufficient-balance error if not covered, no order created | None at creation |
| Result | Completes within seconds | Completes when the full payment arrives; cancelled (`70`) if the payment window passes |

Recommend prefunded when the business can hold a balance: the order is paid the moment it is created, cannot expire unpaid, and you know before trading whether funds are there. Many pay-per-order orders expire unpaid.

## Workflow

Base URLs: production `https://api.velafi.com`, sandbox `https://api-test.velafi.com`. Every call sends `X-BH-TOKEN`. Default to the sandbox.

1. **Prefunded only: fund the balance.** `GET /v2/merchant/addfunds` returns the merchant's deposit details; send fiat there. Each credited deposit sends `FUNDING_WEBHOOK` (`type` `DEPOSIT`, `status` `2`). Check `balance` with `GET /v2/merchant/accounts` before large orders.
   - https://docs.velafi.com/api-reference/merchant/get-pending-fund-account.md
   - https://docs.velafi.com/api-reference/merchant/get-a-list-of-merchant-accounts.md
2. **Optional: lock the rate.** `GET /v2/user/crypto-quote?country=Mexico&from=MXN&to=USDT&createQuoteId=true`. `price` is fiat per 1 unit of crypto. A `quoteId` is valid 10 s in production (300 s in sandbox), single-use, bound to the `country`, fiat and crypto. Request it immediately before creating the order, never during user input. Without a `quoteId`, the order is priced at creation. Limit: 500 requests per minute per account.
   - https://docs.velafi.com/api-reference/quote/get-user-quote-for-crypto-fiat.md
3. **Create the order.** `POST /v2/order/fiat_to_crypto` with `merchantId`, `country` (full name), `fiat`, `crypto`, `paymentId`, `fiatAmount` or `cryptoAmount` (if both, `fiatAmount` wins), a unique `clientId` (max 40 chars), and optional `quoteId`.
   - Prefunded: `paymentId: 70`. If covered, the order is paid right after creation and moves to `60`, unless it first needs review or documents (`10`, `11`, `31`). The debit appears in Funding Records as `BUY_CRYPTO`.
   - Pay-per-order: `paymentId` of the merchant's channel (see https://docs.velafi.com/docs/payment-methods.md). Add `depositAlias` when each payer has a virtual account. PSE (`141`) needs `inFieldJson.bank` (PSE bank code). Order starts in `40`, or `10`, `11`, `31`.
   - Automatic withdrawal (only if enabled for the account): add `network` and `address` (both or neither). Production networks `POL` or `SPL20`; sandbox `POL` or `TSPL20`. Accounts without the feature get `-4040` ("You are currently not a user of the onRamp automatic withdrawal service.").
   - Response: `{"code":200,"msg":"SUCCESS","data":{"orderId":...}}`. Store `orderId` with your `clientId`.
   - https://docs.velafi.com/api-reference/order/create-a-fiat-to-crypto-order.md
4. **Pay-per-order only: show payment instructions.** `GET /v2/order/detail?orderType=fiat_to_crypto&orderId=...` and show the payer `paymentInfo` (for example the CLABE) and the exact `fiatAmount`, with a deadline from `createTime`. The payment window is set per account and is not returned by the API; ask VelaFi for the value. A short payment does not complete the order. On manual payment methods, call `POST /v2/order/confirm` with `orderType=fiat_to_crypto` after the transfer is sent.
   - https://docs.velafi.com/api-reference/order/retrieve-a-specific-order.md
   - https://docs.velafi.com/api-reference/order/confirm-a-specific-order.md
5. **Track to completion.** Handle `ORDER_WEBHOOK` (`orderType` `BUY`) and also poll `GET /v2/order/detail?orderType=fiat_to_crypto&clientId=...`. Done at `60`; failed at `70`, `80`, `81`. Polling shows review rejections as `80`/`81`; the webhook sends them as `70`. Read `references/statuses-and-failures.md`.
6. **Optional: deliver the crypto.** Automatic withdrawal sends `ON_RAMP_WITHDRAW_WEBHOOK` on success only (key on `orderId`, record `txHash`); failed ones send nothing. Both automatic and manual withdrawals send `CRYPTO_WITHDRAW_WEBHOOK` at a final status; for an automatic one its `clientId` is the on-ramp `orderId`. For a manual withdrawal use `velafi-crypto-wallet`.
   - https://docs.velafi.com/api-reference/webhooks/on-ramp-withdraw-message-push.md
7. **Reconcile.** Scheduled job re-reads every order open on your side with Get Order; use `GET /v2/orders` with a time range for totals and `GET /v2/merchant/funding/records` for `DEPOSIT` and `BUY_CRYPTO`. Webhooks are dropped after 3 failed attempts.

### Retries and idempotency

- A reused `clientId` is rejected with `-1174` (repeated submission); the response does not return the original order.
- On a timeout or outcome-unknown error (for example `-1007`): look the order up by `clientId` first. Found: do not create again. Not found: retry with the **same** `clientId` and a **new** quote (a rejected create can consume a `quoteId`).
- A `clientId` stays bound to its order permanently, even after cancellation. New order, new `clientId`.

## Rules

- Never hardcode, log or commit the API key, secret or tokens. Load them from env vars or a secrets manager; add `.env*` to `.gitignore`.
- All VelaFi calls run server-side. Never call the API from a browser or mobile app.
- Default to the sandbox. Get the developer's explicit confirmation before anything runs against production or moves money.
- Never mark an order complete before `orderStatus` `60` is confirmed by webhook or Get Order. Never treat the create response as success of the trade.
- Always send a unique `clientId` on create; store it before sending.
- Read `orderStatus` together with `orderType`; ramp and global payment codes differ.
- Deduplicate `ORDER_WEBHOOK` on `orderId` + `orderStatus`; events can repeat, arrive out of order, or skip statuses. When an event does not fit your state, re-read the order.
- After `70` on pay-per-order, create a **new** order with a new `clientId`; a cancelled order cannot be reopened. A late payment lands in the Pending Fund balance (`FUNDING_WEBHOOK` `DEPOSIT`), not on the cancelled order.
- With several payers on one currency account, give each a virtual account (`depositAlias`) so one payer's transfer cannot pay another's order.
- Do not retry an insufficient-balance rejection in a loop; top up first, then create with a new `clientId` and quote.
- Do not resubmit `80`/`81` orders unchanged.

## Verify

- Sandbox: `https://api-test.velafi.com`. **Webhooks are not sent in the sandbox**: poll `GET /v2/order/detail`.
- Fund a test merchant's balance, or pay a pay-per-order order, with the fiat deposit simulator `POST /v2/platform/test/deposit` (query params `merchantId`, `fiat`, `fiatAmount`, `paymentId`, optional `depositAlias`). See https://docs.velafi.com/docs/sandbox#sandbox-testing-tools
- Test the expiry path by creating a pay-per-order order and not paying it. Simulators only produce successful deposits.
- Check: duplicate `clientId` handling, timeout lookup path, `70` handling, webhook handler returns HTTP 2xx with exactly `{"callbackStatus":"SUCCESS"}` (test with a recorded payload).
- Before production, run `velafi-go-live-check` and the use-case checklist: https://docs.velafi.com/docs/use-cases/convert-to-stablecoins#go-live-checklist

## Reference links

- `references/statuses-and-failures.md`: status codes, webhook mapping, failure table.
- On-Ramp guide: https://docs.velafi.com/docs/guides/on-ramp.md
- Order Statuses: https://docs.velafi.com/docs/order-statuses.md
- List Orders: https://docs.velafi.com/api-reference/order/retrieve-a-list-of-orders.md
- Order Event: https://docs.velafi.com/api-reference/webhooks/fiat-crypto-order-message-push.md
- Upload Documents: https://docs.velafi.com/api-reference/order/upload-invoice-documents-for-a-specific-order.md
- Funding Records: https://docs.velafi.com/api-reference/merchant/retrieve-funding-records.md
- Error Codes: https://docs.velafi.com/docs/error-codes.md
