# On-ramp statuses, webhooks and failures

Source: https://docs.velafi.com/docs/order-statuses.md and https://docs.velafi.com/docs/use-cases/convert-to-stablecoins.md

## Ramp order status codes (`fiat_to_crypto`)

| Code | Name | Meaning for an on-ramp | Final |
| --- | --- | --- | --- |
| `10` | Reviewing | Under review. | No |
| `11` | Risk review | Under risk review. Upload documents with `POST /v2/order/invoice`; the order moves to `12`. | No |
| `12` | RFI documents uploaded | Waiting for a decision after documents were uploaded. | No |
| `31` | Supporting documents pending | Upload documents; the order then moves to `40`. | No |
| `40` | Pending payment | Waiting for the fiat payment (pay-per-order). | No |
| `50` | Paid | Payment step done, order not completed yet. | No |
| `60` | Completed | Crypto credited to the merchant wallet. | Yes (unless later refunded) |
| `70` | Cancelled | Cancelled. Orders that expired unpaid are also `70`. | Yes |
| `71` | Cancelling | Being cancelled; a scheduled job finishes it. | No |
| `72` | Refunded | Refund complete. | Yes |
| `73` | Refunding | Refund in progress. | No |
| `80` | Rejected | Rejected in review (also review timed out). | Yes |
| `81` | Risk review rejected | Rejected in risk review. | Yes |

A new API order normally starts in `10`, `11`, `31` or `40`. You never receive internal codes `0`, `90`, `91`, `92`: they are reported as `10`, `80`, `70`, `70`.

`GET /v2/orders` lists every order on the account, including orders not created through the API. Those can also show `20` (review rejected) or `30` (approved).

## ORDER_WEBHOOK mapping

- Sent only for orders created through the API, with `orderType` `BUY` for on-ramp.
- Statuses sent: `10`, `11`, `12`, `31`, `40`, `50`, `60`, `70`, `72`.
- Review and risk-review rejections are sent as `70` (polling shows `80` / `81`). `20`, `30`, `71`, `73` are not sent.
- `failCode` / `failReason` are present only on `70` or `72` when recorded.
- Deduplicate on `orderId` + `orderStatus`.

Payload reference: https://docs.velafi.com/api-reference/webhooks/fiat-crypto-order-message-push.md

## Other webhooks in this flow

| Event | When | Key on | Action |
| --- | --- | --- | --- |
| `FUNDING_WEBHOOK` | Pending Fund record completes: `DEPOSIT` (top-up or payer transfer), `BUY_CRYPTO` (fiat applied to an order) | `txId` + `status` | Track the fiat balance |
| `ON_RAMP_WITHDRAW_WEBHOOK` | Automatic withdrawal succeeded (`status` always `succeeded`) | `orderId` | Record `txHash`. Failures send nothing |
| `CRYPTO_WITHDRAW_WEBHOOK` | Withdrawal reached `SUCCESS`, `FAILED`, `REFUNDED` or `CANCELLED` | `withdrawId` + `status` | Mark the withdrawal final |

## Failure handling

| What you see | Likely cause | What to do |
| --- | --- | --- |
| Create rejected, insufficient balance (prefunded) | Pending Fund balance does not cover the order | Top up or lower the amount, then create again with a new `clientId` and new quote |
| Create rejected as repeated submission (`-1174`) | `clientId` already used, maybe by your own timed-out request | Look up by `clientId`; do not create again |
| Create rejected after passing `quoteId` | Quote expired, used, or for another pair | New quote. A rejected create can consume a `quoteId` |
| `-4040` "not a user of the onRamp automatic withdrawal service" | Account not enabled for automatic withdrawal | Remove `network`/`address`, withdraw manually |
| `70` on pay-per-order | No full payment within the window, or cancelled | New order, new `clientId`, new instructions to the payer |
| `80` / `81` when polling (`70` in webhook) | Rejected in review / risk review | Do not resubmit unchanged; contact VelaFi for the reason |
| Stuck in `10`, `11`, `31` | Review or documents required | Upload documents when asked |
| `ON_RAMP_WITHDRAW_WEBHOOK` never arrives | Automatic withdrawal failed or was not made | Check crypto balance and `GET /v2/assets/withdrawalOrders` with `clientId` = on-ramp `orderId`; if crypto is still in the wallet, withdraw it manually |

## Deposit matching (pay-per-order)

When a payer's transfer is credited, VelaFi applies it to open orders on the same currency account: a deposit equal to an order's amount goes to that order first, otherwise to the oldest open order. An order with a `depositAlias` is only paid by deposits to that virtual account. An order without one can be paid by any deposit on the currency account, including fiat already in the Pending Fund balance. An order is only paid when the full amount is available.

A payment that arrives after the order was cancelled is credited to the Pending Fund balance. Create a new order (paid from the balance) or pay it out with Claim Pending Funds (https://docs.velafi.com/api-reference/merchant/claim-pending-fund.md).
