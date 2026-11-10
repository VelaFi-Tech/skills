# Off-ramp payout statuses and failures

Source: https://docs.velafi.com/docs/order-statuses.md and https://docs.velafi.com/docs/use-cases/payouts-funded-by-stablecoins.md

## Status codes for a `crypto_to_fiat` payout

| Code | Meaning for a payout | Final |
| --- | --- | --- |
| `10` | Reviewing | No |
| `11` | Risk review. Upload documents; moves to `12` | No |
| `12` | RFI documents uploaded, waiting for a decision | No |
| `31` | Supporting documents pending. Upload; moves to `40` | No |
| `32` | Post-funded only: waiting for your crypto deposit until `orderExpireTimestamp` (Unix seconds, returned only in this status) | No |
| `40` | Crypto debited from the wallet, fiat payout in progress | No |
| `50` | Payout step done, order not completed. Automated channels complete it on their own some time after the payout succeeds; or call `POST /v2/order/confirm` | No |
| `60` | Completed: the beneficiary was paid. Can still be refunded later (`73` then `72`, or straight to `72`) | Yes, unless later refunded |
| `70` | Cancelled (also post-funded deadline passed, and rare balance race after creation) | Yes |
| `71` | Cancelling: returning the crypto failed; a scheduled job finishes it | No |
| `72` | Refunded: the crypto is back in the merchant wallet | Yes |
| `73` | Refunding | No |
| `80` | Rejected in review (also review timed out) | Yes |
| `81` | Rejected in risk review | Yes |

A new API order normally starts in `10`, `11`, `31`, `32` or `40`. `GET /v2/orders` also lists non-API orders, which can show `20` or `30`.

## ORDER_WEBHOOK

- Only for orders created through the API; `orderType` is `SELL`.
- Sent for `10`, `11`, `12`, `31`, `32`, `40`, `50`, `60`, `70`, `72`. Not sent: `71`, `73`, `20`, `30`.
- `80` and `81` are sent as `70`.
- Deduplicate on `orderId` + `orderStatus`; read Get Order when an event does not fit your state.

## Failure handling

| What you see | Likely cause | What to do |
| --- | --- | --- |
| Create rejected with `-1131` | Wallet `free` balance does not cover the order (post-funded not enabled) | Deposit more crypto, then create again with a new `clientId` and quote |
| Create rejected for the beneficiary | `userPaymentId` not `status` `1`, belongs to another merchant, or currency/channel mismatch | Check with Get Beneficiary and the merchant's activated accounts |
| Create rejected as repeated submission (`-1174`) | `clientId` already used | Look up by `clientId`; do not create again |
| `70` after `32` | Post-funded deadline passed | Fund the wallet first, then create a new order |
| `80` / `81` when polling (`70` in webhook) | Rejected in review / risk review | Do not resubmit unchanged; contact VelaFi |
| Order stays in `40` | Rail rejected or has not confirmed. A rejected payout does not move the order to a final status by itself; VelaFi operations retry or cancel | Contact support with `orderId` if longer than usual. Do not create a second order |
| `60`, then `72` | Payout returned after completion (for example bounced by the beneficiary's bank) | Crypto is back in the wallet. Fix beneficiary details, create a new order with a new `clientId` |

`failReason` is often empty because many rails return no reason. Log it; drive logic by `orderStatus`.

## Reconciliation sources

- Each payout: Get Order by `orderId` or `clientId`: `orderStatus`, `cryptoAmount` (debited), `fiatAmount` (paid), `fiatFee`, `orderPrice`, `orderFeeDetail`, `traceNumber`, `failCode`, `failReason`.
- Totals: `GET /v2/orders?orderType=crypto_to_fiat` with `startTime`/`endTime` (matched against `completedTime`), `pageSize` up to 100.
- Wallet: `GET /v2/assets/depositOrders` and `GET /v2/assets/account/assets` (`free`, `locked`).
