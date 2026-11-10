# CRYPTO_WITHDRAW_WEBHOOK and withdrawal monitoring

Sources: https://docs.velafi.com/api-reference/webhooks/crypto-withdraw-message-push.md and the Security Best Practices section of https://docs.velafi.com/api-reference/authentication.md

Register with `POST /v2/webhook` and `"eventType": "CRYPTO_WITHDRAW_WEBHOOK"` (see `velafi-webhooks`). One webhook receives events for every merchant under the account. Not sent in the sandbox.

## Coverage

Sent when a withdrawal reaches a final status for:

- withdrawals to external addresses created with `POST /v2/assets/withdraw` **or in the VelaFi dashboard**;
- mass payout items sent to external addresses (`clientId` = `masspayout:<id>`, shared by all items);
- automatic withdrawals of on-ramp orders (`clientId` = the on-ramp `orderId`, `fee` always `0`). These also send `ON_RAMP_WITHDRAW_WEBHOOK` on success.

Not sent for: withdrawals to VelaFi wallet addresses (booked as internal transfers), stablecoin payment refunds, and any non-final state (in progress, approval, review).

## Payload (all values are strings)

`webhookId`, `eventType` (`CRYPTO_WITHDRAW_WEBHOOK`), `withdrawId` (= `orderId` from create and history), `clientId`, `userId`, `merchantId`, `crypto`, `network` (= `chainType`), `address`, `amount`, `fee`, `netAmount`, `status`, `statusCode`, `txHash` (only on `SUCCESS`), `createTime`, `completeTime`, `timestamp`.

| `status` | `statusCode` | Meaning | Action |
| --- | --- | --- | --- |
| `SUCCESS` | `6` | Completed on-chain | Mark sent, store `txHash` |
| `FAILED` | `7` | Failed or rejected; amount returned to the wallet | Mark failed, release the user's balance |
| `REFUNDED` | `7` | Funds left, came back, and were returned to the wallet | Same as `FAILED` |
| `CANCELLED` | `9` | Cancelled in the dashboard before sending; amount returned | Mark cancelled (the Open API has no cancel endpoint) |

## Handler requirements

- Verify the `signature` header (RSA-SHA256, hex, over the raw body, webhook `publicKey`) before trusting the body.
- Return HTTP 2xx with exactly `{"callbackStatus":"SUCCESS"}`. Anything else counts as a failure and is retried.
- Deduplicate on `withdrawId` + `status`.
- 3 delivery attempts, then the event is dropped with no redelivery. Reconcile pending withdrawals against `GET /v2/assets/withdrawalOrders`, matching on `clientId` (or `withdrawId` = `orderId` for mass payout items).
- To change the URL, **update** the existing webhook (`PUT /v2/webhook/{webhookId}`, see https://docs.velafi.com/api-reference/webhooks/update-a-webhook.md). Pending deliveries go only to the webhook they were queued for: creating a new webhook after deleting or disabling the old one loses them. Re-enabling the same disabled webhook delivers its pending events.

## Monitoring withdrawals you did not initiate

1. Record every withdrawal you create (`clientId`, `orderId`, `address`, `amount`) before or right after the API call.
2. For each event, look up your record by `withdrawId` or `clientId`.
3. Alert (do not silently ignore) when:
   - no matching record exists (for example a dashboard withdrawal by a team member, or a compromised key);
   - `address` is not one you expect;
   - `amount` is unusual for that merchant.
4. The event arrives after the withdrawal completes or fails, so it cannot stop one. Limit where funds can go by keeping the withdrawal whitelist short and reviewing `GET /v2/user/whitelistAddress` regularly.
5. If you see suspicious activity, delete the API key on the API Management page, create a new one, and contact VelaFi support.
