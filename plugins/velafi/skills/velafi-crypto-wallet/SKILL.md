---
name: velafi-crypto-wallet
description: Integrate the VelaFi merchant crypto wallet. Read USDT/USDC/BTC balances, get deposit addresses, list crypto deposits, manage the withdrawal address whitelist, check withdrawal quota and network fees, create crypto withdrawals with a required clientId, list withdrawals, move crypto between your merchants with internal transfers, and handle CRYPTO_WITHDRAW_WEBHOOK, including alerting on withdrawals you did not initiate. Use when a developer wants to withdraw USDC to an address, send USDT on TRC20/Polygon/Solana, show a deposit address, check a wallet balance, whitelist an address, transfer crypto between merchants, or monitor wallet withdrawals.
license: Apache-2.0
---

# VelaFi crypto wallet

## Overview

Each VelaFi merchant has a custody wallet. You will build server-side code that reads balances and deposits, sends crypto out to **whitelisted** addresses, moves crypto between merchants under the same account, and watches every withdrawal through `CRYPTO_WITHDRAW_WEBHOOK`.

Sibling skills:

- `velafi-api-setup`: API key, IP whitelist, token (`X-BH-TOKEN`). Do this first.
- `velafi-webhooks`: registering `CRYPTO_WITHDRAW_WEBHOOK`, signature verification, acknowledgement.
- `velafi-onramp`: buy stablecoins with local currency (fills this wallet; can auto-withdraw).
- `velafi-offramp-payouts`: spend wallet crypto on fiat payouts.
- `velafi-go-live-check`: run before production.

Full endpoint reference for this skill: `references/endpoints.md`.

## Before you start

**Ask first, then build.** Before you write or change any code, ask the developer the questions in this section and wait for their answers. Ask them together in one message. If the developer's request already answers a question, state your understanding in one line and ask them to confirm it instead of asking again. Do not assume a country, currency, channel, merchant ID, amount mode or environment. Only skip a question the developer explicitly tells you to skip, and say which default you are using.

- API access works (`velafi-api-setup`). The IP whitelist for API keys is separate from the **withdrawal address whitelist** below.
- Know the `merchantId` of each wallet.

Ask the developer:

1. Which tokens and networks (`USDT` on `TRC20`, `USDC` on `POL`, ...)?
2. Do they need deposits, withdrawals, internal transfers, or all three?
3. Which destination addresses will receive withdrawals (they must be whitelisted first)?
4. Where should withdrawal alerts go (for withdrawals they did not start)?
5. Language and framework; sandbox credentials available?

## Workflow

Base URLs: production `https://api.velafi.com`, sandbox `https://api-test.velafi.com`. Every call sends `X-BH-TOKEN`. Default to the sandbox.

1. **Balances.** `GET /v2/assets/account/assets?merchantId=...` returns `balances[]` with `total`, `free` (spendable) and `locked`. `merchantId=0` sums all merchants under the account.
   - https://docs.velafi.com/api-reference/merchant/get-crypto-assets-balance.md
2. **Deposit address.** `GET /v2/assets/depositAddress?tokenId=USDT&chainType=TRC20&merchantId=...`. Only show the address when `allowDeposit` is `true`; include `addressExt` when `needAddressTag` is `true`; tell senders the `minQuantity`. Supported token/network pairs are in `references/endpoints.md`.
   - https://docs.velafi.com/api-reference/merchant/get-crypto-deposit-address.md
3. **Deposits.** There is no deposit webhook. Poll `GET /v2/assets/depositOrders` (filters `merchantId`, `crypto`, `txId`, `startTime`, `endTime`, `pageSize` up to 1000). `status`: `1` in progress, `2` successful, `3` failed or cancelled, `4` other. Credit your user only on `2`, deduplicated by `txId`/`orderId`.
   - https://docs.velafi.com/api-reference/crypto-wallet/get-crypto-deposit-history.md
4. **Quota and networks.** `GET /v2/assets/withdrawQuota?crypto=USDT[&chainType=TRC20]` returns `minCryptoAmount` and, per network, `chainType`, `allowWithdraw` and `fee`. Use these `chainType` values exactly.
   - https://docs.velafi.com/api-reference/crypto-wallet/get-withdrawal-quota.md
5. **Whitelist the destination.** `POST /v2/user/whitelistAddress` with `crypto`, `chainType`, `address`, optional `addressTag`, `remark`. Store `addressId`. List with `GET /v2/user/whitelistAddress`; remove with `DELETE /v2/user/whitelistAddress/{addressId}`. Entries belong to the API user and apply to every merchant under it.
   - https://docs.velafi.com/api-reference/crypto-wallet/add-whitelist-address.md
6. **Withdraw.** `POST /v2/assets/withdraw` with `merchantId`, **`clientId` (required, unique)**, `crypto`, `chainType`, `address`, optional `addressTag`, `cryptoAmount` (> 0), optional `remark`. Response `data.orderId` = the withdrawal ID (`withdrawId` in the webhook). Rejected unless an active whitelist entry matches `address`, `chainType` and `addressTag` for that `crypto`. Amount rules and VelaFi-address behaviour: `references/endpoints.md`.
   - https://docs.velafi.com/api-reference/crypto-wallet/create-crypto-withdrawal.md
7. **Track the withdrawal.** Wait for `CRYPTO_WITHDRAW_WEBHOOK` (final statuses only) and poll `GET /v2/assets/withdrawalOrders?merchantId=...&clientId=...` until `status` is `6` (successful), `7` (failed) or `9` (cancelled). `5` = in progress; `0` = other (for example awaiting sub-account approval or RFI). Apply a timeout; do not keep a user's balance locked forever.
   - https://docs.velafi.com/api-reference/crypto-wallet/get-crypto-withdrawal-history.md
8. **Internal transfer between merchants.** `POST /v2/assets/internalTransfer` with `fromMerchantId`, `toMerchantId`, `tokenId` (`USDT`, `USDC`, `BTC`, `MMXN`), `amount`, and a `clientId`. Settles instantly, no gas. A reused `clientId` from the same sender is rejected with `-4040` (`Duplicate withdrawal request`). History: `GET /v2/assets/internalTransferOrders` (two records per transfer: negative on the sender, positive on the recipient). No webhook is documented for internal transfers; reconcile them with `GET /v2/assets/internalTransferOrders`.
   - https://docs.velafi.com/api-reference/merchant/crypto-transfer.md
   - https://docs.velafi.com/api-reference/merchant/query-crypto-transfers.md
9. **Handle CRYPTO_WITHDRAW_WEBHOOK.** Register it (`velafi-webhooks`). `status`: `SUCCESS` (with `txHash`), `FAILED`, `REFUNDED` (handle like `FAILED`), `CANCELLED` (cancelled in the dashboard; the Open API has no cancel endpoint). On `FAILED`/`REFUNDED`/`CANCELLED` the amount is back in the wallet. Deduplicate on `withdrawId` + `status`. Details: `references/withdraw-webhook-and-monitoring.md`.
   - https://docs.velafi.com/api-reference/webhooks/crypto-withdraw-message-push.md
10. **Monitor for withdrawals you did not initiate.** The event also covers dashboard withdrawals (including by team members), mass payout items and automatic on-ramp withdrawals. Match every event against your own records by `withdrawId` or `clientId`, and alert on unknown withdrawals, unknown `address`, or unusual `amount`. The event arrives after the fact and cannot stop a withdrawal, so keep the whitelist short and review it regularly. Source: Security Best Practices in https://docs.velafi.com/api-reference/authentication.md

### Retries and idempotency

- Store the `clientId` before sending. On a timeout or outcome-unknown error (`-1001`, `-1006`, `-1007`, `30012`), look up `GET /v2/assets/withdrawalOrders` (or `internalTransferOrders`) by `clientId` first; retry with the **same** `clientId` only if nothing is there. A duplicate rejection on that retry means the first request went through.
- A `clientId` stays bound permanently; a new withdrawal needs a new one.

## Rules

- Never hardcode, log or commit the API key, secret or tokens; use env vars or a secrets manager; add `.env*` to `.gitignore`.
- All VelaFi calls are server-side only.
- Default to the sandbox. Get the developer's explicit confirmation before any production withdrawal, transfer or whitelist change.
- Never report a withdrawal as sent before `SUCCESS` / status `6` is confirmed. Never credit a deposit before status `2`.
- Never add a whitelist address from untrusted input without human review; the whitelist is the main control on where funds can go.
- Always send a unique `clientId` on withdrawals and internal transfers.
- Use `chainType` values from Get Withdrawal Quota; check `allowWithdraw` and `minCryptoAmount` before withdrawing.
- To move a `CRYPTO_WITHDRAW_WEBHOOK` to a new URL, **update** the existing webhook; deleting and recreating loses events still queued for the old one.
- Alert on any withdrawal event you cannot match to your own records.

## Verify

- Sandbox: `https://api-test.velafi.com`. **Webhooks are not sent**: poll withdrawal history.
- Add test funds with `POST /v2/platform/test/crypto/deposit?merchantId=...&crypto=USDT&amount=500` (`USDT` or `USDC` only; 20 requests/min). https://docs.velafi.com/docs/sandbox#sandbox-testing-tools
- Test: non-whitelisted address is rejected; duplicate `clientId` is rejected; timeout lookup path; amount below fee / minimum; internal transfer shows two records.
- Test the webhook handler with recorded `SUCCESS` and `FAILED` payloads: signature verified, HTTP 2xx with exactly `{"callbackStatus":"SUCCESS"}`, unmatched events raise an alert.
- Before production run `velafi-go-live-check` (https://docs.velafi.com/docs/use-cases/go-live-checklist.md).

## Reference links

- `references/endpoints.md`: parameters, supported tokens/networks, withdrawal amount rules.
- `references/withdraw-webhook-and-monitoring.md`: webhook payload, coverage and monitoring.
- Authentication (Security Best Practices): https://docs.velafi.com/api-reference/authentication.md
- Error Codes: https://docs.velafi.com/docs/error-codes.md
