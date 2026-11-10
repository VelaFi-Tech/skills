# Per-flow go-live checklists

Evaluate the list for every flow that is launching, in addition to the shared checklist in `SKILL.md`. The first five lists are the published checklists at the end of each use-case page. The last two have no dedicated checklist page; their items restate facts from the linked reference pages.

## Collect with virtual accounts

https://docs.velafi.com/docs/use-cases/collect-with-virtual-accounts#go-live-checklist

- [ ] The `FUNDING_WEBHOOK` endpoint verifies the signature and returns HTTP `200` with `{"callbackStatus":"SUCCESS"}` quickly, well within the 60-second timeout.
- [ ] The handler is idempotent on `eventType` + `txId` + `status` and ignores events it has already processed.
- [ ] Every payer has their own virtual account, and the alias maps to one customer in your system.
- [ ] Your ledger keeps per-payer balances; you do not expect VelaFi to hold a balance per virtual account.
- [ ] Deposits without a `depositAlias` go to a review queue.
- [ ] A scheduled job compares funding records (`type=DEPOSIT`) with stored webhooks and processes the gaps.
- [ ] QR codes and payment links are fetched fresh before they are shown.

## Pay out from your balance

https://docs.velafi.com/docs/use-cases/payouts-from-balance#go-live-checklist

- [ ] Every payout and transfer sends a unique `clientId` that you store before making the call.
- [ ] On a timeout you look up the `clientId` before retrying, and you resend with the same `clientId`.
- [ ] A failed payout is retried only with a new `clientId`, after the beneficiary details are checked.
- [ ] Beneficiaries are saved under the same merchant and channel as the balance, and only `status` `1` beneficiaries are used.
- [ ] The balance check includes the fee.
- [ ] The `FUNDING_WEBHOOK` handler handles `WITHDRAW` with status `2`, `3` and `4`, and works when `failReason` is missing.
- [ ] A scheduled job flags payouts still pending after your expected settlement time.

## Convert to stablecoins (on-ramp)

https://docs.velafi.com/docs/use-cases/convert-to-stablecoins#go-live-checklist

- [ ] Every create request sends a unique `clientId`, and timeouts are resolved by looking up the `clientId` before retrying.
- [ ] Prefunded flows check the balance and handle the insufficient-balance rejection without retrying the same request in a loop.
- [ ] Pay-per-order flows show `paymentInfo`, the exact amount and a deadline, and create a new order after `70`.
- [ ] Each payer has a virtual account (`depositAlias`) if you run pay-per-order for several payers on one currency account.
- [ ] The `ORDER_WEBHOOK` endpoint verifies the signature, returns `{"callbackStatus":"SUCCESS"}` with HTTP `2xx`, and deduplicates on `orderId` + `orderStatus`.
- [ ] A scheduled job reconciles open orders, funding records and withdrawals against the API.
- [ ] Withdrawal destinations are whitelisted, or automatic withdrawal is enabled and tested with `network` and `address`.
- [ ] Added from [Order Statuses](https://docs.velafi.com/docs/order-statuses.md): polling treats `60` as done and `70`, `80`, `81` as failed (the webhook sends `80`/`81` as `70`). Rejected orders are not resubmitted unchanged.

## Pay out funded with stablecoins (off-ramp)

https://docs.velafi.com/docs/use-cases/payouts-funded-by-stablecoins#go-live-checklist

- [ ] The wallet is funded before orders are created, or post-funded off-ramp is enabled and your system funds orders in `32` before `orderExpireTimestamp`.
- [ ] Beneficiaries are registered once, stored by `userPaymentId`, and only used when `status` is `1`.
- [ ] Every create request sends a unique `clientId`, and timeouts are resolved by looking up the `clientId` before retrying.
- [ ] The `ORDER_WEBHOOK` endpoint verifies the signature, returns `{"callbackStatus":"SUCCESS"}` with HTTP `2xx`, and deduplicates on `orderId` + `orderStatus`.
- [ ] `70` and `72` (including `72` after `60`) release or reverse the payout on your side, and a replacement is only created after the original is final.
- [ ] Orders stuck in `40` or `50` are flagged and escalated with the `orderId`.
- [ ] For USD and EUR, the CPN account is activated and CPN beneficiaries include the required compliance fields.
- [ ] Added from [Order Statuses](https://docs.velafi.com/docs/order-statuses.md): polling treats `80` and `81` as failed final states.

## Onboard your customers (sub-merchants)

https://docs.velafi.com/docs/use-cases/onboard-your-customers#go-live-checklist

- [ ] Store `merchantId` as soon as `POST /v2/merchants` returns, and map it one-to-one to your customer.
- [ ] Handle every merchant status (`1`, `2`, `3`, `4`) and every activation status (`0` to `4`), including `verifyLink` redirects.
- [ ] Poll with `status=-1`, so merchants that are not approved yet are not missing from your results.
- [ ] Re-request expired links with the existing `merchantId` and `merchantType` instead of creating a duplicate merchant.
- [ ] Wait for the channel to show `status: 2` before you create virtual accounts or send payments for that currency.
- [ ] Pass the customer's MID on every downstream call, and route webhook events by `merchantId`.

## Global payments (fiat-to-fiat)

Sources: https://docs.velafi.com/docs/guides/global-payments.md, https://docs.velafi.com/docs/order-statuses.md, https://docs.velafi.com/api-reference/webhooks/fiat-fiat-order-message-push.md

- [ ] `POST /v2/order/fiat_to_fiat` sends a unique `clientId` (max 40 chars); a repeated one is rejected with `-1174`. Outcome-unknown responses are resolved with `GET /v2/orders?orderType=fiat_to_fiat` for the time window, matching `clientId`.
- [ ] Status code handling uses the global payment table, not the ramp table: `60` completed; `71` pay-in cancelled (including review rejection or timeout), `72` payout cancelled and `90` risk review rejected are final failures.
- [ ] `GLOBAL_PAYMENT_WEBHOOK` deduplicates on `orderId` + `orderStatus` and tolerates skipped statuses.

## Crypto withdrawals from merchant wallets

Sources: https://docs.velafi.com/api-reference/crypto-wallet/create-crypto-withdrawal.md, https://docs.velafi.com/api-reference/webhooks/crypto-withdraw-message-push.md

- [ ] `POST /v2/assets/withdraw` always sends a unique `clientId` (required); a duplicate is rejected with `Duplicate withdrawal request`.
- [ ] Final status comes from `CRYPTO_WITHDRAW_WEBHOOK` (dedupe `withdrawId` + `status`) or `GET /v2/assets/withdrawalOrders` (`6` success, `7` failed, `9` cancelled); `REFUNDED` is handled like `FAILED`.
- [ ] Pending withdrawals are reconciled against the history with a timeout; balances are not locked on your side indefinitely.
- [ ] Each event is matched to your own records; withdrawals you did not initiate, unknown addresses or unusual amounts raise an alert.
- [ ] The withdrawal address whitelist is short and reviewed.
- [ ] URL changes for `CRYPTO_WITHDRAW_WEBHOOK` use `PUT /v2/webhook/{webhookId}`, not delete-and-recreate.
