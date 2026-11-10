# Global payment statuses, webhook mapping and pairs

Sources: https://docs.velafi.com/docs/order-statuses.md, https://docs.velafi.com/api-reference/webhooks/fiat-fiat-order-message-push.md, https://docs.velafi.com/docs/guides/global-payments.md

## Global payment order status codes (`fiat_to_fiat`)

| Code | Name | Meaning | Final |
| --- | --- | --- | --- |
| `10` | Reviewing | Under review | No |
| `11` | Risk review | Under risk review. Upload documents; moves to `12` | No |
| `12` | RFI documents uploaded | Waiting for a decision | No |
| `31` | Supporting documents pending | Documents required and none uploaded. After upload the order shows `41` or `51` again | No |
| `41` | Pay-in pending | Waiting for the sender's fiat deposit | No |
| `51` | Payout pending | Pay-in leg complete, payout leg in progress | No |
| `60` | Completed | Payout leg complete | Yes |
| `71` | Pay-in cancelled | Pay-in leg cancelled. Review rejections and review timeouts are also `71` | Yes |
| `72` | Payout cancelled | Payout leg cancelled | Yes |
| `90` | Risk review rejected | Rejected in risk review | Yes |

### Same codes, different meaning (ramp vs global payment)

| Code | Ramp order (`fiat_to_crypto`, `crypto_to_fiat`) | Global payment (`fiat_to_fiat`) |
| --- | --- | --- |
| `71` | Cancelling (not final) | Pay-in cancelled (final) |
| `72` | Refunded (final) | Payout cancelled (final) |
| `90` | Never returned | Risk review rejected (final) |

Ramp-only codes such as `40`, `50`, `70`, `80`, `81` do not appear on fiat_to_fiat orders; `41` and `51` do not appear on ramp orders.

### Internal statuses and how they are reported

| Internal | Reported as |
| --- | --- |
| `0` (initialising) | `10` |
| `30` (approved) | `41`, or `31` if documents are required and missing |
| `40` (pay-in received) | `51` |
| `41`, `51` | Unchanged, or `31` if documents are required and missing |
| `73` (review timed out) | `71` |
| `90` (review rejected) | `71` |
| `91` (risk review rejected) | `90` |

Because `GET /v2/orders` filters fiat_to_fiat on the **stored** status: `10`, `11`, `12`, `60`, `72` match exactly; `41`/`51` can also return orders reported as `31`; filtering by `31`, `71` or `90` does not return exactly those orders.

## GLOBAL_PAYMENT_WEBHOOK

- Sent only for fiat_to_fiat orders created through the API.
- Statuses sent: `10`, `31`, `41`, `51`, `60`, `71`, `72`. Other statuses are not sent.
- A status can be skipped if the order already moved on. Duplicates possible: deduplicate on `orderId` + `orderStatus`.
- Payload fields (strings): `webhookId`, `eventType`, `orderId`, `clientId` (omitted if none), `userId`, `onRampCountry`, `onRampMerchantId`, `onRampFiat`, `onRampFiatAmount`, `onRampFiatFee`, `offRampCountry`, `offRampMerchantId`, `offRampFiat`, `offRampFiatAmount`, `offRampFiatFee`, `orderPrice`, `orderStatus`, `createTime`, `updateTime`, `timestamp`.
- Acknowledge with HTTP 2xx and exactly `{"callbackStatus":"SUCCESS"}`.

## Supported pairs (from the guide; always confirm with `GET /v2/base/fiat/symbols`)

| Sending country | Sending currency | Receiving country | Receiving currency |
| --- | --- | --- | --- |
| Argentina | ARS | Mexico | MXN |
| Argentina | ARS | United States | USD |
| Brazil | BRL | Argentina | ARS |
| Brazil | BRL | Hong Kong | USD |
| Brazil | BRL | Global | USD |
| Colombia | COP | Mexico | MXN |
| Mexico | MXN | Argentina | ARS |
| Mexico | MXN | Colombia | COP |
| Mexico | MXN | Hong Kong | USD |
| Mexico | MXN | United States | USD |
| Mexico | MXN | Global | USD |
| United States | USD | Argentina | ARS |
| United States | USD | Mexico | MXN |

"Global" covers USD payouts not tied to a specific country. Pairs are directional. Contact VelaFi for a pair that is not listed.
