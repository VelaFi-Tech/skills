---
name: velafi-payouts-from-balance
description: Build local-currency payouts from a VelaFi merchant's fiat (Pending Fund) balance with POST /v2/merchant/claimfunds, saved beneficiaries (POST /v2/payments), FUNDING_WEBHOOK WITHDRAW tracking and clientId-safe retries, plus internal transfers between merchants with POST /v2/merchant/transfer and the transfer fee. Use when the developer wants to pay out to a bank account, CLABE, CVU, Pix key or Colombian/Peruvian account from the balance, send MXN, ARS, COP, BRL or PEN payouts, withdraw or claim pending funds, add beneficiaries, handle failed or refunded payouts, or move balance from one merchant to another.
license: Apache-2.0
---

# VelaFi: pay out local currency from the balance

## Overview

You will build, in the developer's backend:

1. Beneficiary management: get the channel template, save the destination under the merchant that holds the balance (`POST /v2/payments`).
2. Payout creation: `POST /v2/merchant/claimfunds` with a unique `clientId`.
3. Result tracking: `FUNDING_WEBHOOK` with `type` `WITHDRAW` (statuses `2`, `3`, `4`), with funding records as the fallback.
4. Optional: move balance between the developer's merchants with `POST /v2/merchant/transfer`.
5. A reconciliation job.

The balance usually comes from deposits; see `velafi-collect-virtual-accounts`.

Related skills:
- `velafi-api-setup`: authentication, token, IP whitelist, base URLs. Do this first.
- `velafi-webhooks`: registering `FUNDING_WEBHOOK`, signature check, the acknowledgement body.
- `velafi-onboard-merchants`: create merchants and activate their currency accounts.
- `velafi-offramp-payouts`: payouts funded with USDT/USDC (crypto_to_fiat orders) instead of a fiat balance.
- `velafi-go-live-check`: run before production.

Full guide: https://docs.velafi.com/docs/use-cases/payouts-from-balance.md

## Before you start

Ask the developer:

- **Currency and channel** the balance sits on (see the table). The payout goes out on that same channel.
- **Which merchant** holds the balance (their own MID or a customer's MID).
- **Where beneficiaries come from** (their users enter bank details, or a fixed list) and how they will store `userPaymentId`.
- **Language and framework**, and where payout records live in their system.
- **Sandbox credentials available?** Default to `https://api-test.velafi.com`. Production `https://api.velafi.com` uses separate credentials.

Prerequisites:
- API key, whitelisted server IP, token in `X-BH-TOKEN` (`velafi-api-setup`).
- A verified merchant with an **active** currency account (`status` `2` in `GET /v2/merchant/accounts`) on a channel that supports payouts.
- Balance on that currency account from deposits on the same channel.
- A registered `FUNDING_WEBHOOK` endpoint (`velafi-webhooks`).

### Channels that support payouts from the balance

| Currency | Channel | Beneficiary `paymentId` |
|---|---|---|
| MXN | SPEI (Finco Pay) | `105` |
| MXN | SPEI (Tesored) | `72` |
| ARS | CBU/CVU (Momentum) | `63` |
| COP | COP Account (Cobre) | `68`, `69` |
| BRL | Pix (Genial) | `90` |
| BRL | Pix - Woovi (Avenia) | `92` |
| PEN | Bank Transfer | `95` (minimum payout 10 PEN) |

Sandbox payment IDs can differ (for example ARS Momentum `63` is `18` in the sandbox). Read `paymentId` from `GET /v2/merchant/accounts` instead of hardcoding it.

Three rules apply to every payout:
1. **Same channel.** The payout goes out through the channel of the currency account holding the balance. Only balance that came in through that channel (or through VelaFi Pending Fund) can be paid out on it.
2. **Same merchant currency account.** The beneficiary must be saved under the same merchant, for the same currency and channel. A beneficiary under another merchant, or for another channel (for example a Tesored beneficiary against a Finco Pay balance), is rejected.
3. **Amount plus fee.** The balance must cover `amount` plus the payout fee.

## Workflow

### 1. Save the beneficiary

1. `GET /v2/payments/templates?paymentId=...` returns the `fieldJson` keys for the channel. The response at runtime is authoritative; use the field's `indexCode` as the key when it is non-empty, otherwise the `title`. Dropdown fields take one of the option `code`s; anything else is `-4010`.
   Doc: https://docs.velafi.com/api-reference/beneficiary/get-payment-templates.md
2. `POST /v2/payments` with `merchantId` (always send it: without it the request fails with `-4010` for manual and `-5070` for automatic methods), `paymentId`, `country` (full name, e.g. `Mexico`), `fiat`, `realName`, `fieldJson`, optional `remark`.
   Doc: https://docs.velafi.com/api-reference/beneficiary/add-beneficiary.md

```json
{
  "merchantId": 100001,
  "paymentId": 105,
  "country": "Mexico",
  "fiat": "MXN",
  "realName": "Example Beneficiary",
  "fieldJson": {
    "Account Type": "clabe",
    "Account Number": "000000000000000001",
    "Beneficiary Name": "Example Beneficiary",
    "Bank Code": ""
  }
}
```

Response `data`: `id` (the `userPaymentId`), `status` (`1` valid, `2` authenticating, `3` failed), `failReason`, `sameAccountNumberId`.
- Pay out only to `status` `1` beneficiaries.
- `status` `3` with `sameAccountNumberId`: the account number is already saved under this merchant and `paymentId`. Use that ID; do not create another record.

Template notes per channel are in `references/beneficiaries.md`. Guide: https://docs.velafi.com/docs/guides/managing-beneficiaries.md

### 2. Check the balance

`GET /v2/merchant/accounts?merchantId=...&fiat=...`: `balance` of the record for that channel. Leave room for the fee.

### 3. Create the payout

`POST /v2/merchant/claimfunds` with `merchantId`, `fiat` (`MXN`, `ARS`, `COP`, `BRL`, `PEN`; must match the beneficiary), `amount`, `userPaymentId`, and **always** your own unique `clientId`.
Doc: https://docs.velafi.com/api-reference/merchant/claim-pending-fund.md

```json
{ "merchantId": 100001, "clientId": "payout-0001", "fiat": "MXN", "amount": 1000, "userPaymentId": 456 }
```

- Persist the `clientId` in your database **before** making the call.
- Response: `txId`, `amount` (what the beneficiary receives), `fee`, `totalAmount` (`amount` + `fee`, debited from the balance), `createTime`. Amounts are rounded down to the currency's precision.
- HTTP 200 means **accepted**, not paid. The payout is pending until the webhook or funding record says otherwise.
- If `claimfunds` returns an error, no record was created and nothing was debited. Error table: `references/payout-errors.md`.

### 4. Track the result

| Status | Meaning | Balance |
|---|---|---|
| `1` pending | Accepted and being sent (a new record can briefly show `0`; `status=1` filter returns both) | `totalAmount` held (already debited) |
| `2` completed | Channel reported it paid | Stays debited |
| `3` canceled | Failed or rejected before completion | `totalAmount`, fee included, credited back (`WITHDRAW_ROLLBACK` in fiat flows) |
| `4` refunded | A completed payout was returned and reversed | `totalAmount` credited back (`WITHDRAW_ROLLBACK`) |

`FUNDING_WEBHOOK` is sent for `2`, `3`, `4` (not pending), with `type` `WITHDRAW`. In the handler (signature check and acknowledgement per `velafi-webhooks`):
- Match by `clientId` or `txId`. `totalAmount` is negative for withdrawals.
- Idempotent on `eventType` + `txId` + `status`. A payout can move from `2` to `4` later; handle a refund after a completion.
- `failCode` / `failReason` appear only for some canceled payouts. Never depend on them.
- Keep `bankOrderId` (provider reference) for support requests.
- Return HTTP 200 with exactly `{"callbackStatus":"SUCCESS"}` within 60 seconds.

No webhook? Read `GET /v2/merchant/funding/records?txId=...` or `?clientId=...`.
Doc: https://docs.velafi.com/api-reference/merchant/retrieve-funding-records.md

### 5. Timeouts and retries (clientId)

1. On a timeout or network error, do **not** create a new `clientId`. Look up `GET /v2/merchant/funding/records?clientId=...`.
2. Record exists: the payout was created; follow its status.
3. No record: resend the same request with the same `clientId`. If the first did go through, you get `-1174` (not the original payout, and no second payout).
4. `-1146` (another payout or transfer for the same merchant and currency in progress): wait briefly and retry with the same `clientId`.

A `clientId` can never be reused, even after a failed payout. To retry a status `3` payout: check and correct the beneficiary, then create a new payout with a **new** `clientId` (for example `payout-0001-r1`) linked to the original. Never retry automatically in a loop; if the same beneficiary keeps failing without a `failReason`, contact VelaFi support with `txId` and `bankOrderId`.

### 6. Optional: move balance between merchants

Both merchants must belong to the developer's account and have an active currency account for the same `fiat` and `paymentId`.

1. Fee: `GET /v2/merchant/transfer_fee?fiat=MXN` returns `feeType` (`0` fixed amount, `1` fraction of the amount, `0.01` = 1%) and `fee`. The `fee` returned by the transfer itself is what is actually charged.
   Doc: https://docs.velafi.com/api-reference/merchant/get-transfer-pending-funds-fee.md
2. `POST /v2/merchant/transfer` with `clientId`, `fromMerchantId`, `toMerchantId`, `fiat`, `paymentId`, `fiatAmount`. Documented `paymentId` values: `105` or `72` (MXN), `63` (ARS), `68` (COP), `90` (BRL), `95` (PEN).
   Doc: https://docs.velafi.com/api-reference/merchant/transfer-pending-funds.md

```json
{ "clientId": "transfer-0001", "fromMerchantId": 100001, "toMerchantId": 100002, "fiat": "MXN", "paymentId": 105, "fiatAmount": 1000 }
```

- The sender needs `fiatAmount` + fee available from that channel.
- Completes in the same call: `fromId` (`TRANSFER_OUT` record on the sender) and `toId` (`TRANSFER_IN` on the recipient), both status `2`. The recipient gets `fiatAmount`; the sender is debited `totalFiatAmount`.
- Same `clientId` rule: any `clientId` already used by a funding record under the account returns `-1174`. Always send one. `TRANSFER_OUT` carries your `clientId`; `TRANSFER_IN` carries `TRANSFER_IN_` + your `clientId`. Look both up by `txId` (`fromId`, `toId`).
- Transfers between merchants are **not** sent as `FUNDING_WEBHOOK` events.

### 7. Reconcile

- `GET /v2/merchant/funding/records` with `type=WITHDRAW` (or `TRANSFER_OUT`, `TRANSFER_IN`), `fiat`, time window: every payout you created must reach `2`, `3` or `4`. Flag payouts still pending after your expected settlement time.
- `GET /v2/merchant/fiat/flows`: `WITHDRAW` at creation, `WITHDRAW_ROLLBACK` when credited back, `TRANSFER_OUT` / `TRANSFER_IN`; `total` is the running balance.
  Doc: https://docs.velafi.com/api-reference/merchant/get-a-list-merchant-fiat-flow.md

## Rules

- Never hardcode, log or commit the API key, secret or tokens. Use env vars or a secrets manager; add `.env*` to `.gitignore`.
- All VelaFi calls run server-side only.
- This flow moves money. Default to the sandbox, and get the developer's explicit confirmation before any call against production.
- Never show a payout as paid until a `FUNDING_WEBHOOK` or funding record has `status` `2`. A 200 from `claimfunds` only means accepted.
- Every payout and transfer sends a unique `clientId`, stored before the call. Retry a timeout with the same `clientId`; retry a failed payout only with a new one.
- Never let an end user pick the `merchantId` or another user's `userPaymentId`; resolve both server-side.
- Use only `status` `1` beneficiaries saved under the same merchant and channel as the balance.
- Include the fee in the balance check.
- Use only the documented public endpoints listed here.

## Verify

In the sandbox (`https://api-test.velafi.com`):

1. Fund a test merchant with the fiat deposit simulator: `POST /v2/platform/test/deposit?merchantId=...&fiat=...&fiatAmount=...&paymentId=...` (https://docs.velafi.com/docs/sandbox#sandbox-testing-tools).
2. Save a beneficiary, call `claimfunds` and `transfer` against that balance. Exercise validation, the error codes in `references/payout-errors.md`, and the `clientId` timeout logic (send the same `clientId` twice and expect `-1174`).
3. **Webhooks do not fire in the sandbox.** Follow each payout with List Funding Records, and post sample `WITHDRAW` payloads to your handler yourself, including `3` (with and without `failReason`), `4` after `2`, and duplicates.

Before production check: unique stored `clientId`s; lookup-before-retry; new `clientId` only for failed payouts; beneficiaries on the same merchant and channel; fee in the balance check; `WITHDRAW` `2`/`3`/`4` handled; a job flags stale pending payouts. Then run the `velafi-go-live-check` skill.

## Reference links

- Use case: https://docs.velafi.com/docs/use-cases/payouts-from-balance.md
- Claim Pending Funds: https://docs.velafi.com/api-reference/merchant/claim-pending-fund.md
- Transfer Pending Funds: https://docs.velafi.com/api-reference/merchant/transfer-pending-funds.md
- Transfer Fee: https://docs.velafi.com/api-reference/merchant/get-transfer-pending-funds-fee.md
- Manage Beneficiaries: https://docs.velafi.com/docs/guides/managing-beneficiaries.md
- Add Beneficiary: https://docs.velafi.com/api-reference/beneficiary/add-beneficiary.md
- Payment Templates: https://docs.velafi.com/api-reference/beneficiary/get-payment-templates.md
- List Beneficiaries: https://docs.velafi.com/api-reference/beneficiary/get-beneficiary.md
- List Funding Records: https://docs.velafi.com/api-reference/merchant/retrieve-funding-records.md
- List Fiat Flows: https://docs.velafi.com/api-reference/merchant/get-a-list-merchant-fiat-flow.md
- Funding Event (webhook): https://docs.velafi.com/api-reference/webhooks/funding-records-message-push.md
- Error codes: https://docs.velafi.com/docs/error-codes.md
- `references/payout-errors.md`, `references/beneficiaries.md`
