---
name: velafi-collect-virtual-accounts
description: Build local-currency collections with VelaFi virtual accounts. Each payer gets their own CLABE, CVU, Pix key/QR, Bre-B key or COP payment link, deposits land in the merchant's fiat (Pending Fund) balance, and every FUNDING_WEBHOOK DEPOSIT is matched to the payer by depositAlias. Use when the developer wants to collect payments in Mexico, Argentina, Colombia or Brazil (MXN, ARS, COP, BRL), give a CLABE or CVU per customer, accept SPEI, CVU, Pix or Bre-B pay-ins, show bank details to payers, attribute deposits to customers, or reconcile deposits with funding records and fiat flows.
license: Apache-2.0
---

# VelaFi: collect local payments with virtual accounts

## Overview

You will build a pay-in flow in the developer's backend:

1. Create one virtual account per payer (`POST /v2/merchant/virtual/accounts`) with an `alias` that is the developer's own customer ID.
2. Fetch that alias's bank details (`GET /v2/merchant/virtual/addfunds`) and show them to the payer.
3. Receive `FUNDING_WEBHOOK` events with `type` `DEPOSIT` and credit the payer found by `depositAlias` in the developer's ledger.
4. Reconcile on a schedule with funding records and fiat flows.

A virtual account is for **attribution only**. It has no balance of its own. Every deposit on any virtual account is credited to the single balance of the merchant's currency account. Per-payer balances belong in the developer's ledger, keyed by `depositAlias`.

Use a different skill for related work:
- `velafi-api-setup`: authentication, token, IP whitelist, base URLs. Do this first.
- `velafi-webhooks`: registering `FUNDING_WEBHOOK`, signature check, the acknowledgement body. This skill builds on it.
- `velafi-onboard-merchants`: create the merchant and activate the currency account that virtual accounts need.
- `velafi-payouts-from-balance`: spend the collected balance (payouts to bank accounts, transfers between merchants).
- `velafi-onramp`: buy USDT/USDC with the collected balance.
- `velafi-go-live-check`: run before production.

Full guide: https://docs.velafi.com/docs/use-cases/collect-with-virtual-accounts.md

## Before you start

**Ask first, then build.** Before you write or change any code, ask the developer the questions in this section and wait for their answers. If you have a tool for asking the developer multiple-choice questions, use it for questions with a few clear choices, such as environment, corridor, amount mode or funding crypto, and ask them in rounds if there are more than the tool takes at once. Ask open questions, such as merchant IDs, IP addresses or file paths, as text. Without such a tool, ask all the questions together in one message. If the developer's request already answers a question, state your understanding in one line and ask them to confirm it instead of asking again. Do not assume a country, currency, channel, merchant ID, amount mode or environment. Only skip a question the developer explicitly tells you to skip, and say which default you are using.

Confirm these with the developer before writing code:

- **Country, currency and channel.** Which of the supported channels below? (MXN Finco Pay or Tesored, ARS Momentum, COP Automatic ACH or Bre-B, BRL Genial or Woovi.)
- **One account or one per payer?** If they only fund their own balance or have few payers, the merchant's main account (`GET /v2/merchant/addfunds`) may be enough; payers are then identified only by the optional payer fields in the webhook. Use virtual accounts when every payment must be attributed to a customer.
- **Which merchant ID?** Their own merchant, or one MID per customer (see `velafi-onboard-merchants`).
- **Language and framework** of their backend, and where their ledger lives.
- **Sandbox credentials available?** Default to the sandbox (`https://api-test.velafi.com`). Production is `https://api.velafi.com` with separate credentials.

Prerequisites (check each one):
- API key, server IP on the whitelist, and a token in `X-BH-TOKEN` (see `velafi-api-setup`).
- A verified merchant.
- An **active** currency account for that currency and channel: `status` `2` in `GET /v2/merchant/accounts` (https://docs.velafi.com/api-reference/merchant/get-a-list-of-merchant-accounts.md). Read the channel's `paymentId` from that record instead of hardcoding it; sandbox IDs can differ (for example, ARS Momentum `63` is `18` in the sandbox).
- A registered `FUNDING_WEBHOOK` endpoint (see `velafi-webhooks`).

### Channels that support virtual accounts

| Currency | `paymentId` | Channel | Alias rule |
|---|---|---|---|
| MXN | `105` | SPEI (Finco Pay) | Letters and digits, up to 64 characters |
| MXN | `72` | SPEI (Tesored) | Letters and digits, up to 64 characters |
| ARS | `63` | CBU/CVU (Momentum) | Letters and digits, up to 64 characters |
| COP | `68` | Automatic ACH (payment link) | 6 to 21 uppercase letters or digits |
| COP | `69` | Bre-B | 6 to 21 uppercase letters or digits |
| BRL | `90` | Pix (Genial) | Letters and digits, up to 64 characters |
| BRL | `92` | Pix - Woovi (Avenia) | Letters and digits, up to 64 characters |

`default`, in any letter case, is reserved. A currency account on another channel returns `-5084` (this currency does not support multiple virtual accounts). The `fieldList` keys per channel and what the payer does are in `references/channels-and-fieldlist.md`.

## Workflow

### 1. Create a virtual account per payer

`POST /v2/merchant/virtual/accounts` with `merchantId`, `fiat`, `paymentId`, `alias`.
Doc: https://docs.velafi.com/api-reference/merchant/create-multiple-virtual-account.md

```json
{ "merchantId": 100001, "fiat": "MXN", "paymentId": 105, "alias": "CUST0001" }
```

- Use a stable ID from the developer's system as `alias` (for COP, normalize it to 6 to 21 uppercase letters or digits). The alias is permanent.
- Response `data.status`: `1` pending, `2` active, `3` failed. ARS (`63`) returns `2` at once; other rails return `1` while the channel sets up the account.
- Same alias again: `-5085` while pending, `-5086` once active. Treat these as "already exists" and go to step 2; do not invent a new alias.
- `-5079`: the account is not enabled for that currency and channel. `-5071`: the merchant's currency account on that channel is not active. Check the merchant account before retrying.

### 2. Get the bank details for the alias

Poll `GET /v2/merchant/virtual/addfunds` with `merchantId`, `fiat`, `paymentId`, `depositAlias` until the record's `status` is `2`, then read `fieldList`.
Doc: https://docs.velafi.com/api-reference/merchant/get-multiple-virtual-account.md

- The response is paged: `data.record[]`. `pageSize` defaults to 10, values above 100 are capped at 100.
- Store the details against the payer. QR image links in `fieldList` expire one hour after the response, so fetch a fresh one each time you show a QR. Payment links should also be fetched fresh before showing.
- For COP Bre-B (`69`), listing works only after the merchant's Bre-B key exists.
- To fund the merchant's main account instead: `GET /v2/merchant/addfunds` (https://docs.velafi.com/api-reference/merchant/get-pending-fund-account.md).

### 3. Show the payer what to do

Render the instructions for the rail (CLABE for SPEI, CVU for ARS, payment link for COP ACH, Bre-B key, Pix key/QR/copy-and-paste). See `references/channels-and-fieldlist.md`.

### 4. Handle the deposit webhook

Deposits create a funding record of type `DEPOSIT` with status `2` and send a `FUNDING_WEBHOOK` (all values are strings). Use the `velafi-webhooks` skill for signature verification and the acknowledgement. In the handler:

- Verify the `signature` header over the raw body, store the event, and return HTTP 200 with exactly `{"callbackStatus":"SUCCESS"}` within 60 seconds. Acknowledge first, process asynchronously.
- Route by `type`: the same webhook carries `DEPOSIT`, `WITHDRAW` and `BUY_CRYPTO`. Transfers between merchants are not sent.
- `status`: `2` completed, `3` canceled, `4` refunded. Pending records are not sent.
- Idempotency key: `eventType` + `txId` + `status`.
- Credit the payer identified by `depositAlias`. Book `amount` (net) and `fee`; `totalAmount` is the total.
- `payerName`, `payerAccount`, `taxId`, `cardNo` are optional (sent only when the rail provides them).
- `bankWebhookInfo` is a JSON string with provider details (for example the SPEI `tracking_id` or the ARS `idCoelsa`).
- No `depositAlias` (a payment to the main account details, or a rail that does not report it): put the deposit in a manual review queue.

Field list: https://docs.velafi.com/api-reference/webhooks/funding-records-message-push.md

### 5. Check the balance

`GET /v2/merchant/accounts?merchantId=...&fiat=...`: the `balance` of the record for that currency and channel is what is available for payouts, transfers and on-ramp orders.

### 6. Reconcile on a schedule

Webhooks get 3 delivery attempts and are never resent; the Open API has no redelivery endpoint. Build a scheduled job:

- `GET /v2/merchant/funding/records` with `type=DEPOSIT`, `fiat`, `startTime`/`endTime` (ms; the window applies to completion time). Process every status `2` record you have not stored. `webhookInfo` holds the same provider details as `bankWebhookInfo`, including `depositAlias`. Default 100 per page, up to 20,000 with `pageSize`; page with `currentPage`.
  Doc: https://docs.velafi.com/api-reference/merchant/retrieve-funding-records.md
- `GET /v2/merchant/fiat/flows` for line-by-line balance history (`changed`, running `total`, `txId`), up to 1,000 per page. Use it to prove the balance equals the sum of movements.
  Doc: https://docs.velafi.com/api-reference/merchant/get-a-list-merchant-fiat-flow.md

## Rules

- Never hardcode, log or commit the API key, secret or tokens. Read them from env vars or a secrets manager; add `.env*` to `.gitignore`.
- All VelaFi calls run server-side. Never call VelaFi from the browser or a mobile app; the frontend only receives the bank details to display.
- Default to the sandbox. Get the developer's explicit confirmation before running anything against production.
- Never mark a deposit as received from the UI, a redirect or the payer's claim. Credit only on a verified `FUNDING_WEBHOOK` with `status` `2`, or a funding record with `status` `2`.
- One alias maps to exactly one customer. Never let a payer choose or change their alias.
- Do not expect VelaFi to hold a per-virtual-account balance; keep per-payer balances in the developer's ledger.
- Handle duplicates and out-of-order events; read the funding record when you need the latest state.
- Handle a later `4` (refunded) or `3` (canceled) for a record you already processed.
- Respect the alias rules; COP aliases must be 6 to 21 uppercase letters or digits.
- Use only the documented public endpoints listed here.

## Verify

In the sandbox (`https://api-test.velafi.com`, sandbox credentials):

1. Create a virtual account for a pre-configured test merchant and list it until `status` is `2`.
2. Credit a test deposit with the fiat deposit simulator: `POST /v2/platform/test/deposit?merchantId=...&fiat=...&fiatAmount=...&paymentId=...&depositAlias=...` (query parameters, `X-BH-TOKEN`, 20 requests per minute). Doc: https://docs.velafi.com/docs/sandbox#sandbox-testing-tools
3. **Webhooks do not fire in the sandbox.** Confirm the deposit with `GET /v2/merchant/funding/records`, and test the handler by posting sample `FUNDING_WEBHOOK` payloads to it yourself (including a duplicate, a `3`, a `4`, and one without `depositAlias`).
4. The simulator only produces successful deposits; it cannot produce failed or returned ones.
5. Run the reconciliation job against the sandbox records.

Before production, check:
- The webhook verifies signatures and returns `{"callbackStatus":"SUCCESS"}` quickly.
- The handler is idempotent on `eventType` + `txId` + `status`.
- Every payer has their own virtual account; deposits without `depositAlias` go to review.
- A scheduled job compares `DEPOSIT` funding records with stored webhooks.
- QR codes and payment links are fetched fresh before showing.

Then run the `velafi-go-live-check` skill.

## Reference links

- Use case: https://docs.velafi.com/docs/use-cases/collect-with-virtual-accounts.md
- Create Virtual Accounts: https://docs.velafi.com/api-reference/merchant/create-multiple-virtual-account.md
- List Virtual Accounts: https://docs.velafi.com/api-reference/merchant/get-multiple-virtual-account.md
- Get Pending Fund Account (and `fieldList` keys): https://docs.velafi.com/api-reference/merchant/get-pending-fund-account.md
- List Merchant Accounts: https://docs.velafi.com/api-reference/merchant/get-a-list-of-merchant-accounts.md
- List Funding Records: https://docs.velafi.com/api-reference/merchant/retrieve-funding-records.md
- List Fiat Flows: https://docs.velafi.com/api-reference/merchant/get-a-list-merchant-fiat-flow.md
- Funding Event (webhook): https://docs.velafi.com/api-reference/webhooks/funding-records-message-push.md
- Webhook Setup: https://docs.velafi.com/api-reference/webhooks/webhook-setup.md
- Sandbox: https://docs.velafi.com/docs/sandbox.md
- Error codes: https://docs.velafi.com/docs/error-codes.md
- Channel details: `references/channels-and-fieldlist.md`
