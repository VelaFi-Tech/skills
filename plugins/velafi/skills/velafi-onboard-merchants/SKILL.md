---
name: velafi-onboard-merchants
description: Onboard a developer's own customers (individuals or businesses) as VelaFi merchants through the API. Create the merchant and get a hosted KYC/KYB link (POST /v2/merchants), re-request expired links, poll verification status (GET /v2/merchants with status=-1), activate local currency accounts per channel (POST /v2/merchant/accounts for MXN, ARS, COP, BRL, PEN, USD, EUR), and then set up virtual accounts. Use when the developer wants to create sub-merchants, register customers or end users as merchants, generate KYC or KYB links, embed verification in an iframe, check merchant approval status, activate a CLABE, CVU, Pix or COP account for a customer, handle verifyLink, or map customer IDs to merchant IDs (MIDs).
license: Apache-2.0
---

# VelaFi: onboard your customers as merchants

## Overview

If the developer's platform moves money on behalf of its own customers, each customer becomes a **merchant** under the developer's VelaFi account, passes its own KYC (individual) or KYB (business), and gets its own **Merchant ID (MID)**. You will build:

1. Merchant creation and a stored one-to-one mapping customer ID -> `merchantId`.
2. A redirect or iframe to the hosted `kycLink`, plus link re-requests.
3. A status poller (there is no webhook for verification or activation).
4. Currency account activation per currency, including `verifyLink` handling.
5. Optionally, virtual accounts for the customer's payers.

Related skills:
- `velafi-api-setup`: authentication, token, IP whitelist, base URLs. Do this first.
- `velafi-webhooks`: webhook registration and handling. Webhooks are per VelaFi account, not per merchant; route events by `merchantId`.
- `velafi-collect-virtual-accounts`: collect pay-ins into the merchant's balance after activation.
- `velafi-payouts-from-balance`: pay out from the merchant's balance.
- `velafi-go-live-check`: run before production.

Full guide: https://docs.velafi.com/docs/use-cases/onboard-your-customers.md

```
POST /v2/merchants -> customer completes kycLink -> GET /v2/merchants (status=-1) until 2
-> POST /v2/merchant/accounts per currency -> GET /v2/merchant/accounts until 2
-> optional virtual accounts -> use merchantId on every payment call
```

## Before you start

**Ask first, then build.** Before you write or change any code, ask the developer the questions in this section and wait for their answers. Ask them together in one message. If the developer's request already answers a question, state your understanding in one line and ask them to confirm it instead of asking again. Do not assume a country, currency, channel, merchant ID, amount mode or environment. Only skip a question the developer explicitly tells you to skip, and say which default you are using.

Ask the developer:

- **Customer types**: `INDIVIDUAL`, `BUSINESS`, or both? For individuals, which KYC `flow` (`PROFESSIONALS` default, or `CONSUMERS`)?
- **Data on hand**: a unique merchant name and an email per customer; for businesses an `industryType`.
- **Return page** for the browser after the hosted flow (`callbackUrl`), and redirect vs iframe.
- **Currencies and channels** each customer needs (see `references/activation-channels.md`).
- **Language and framework**, and where customer records live.
- **Sandbox credentials available?** Default to `https://api-test.velafi.com`. Production `https://api.velafi.com` uses separate credentials.

Prerequisites: API access with IP whitelist and a token in `X-BH-TOKEN` (`velafi-api-setup`); the developer's own VelaFi account approved (merchants sit under it; see https://docs.velafi.com/docs/merchants.md).

## Workflow

### 1. Create the merchant

`POST /v2/merchants` with `merchantName` (unique under the account), `email` (not used by any VelaFi merchant), `merchantType` (`INDIVIDUAL` or `BUSINESS`), `callbackUrl`. Also send `industryType` (one of the documented values; the guide marks it required for `BUSINESS`) and `industryTypeRemark` when it is `other`. Optional: `flow` (individuals only), `languageCode` (`en` default, `es`, `pt`, `zh`), `remark`.
Doc: https://docs.velafi.com/api-reference/merchant/create-merchant.md

```json
{
  "merchantName": "Example Customer 0001",
  "email": "customer0001@example.com",
  "merchantType": "BUSINESS",
  "industryType": "e-commerce",
  "callbackUrl": "https://your-app.example.com/onboarding/done",
  "languageCode": "en"
}
```

Response `data`: `merchantId`, `kycLink`. **Store `merchantId` against the customer immediately**; the merchant exists from this point.

| Code | Cause |
|---|---|
| `-5005` | `merchantName` already exists under the account |
| `-2017` | `email` already used by a VelaFi merchant |
| `-4010` | Invalid field (`msg` names it), e.g. `merchantType`, `flow`, `email` |
| `-5064` | Account reached its maximum number of merchants; contact VelaFi |

Creating a merchant is **not idempotent**. On a timeout or an outcome-unknown error (`-1001`, `-1006`, `-1007`), do not create it again with different details: list merchants filtered by the `email` you sent (with `status=-1`) to see if it exists.

### 2. Send the customer to the verification link

Redirect the browser to `kycLink`, or embed it in an `<iframe>`. Individuals complete KYC; businesses complete KYB. Guide: https://docs.velafi.com/docs/guides/creating-merchant.md

- `callbackUrl` is a **browser redirect, not a server notification**. Reaching it only means the customer left the hosted flow, not that they were approved. Never mark a customer verified from it; always check status (step 3).
- The link is time-limited. To get a new one, call `POST /v2/merchants` again with the existing `merchantId`, the **same `merchantType`** used at creation (it selects KYC vs KYB), and `callbackUrl` (optional `languageCode`). This does not create a second merchant. It fails with `-5062` while verification is under review and `-5063` once approved.

```json
{ "merchantId": 100001, "merchantType": "BUSINESS", "callbackUrl": "https://your-app.example.com/onboarding/done", "languageCode": "en" }
```

### 3. Poll the merchant status

`GET /v2/merchants?status=-1&email=...` (or `merchantName=`, partial match). **Always pass `status=-1`**: without it the list returns only approved merchants. Read `status` and `rejectReason`.
Doc: https://docs.velafi.com/api-reference/merchant/get-a-list-of-merchants.md

| `status` | Meaning | Action |
|---|---|---|
| `4` | Incomplete: hosted flow not finished | Send a fresh link (step 2) |
| `1` | Authenticating: under review | Keep polling |
| `2` | Normal: approved | Continue to step 4 |
| `3` | Authentication failed | Show `rejectReason`; request a new link with the same `merchantId` and `merchantType` to resubmit |

There is no webhook for merchant verification. Poll at a modest interval (every few minutes while the customer is onboarding, less often after). `merchantType` in the list response is numeric (`1` INDIVIDUAL, `2` BUSINESS). The list also returns daily/monthly limits and usage.

### 4. Activate currency accounts

For each currency, `POST /v2/merchant/accounts` with `merchantId`, `fiat`, `trench` (the channel name) and the channel's `fieldList`. The request differs by merchant type:
- Individuals: https://docs.velafi.com/api-reference/merchant/activate-merchant-account-for-individual.md
- Businesses: https://docs.velafi.com/api-reference/merchant/activate-merchant-account-for-business.md
- Guide: https://docs.velafi.com/docs/guides/activating-merchant-account.md

```json
{ "merchantId": "100001", "fiat": "MXN", "trench": "CLABE - FINCO PAY", "fieldList": { "alias": "customer0001" } }
```

Trench names, `fieldList` per channel and special cases (BRL Pix - Woovi liveness and documents, Lead Bank agreement) are in `references/activation-channels.md`.

Handle the returned `status`:

| `status` | Meaning | Action |
|---|---|---|
| `0` + `verifyLink` | Business merchant: the channel needs an additional business verification | Send the business to `verifyLink`. After VelaFi approves it, the channel opens without another call |
| `1` | Pending: the provider is opening the account | Poll List Merchant Accounts |
| `2` | Active | Done |
| `3` | Failed | Read `failReason` |
| `4` + `verifyLink` | Incomplete (e.g. USD/EUR via Lead Bank needs an agreement) | Send the merchant to `verifyLink` |

Common errors: `-5073` (merchant has not passed KYC), `-5074` (already active), `-5062` (activation already pending), `-5079` (no activation permission for this channel), `-4010` (a required `fieldList` field is missing or invalid). Treat `-5074` and `-5062` as "check status", not as failures. More codes in the reference file.

### 5. Poll the currency accounts

`GET /v2/merchant/accounts?merchantId=...` until the channel shows `status` `2`. Each record returns the channel's `paymentId` (needed for virtual accounts, beneficiaries, payouts, orders), `balance`, monthly buy/sell limits and `failReason`. Closed or disabled channels are also reported as `1`, and a channel that is still pending or incomplete may not be listed yet.
Doc: https://docs.velafi.com/api-reference/merchant/get-a-list-of-merchant-accounts.md

### 6. Optional: virtual accounts

Once the channel is `2`, give each of the customer's payers its own deposit details with `POST /v2/merchant/virtual/accounts` (`merchantId`, `fiat`, `paymentId`, `alias`). Available for MXN, ARS, BRL and COP. Use the `velafi-collect-virtual-accounts` skill for the full flow.

### 7. Use the customer's MID everywhere

The `merchantId` decides whose balance, limits and accounts a call uses. Send the customer's MID, never the developer's own, on every call for that customer:

| Call | Field |
|---|---|
| `POST /v2/order/fiat_to_crypto`, `POST /v2/order/crypto_to_fiat` | `merchantId` |
| `POST /v2/order/fiat_to_fiat` | `onRampMerchantId`, `offRampMerchantId` |
| `POST /v2/merchant/claimfunds` | `merchantId` |
| `POST /v2/merchant/transfer` | `fromMerchantId`, `toMerchantId` |
| `POST /v2/payments` (beneficiaries) | `merchantId` of the merchant whose currency account it belongs to (always pass it) |
| Crypto withdrawals and deposit addresses | `merchantId` |
| Deposit details, funding records, fiat flows, balances | `merchantId` filter |

## Rules

- Never hardcode, log or commit the API key, secret or tokens. Use env vars or a secrets manager; add `.env*` to `.gitignore`.
- All VelaFi calls run server-side. Only the `kycLink` / `verifyLink` URL goes to the browser.
- Default to the sandbox; get the developer's explicit confirmation before creating merchants or activating channels in production.
- Never treat the `callbackUrl` redirect as approval. Approval is `status` `2` from `GET /v2/merchants?status=-1`; channel readiness is `status` `2` from `GET /v2/merchant/accounts`.
- Keep a one-to-one mapping customer ID <-> MID. Never let a customer-supplied value choose the MID.
- Never create a second merchant for the same customer (abandoned flow, rejection, expired link, timeout). Re-request the link with the existing `merchantId` and `merchantType`.
- Wait for `status` `2` on a channel before creating virtual accounts or sending payments on it.
- Upload documents (for example for Pix - Woovi) with Upload File and pass the returned `fileUrl`; public URLs are rejected.
- Collect only the personal data the channel requires and do not log it.
- Use only the documented public endpoints listed here.

## Verify

The sandbox comes with **pre-configured test merchants**, and no real KYC/KYB takes place there; you cannot make a reviewer approve or reject a sandbox merchant. So:

1. Test merchant creation request validation and your error handling (`-5005`, `-2017`, `-4010`).
2. Run activation, List Merchant Accounts polling, and virtual accounts against the pre-configured test merchants.
3. Unit-test your status handling against every merchant status (`1`, `2`, `3`, `4`) and every activation status (`0` to `4`), including `verifyLink` redirects.
4. Fund a test merchant with the deposit simulator to test the downstream flows: https://docs.velafi.com/docs/sandbox#sandbox-testing-tools
5. Webhooks do not fire in the sandbox (and verification/activation have none anyway).

Before production check: `merchantId` stored as soon as creation returns; polling uses `status=-1`; expired links re-requested, never duplicated; channels at `2` before use; the customer's MID on every downstream call; webhook events routed by `merchantId`; a periodic job compares customer records with both lists so nobody is stuck in an unknown state. Then run the `velafi-go-live-check` skill.

## Reference links

- Use case: https://docs.velafi.com/docs/use-cases/onboard-your-customers.md
- Create a Merchant (guide): https://docs.velafi.com/docs/guides/creating-merchant.md
- Activate a Merchant Account (guide): https://docs.velafi.com/docs/guides/activating-merchant-account.md
- Create Merchant: https://docs.velafi.com/api-reference/merchant/create-merchant.md
- List Merchants: https://docs.velafi.com/api-reference/merchant/get-a-list-of-merchants.md
- Activate Individual: https://docs.velafi.com/api-reference/merchant/activate-merchant-account-for-individual.md
- Activate Business: https://docs.velafi.com/api-reference/merchant/activate-merchant-account-for-business.md
- List Merchant Accounts: https://docs.velafi.com/api-reference/merchant/get-a-list-of-merchant-accounts.md
- Get Woovi Liveness URL: https://docs.velafi.com/api-reference/merchant/get-woovi-liveness-url.md
- Upload File: https://docs.velafi.com/api-reference/basic-configuration/upload-file.md
- Merchants model: https://docs.velafi.com/docs/merchants.md
- Error codes: https://docs.velafi.com/docs/error-codes.md
- `references/activation-channels.md`
