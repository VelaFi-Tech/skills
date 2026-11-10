---
name: velafi-offramp-payouts
description: Build VelaFi payouts funded with stablecoins. Deposit USDT or USDC to a merchant wallet, register a beneficiary bank account, quote, and create crypto_to_fiat orders that pay MXN, BRL, ARS, COP and other local currency, or USD, EUR, HKD, SGD and NGN through Circle Payment Network (CPN). Use when a developer wants to pay out BRL from USDT, off-ramp or cash out crypto to a bank account, pay suppliers or sellers in local currency from a stablecoin balance, send SPEI/Pix/CVU/Bre-B payouts funded by crypto, handle post-funded orders (status 32), -1131 insufficient balance, refunds (72), or ORDER_WEBHOOK for sell orders.
license: Apache-2.0
---

# VelaFi stablecoin-funded payouts (crypto_to_fiat)

## Overview

You will build a server-side payout flow: fund the merchant's crypto wallet, register each recipient once as a beneficiary (`userPaymentId`), optionally lock a rate, create a `crypto_to_fiat` order per payout with `POST /v2/order/crypto_to_fiat`, and track it until the beneficiary is paid (`60`) or the payout is cancelled or refunded (`70`, `72`). VelaFi converts the crypto and sends fiat over the local rail (SPEI, Pix, CVU, Bre-B and others) or CPN.

Use this skill for **stablecoin in, fiat paid to a third party**. Sibling skills:

- `velafi-api-setup`: API key, IP whitelist, token (`X-BH-TOKEN`). Do this first.
- `velafi-webhooks`: register `ORDER_WEBHOOK`, verify signatures, exact acknowledgement.
- `velafi-crypto-wallet`: deposit addresses, balances, deposit history, crypto withdrawals.
- `velafi-onramp`: the reverse direction (local currency in, stablecoin out).
- `velafi-global-payments`: fiat in one country, fiat out in another, no crypto balance.
- `velafi-go-live-check`: run before production.

Paying out from a **fiat** balance (Pending Fund, `claimfunds`) is a different flow: use `velafi-payouts-from-balance`. Merchant creation and currency-account activation: `velafi-onboard-merchants`.

Main doc: https://docs.velafi.com/docs/use-cases/payouts-funded-by-stablecoins.md

## Before you start

Prerequisites:

- API access works (`velafi-api-setup`).
- A verified merchant with an **activated account for the payout currency and channel**. The beneficiary must use a payment method (`paymentId`) of that account. https://docs.velafi.com/docs/guides/activating-merchant-account.md
- `ORDER_WEBHOOK` registered (`velafi-webhooks`).

Ask the developer:

1. Payout country and currency, and which rail (see https://docs.velafi.com/docs/payment-methods.md)? For USD, EUR, HKD, SGD or NGN through CPN, read `references/cpn-payouts.md`.
2. Which crypto funds the payouts (USDT or USDC) and on which network will they deposit?
3. Fix the amount the beneficiary receives (`fiatAmount`) or what you spend (`cryptoAmount`)?
4. Has VelaFi enabled **post-funded off-ramp** for the account (can differ by fiat)? If not, the wallet must be funded before each order.
5. Language and framework, and are sandbox credentials available?

## Workflow

Base URLs: production `https://api.velafi.com`, sandbox `https://api-test.velafi.com`. Every call sends `X-BH-TOKEN`. Default to the sandbox.

1. **Fund the merchant wallet.** `GET /v2/assets/depositAddress?tokenId=USDT&chainType=TRC20&merchantId=...`. Check `allowDeposit` is `true`; send at least `minQuantity` to `address` (with `addressExt` if `needAddressTag`). There is **no webhook for crypto deposits**: confirm with `GET /v2/assets/depositOrders` (`status` `2` = successful) and read the spendable `free` amount from `GET /v2/assets/account/assets?merchantId=...`.
   - https://docs.velafi.com/api-reference/merchant/get-crypto-deposit-address.md
   - https://docs.velafi.com/api-reference/merchant/get-crypto-assets-balance.md
2. **Register the beneficiary once.** `GET /v2/payments/templates?paymentId=...` for the field keys, then `POST /v2/payments` with `merchantId` (always send it; same merchant as your orders), `paymentId`, `country`, `fiat`, `realName`, `fieldJson`. Store `data.id` as `userPaymentId`.
   - `status` `1` valid (can receive payouts), `2` verification in progress, `3` failed: read `failReason`; if the account already exists, use `sameAccountNumberId` instead of creating a new record.
   - Missing or invalid fields return `-4010`; dropdown fields need an option `code`.
   - https://docs.velafi.com/docs/guides/managing-beneficiaries.md
   - https://docs.velafi.com/api-reference/beneficiary/add-beneficiary.md
   - https://docs.velafi.com/api-reference/beneficiary/get-payment-templates.md
3. **Optional: lock the rate.** `GET /v2/user/crypto-quote?country=Mexico&from=USDT&to=MXN&createQuoteId=true`. `price` is fiat per 1 crypto. `quoteId` lasts 10 s in production (300 s sandbox), single-use, bound to `country`, crypto and fiat. Request it right before creating the order.
   - https://docs.velafi.com/api-reference/quote/get-user-quote-for-crypto-fiat.md
4. **Create the payout order.** `POST /v2/order/crypto_to_fiat` with `merchantId`, `country` and `fiat` of the beneficiary, `crypto`, `userPaymentId`, `fiatAmount` or `cryptoAmount` (if both, `fiatAmount` wins), unique `clientId` (max 40 chars), optional `quoteId`. Response: `data.orderId`.
   - Funded: VelaFi debits the crypto from the wallet at creation; order goes to `40` (or `10`, `11`, `31` first).
   - Underfunded: rejected with `-1131` (`Balance insufficient`), no order created.
   - Post-funded (if enabled): accepted in `32`; Get Order returns `orderExpireTimestamp` (Unix **seconds**). VelaFi checks the balance every minute, applies it to waiting orders oldest first, and moves a covered order to `40` (or `31`). Deadline passes: `70`.
   - https://docs.velafi.com/api-reference/order/create-a-crypto-to-fiat-order.md
5. **Track the payout.** Handle `ORDER_WEBHOOK` (`orderType` `SELL`) and poll `GET /v2/order/detail?orderType=crypto_to_fiat&clientId=...`. `60` = beneficiary paid. `70` / `72` = released; read `failCode` / `failReason` (often empty: treat empty as unknown, not success). `traceNumber` is the central bank reference when the rail returns one. In `50`, the order completes on its own on automated channels, or call `POST /v2/order/confirm` (`orderType=crypto_to_fiat`). Read `references/statuses-and-failures.md`.
6. **Risk review / documents.** In `11` or `31`, upload with `POST /v2/order/invoice` (multipart, up to 5 files, 5 MB each, jpg/jpeg/png/pdf). `11` moves to `12`; `31` moves to `40`.
   - https://docs.velafi.com/api-reference/order/upload-invoice-documents-for-a-specific-order.md
7. **Reconcile.** Scheduled job re-reads every payout open on your side with Get Order; `GET /v2/orders?orderType=crypto_to_fiat` with a time range for totals; deposit history and balance for the wallet. Flag orders stuck in `40` or `50` beyond the rail's normal time.

### Retries and idempotency

- Reused `clientId` is rejected with `-1174`; the original order is not returned. Look it up by `clientId`.
- On timeout or outcome-unknown errors (`-1001`, `-1006`, `-1007`, `30012`): look up by `clientId` first; retry with the same `clientId` and a new quote only if nothing is found.
- Create a **replacement** payout only after the original is final (`70` or `72`). Never create a second order while the first is open.

## Rules

- Never hardcode, log or commit the API key, secret or tokens; use env vars or a secrets manager; add `.env*` to `.gitignore`.
- All VelaFi calls are server-side only.
- Default to the sandbox. Get explicit developer confirmation before any production call or money movement.
- Never tell a user or mark a payout paid before `orderStatus` `60` is confirmed (webhook or Get Order).
- Only use beneficiaries in `status` `1`, with the same `merchantId`, currency and channel as the order. Register once and reuse; never create duplicate beneficiaries.
- Treat `60` as possibly not final: a returned payout moves a completed order to `73`/`72` and the crypto goes back to the wallet. Handle `72` after `60`.
- Deduplicate `ORDER_WEBHOOK` on `orderId` + `orderStatus`; it is only sent for API-created orders, never sends `71`/`73`, and sends `80`/`81` as `70`.
- Read `orderStatus` with `orderType` (ramp and global payment codes differ).
- Do not resubmit `80`/`81` orders unchanged. For orders stuck in `40`, contact VelaFi support with the `orderId`.
- CPN is payout only. Do not offer CPN for collections or `fiat_to_crypto`.

## Verify

- Sandbox: `https://api-test.velafi.com`. **Webhooks are not sent**: poll Get Order.
- Fund a test wallet with `POST /v2/platform/test/crypto/deposit?merchantId=...&crypto=USDT&amount=500` (USDT or USDC only). https://docs.velafi.com/docs/sandbox#sandbox-testing-tools
- Some payment method IDs differ in the sandbox (for example CBU/CVU Momentum `18` instead of `63`). https://docs.velafi.com/docs/payment-methods#sandbox-vs-production-ids
- Bounced payouts cannot be simulated: test `70` and `72` handling with recorded payloads.
- Check the `-1131`, `-1174`, timeout and `72`-after-`60` paths, and that the webhook handler returns HTTP 2xx with exactly `{"callbackStatus":"SUCCESS"}`.
- Before production run `velafi-go-live-check` and https://docs.velafi.com/docs/use-cases/payouts-funded-by-stablecoins#go-live-checklist

## Reference links

- `references/statuses-and-failures.md`: status table and failure handling.
- `references/cpn-payouts.md`: USD, EUR, HKD, SGD, NGN payouts through Circle Payment Network.
- Off-Ramp guide: https://docs.velafi.com/docs/guides/off-ramp.md
- Order Statuses: https://docs.velafi.com/docs/order-statuses.md
- Get Order: https://docs.velafi.com/api-reference/order/retrieve-a-specific-order.md
- Get Beneficiaries: https://docs.velafi.com/api-reference/beneficiary/get-beneficiary.md
- Order Event: https://docs.velafi.com/api-reference/webhooks/fiat-crypto-order-message-push.md
- Error Codes: https://docs.velafi.com/docs/error-codes.md
