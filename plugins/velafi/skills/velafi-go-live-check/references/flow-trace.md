# Flow trace

The checklists confirm that the important pieces exist. The flow trace confirms that each launching flow is built correctly from the first call to the final state in the developer's own system. Run it for every flow that is launching.

## Method

1. Load the matching flow skill and take its numbered **Workflow** steps as the expected sequence. Use the step list below to name the steps in the report.
2. For each step, find where it happens in the developer's code (file:line). Follow the real call path: from the entry point (API route, job, queue consumer) through the VelaFi client to the database write. Do not stop at the first matching string.
3. For each step, check:
   - **Order.** The step runs after the steps it depends on (for example the beneficiary is saved and has `status` `1` before the payout is created; the channel shows `status: 2` before virtual accounts or payments).
   - **Request.** Endpoint and method; every required field is sent with the right type and source (IDs from the developer's own records, not constants; amounts as decimal strings or exact decimals, not floats; the right `merchantId`, `paymentId`, `country`, `fiat` and crypto). Check each field against the endpoint's API reference page (the `.md` link in the flow skill, or the docs MCP server).
   - **Response.** The code checks `code` before reading `data`, reads the fields it needs (for example `orderId`, `txId`, `userPaymentId`, `merchantId`, `fieldList`), and stores the VelaFi ID next to the developer's own ID and `clientId`.
   - **State.** Every possible status of the record maps to a state in the developer's system, including the failure and reversal statuses listed in the flow skill. Note any status that falls through, is ignored, or maps to the wrong state.
   - **Money.** The developer's ledger is credited or debited at the right status, once, and reversed when the flow says it must be (for example `72` after `60`, `WITHDRAW` status `3` or `4`, `WITHDRAW_ROLLBACK`).
4. Mark each step 🟢 PASS, 🔴 FAIL or 🟡 WARN with evidence (⚪ N/A for an optional step the developer does not use). A step that cannot be found in the code is FAIL if the flow needs it, and N/A if it is optional and the developer confirms they do not use it.

Report one table per flow:

```markdown
### Flow trace: <flow>
🔴 <n> FAIL · 🟡 <n> WARN · 🟢 <n> PASS

| # | Step | Code | Request | Response | State and money | Result |
```

Any FAIL in a flow trace is a blocking item.

## Steps per flow

Use the flow skill's Workflow for the detail behind each step.

**Collect with virtual accounts** (`velafi-collect-virtual-accounts`)
1. Create a virtual account per payer (`POST /v2/merchant/virtual/accounts`), alias mapped to one customer.
2. Get the bank details for the alias (`GET /v2/merchant/virtual/addfunds`) until `status` `2`; QR and links fetched fresh.
3. Show the payer the details.
4. Handle `FUNDING_WEBHOOK` `DEPOSIT`: attribute by `depositAlias`, credit the customer once; unmatched deposits go to review.
5. Read the balance (`GET /v2/merchant/accounts`).
6. Reconcile funding records (`type=DEPOSIT`) against stored webhooks.

**Pay out from your balance** (`velafi-payouts-from-balance`)
1. Save the beneficiary (`GET /v2/payments/templates`, `POST /v2/payments`) under the merchant that holds the balance; use it only at `status` `1`.
2. Check the balance, including the fee.
3. Create the payout (`POST /v2/merchant/claimfunds`) with a stored, unique `clientId`.
4. Track the result: `FUNDING_WEBHOOK` `WITHDRAW` `2` / `3` / `4`, or funding records by `txId` or `clientId`; release or reverse the amount on the developer's side.
5. Timeouts: look up by `clientId` before retrying with the same `clientId`.
6. Optional: transfers between merchants (`GET /v2/merchant/transfer_fee`, `POST /v2/merchant/transfer`).
7. Reconcile.

**Convert to stablecoins (on-ramp)** (`velafi-onramp`)
1. Prefunded only: fund the balance.
2. Optional: lock the rate with a quote immediately before the order.
3. Create the order (`POST /v2/order/fiat_to_crypto`) with the right `paymentId` (`70` prefunded, or the channel's), unique `clientId`, and `network` + `address` only if automatic withdrawal is enabled.
4. Pay-per-order only: show `paymentInfo`, the exact amount and a deadline; confirm manual payment methods.
5. Track to `60`, or `70` / `80` / `81`; a new order after `70`.
6. Optional: deliver the crypto (automatic or manual withdrawal).
7. Reconcile.

**Pay out funded with stablecoins (off-ramp)** (`velafi-offramp-payouts`)
1. Fund the crypto wallet (or post-funded: fund orders in `32` before `orderExpireTimestamp`).
2. Register the beneficiary and store `userPaymentId`; use it only at `status` `1`.
3. Optional: lock the rate with a quote.
4. Create the order (`POST /v2/order/crypto_to_fiat`) with `userPaymentId`, the beneficiary's `country` and `fiat`, and a unique `clientId`.
5. Track to `60`; handle `70` and `72` (including `72` after `60`); flag orders stuck in `40` or `50`.
6. Reconcile.

**Onboard your customers** (`velafi-onboard-merchants`)
1. Create the merchant (`POST /v2/merchants`) and store `merchantId` at once, one-to-one with the customer.
2. Send the customer to the verification link; re-request expired links with the existing `merchantId`.
3. Poll merchant status with `status=-1`.
4. Activate currency accounts (`POST /v2/merchant/accounts`).
5. Poll the accounts until the channel shows `status: 2`; handle `verifyLink`.
6. Optional: virtual accounts.
7. Pass the customer's MID on every downstream call and route webhook events by `merchantId`.

**Global payments** (`velafi-global-payments`)
1. Check the corridor (`GET /v2/base/fiat/symbols`) and use its `accuracy` for amounts.
2. Get payment methods per side (`GET /v2/base/fiat/payments`).
3. Register the recipient beneficiary on the off-ramp merchant; use it only at `status` `1`.
4. Optional: lock the rate (`GET /v2/user/fiat-quote`) right before the order.
5. Create the order (`POST /v2/order/fiat_to_fiat`) with on-ramp and off-ramp merchants and a unique `clientId`.
6. Show pay-in instructions while the order is in `41` (`GET /v2/order/detail` with `orderId`).
7. Upload documents in `11` or `31` (`POST /v2/order/invoice`).
8. Track to `60`; `71`, `72` and `90` are final failures.
9. Reconcile open orders by `orderId`.

**Crypto wallet** (`velafi-crypto-wallet`)
1. Read balances (`free` is spendable).
2. Show a deposit address only when `allowDeposit` is `true`, with `addressExt` when needed.
3. Credit crypto deposits only at `status` `2`, deduplicated (no deposit webhook).
4. Check quota, networks and fee (`GET /v2/assets/withdrawQuota`).
5. Whitelist the destination (`POST /v2/user/whitelistAddress`).
6. Withdraw (`POST /v2/assets/withdraw`) with a required, unique `clientId`.
7. Track to `6`, or `7` / `9`, with a timeout.
8. Optional: internal transfers (`POST /v2/assets/internalTransfer`), reconciled from their history.
9. Handle `CRYPTO_WITHDRAW_WEBHOOK` (`REFUNDED` like `FAILED`).
10. Alert on withdrawals the developer did not initiate.
