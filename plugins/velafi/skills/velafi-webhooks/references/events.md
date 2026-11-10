# VelaFi webhook events

Every delivery is an HTTP POST with `Content-Type: application/json`, a `signature` header, and a JSON body whose values are all strings. Every payload has `webhookId`, `eventType` and `timestamp` (Unix ms, regenerated on every attempt). Source pages are linked per event; read them for every field.

## ORDER_WEBHOOK — on-ramp (`BUY`) and off-ramp (`SELL`) orders

https://docs.velafi.com/api-reference/webhooks/fiat-crypto-order-message-push.md

- Only orders created through the API.
- Key fields: `orderId`, `clientId` (omitted if you sent none), `merchantId`, `settingsId`, `orderType`, `fiat`, `fiatAmount`, `arriveFiatAmount`, `fiatFee`, `crypto`, `cryptoAmount`, `orderPrice`, `orderStatus`, `failCode`/`failReason` (only on `70`/`72` with a recorded code), `createTime`, `updateTime`. Legacy duplicates: `fiatCurrency`, `orderAmount`, `arriveOrderAmount`, `mcSettingsId`, `cryptoCurrency`, `quantity`.
- Statuses sent: `10` reviewing, `11` risk review, `12` RFI uploaded, `31` documents pending, `32` awaiting crypto deposit, `40` pending payment, `50` paid, `60` completed, `70` canceled/rejected/timed out, `72` refunded. Not sent: `20`, `30`, `71`, `73`.
- **Polling differs:** `GET /v2/order/detail` reports review rejection as `80` and risk-review rejection as `81`; the webhook sends both as `70`. Status handling must treat `70`, `80` and `81` as failed final states (https://docs.velafi.com/docs/order-statuses.md).
- A `60` order can later become `72` (refund after completion); release or reverse on your side.
- Dedupe: `orderId` + `orderStatus`.

## GLOBAL_PAYMENT_WEBHOOK — fiat-to-fiat orders

https://docs.velafi.com/api-reference/webhooks/fiat-fiat-order-message-push.md

- Only orders created through the API.
- Key fields: `orderId`, `clientId`, `onRampCountry`, `onRampMerchantId`, `onRampFiat`, `onRampFiatAmount`, `onRampFiatFee`, `offRampCountry`, `offRampMerchantId`, `offRampFiat`, `offRampFiatAmount`, `offRampFiatFee`, `orderPrice`, `orderStatus`.
- Statuses sent: `10`, `31`, `41` pay-in pending, `51` payout pending, `60` released, `71` pay-in canceled, `72` payout canceled. Read status codes together with order type: `71`/`72` mean different things for ramp orders.
- Dedupe: `orderId` + `orderStatus`.

## FUNDING_WEBHOOK — fiat activity on the merchant's Pending Fund account

https://docs.velafi.com/api-reference/webhooks/funding-records-message-push.md

- `type`: `DEPOSIT`, `WITHDRAW` (fiat payout, not crypto), `BUY_CRYPTO`. `status`: `2` completed, `3` canceled, `4` refunded. Pending records are not sent. Merchant-to-merchant transfers (`TRANSFER_IN`/`TRANSFER_OUT`) are not sent.
- Key fields: `txId`, `clientId`, `merchantId`, `merchantName`, `fiat`, `totalAmount` (negative for `WITHDRAW`, `BUY_CRYPTO`), `amount`, `fee`, `refundedAmount`, `paymentId`, `userPaymentId`, `completedTime`, `refundedTime`, `depositAlias` (virtual account that received a deposit), payer details `cardNo`, `taxId`, `payerName`, `payerAccount` (may be absent), `bankWebhookInfo` (provider JSON **string**, shape varies by currency), `failCode`/`failReason` (only on canceled payouts with a recorded code; can be missing), `extId` (for `BUY_CRYPTO`, the on-ramp order ID), `bankOrderId`.
- Deposits without a `depositAlias` should go to a review queue in collection flows.
- Dedupe: `txId` + `status`. Reconcile with `GET /v2/merchant/funding/records`.

## ON_RAMP_WITHDRAW_WEBHOOK — on-ramp crypto delivered to the destination address

https://docs.velafi.com/api-reference/webhooks/on-ramp-withdraw-message-push.md

- Only for API on-ramp orders that VelaFi withdraws automatically (enabled per account). Only successes are sent; `status` is always `succeeded`.
- Key fields: `orderId`, `clientId`, `network`, `address`, `crypto`, `amount`, `txHash` (may be omitted).
- The same transfer also triggers `CRYPTO_WITHDRAW_WEBHOOK` if subscribed.
- Dedupe: `orderId`.

## STABLE_COIN_PAYMENT_WEBHOOK — stablecoin payment confirmed

https://docs.velafi.com/api-reference/webhooks/stablecoin-payment-order-message-push.md

- The only stablecoin payment event. Rejected, cancelled, refunded or mismatched orders send nothing.
- Key fields: `orderId`, `merchantId`, `linkId`, `walletId`, `walletName`, `referenceId`, `currency`, `network`, `networkName`, `depositAmount`, `feeAmount`, `receivedAmount`, `status` (normally `CONFIRMED`), `fromAddress`, `toAddress`, `txHash`, `paymentLink`, `createTime`, `cancelTime`, `processTime`, `confirmTime`. An unset timestamp is the string `"null"`.
- Dedupe: `orderId` + `status`.

## CRYPTO_WITHDRAW_WEBHOOK — merchant-wallet crypto withdrawals

https://docs.velafi.com/api-reference/webhooks/crypto-withdraw-message-push.md

- Only final statuses: `SUCCESS` (`statusCode` `6`, has `txHash`), `FAILED` and `REFUNDED` (`7`, funds back in the wallet; handle `REFUNDED` like `FAILED`), `CANCELLED` (`9`, cancelled in the dashboard).
- Covers API and dashboard withdrawals (including by team members), mass payout items (`clientId` `masspayout:<id>`), and automatic on-ramp withdrawals (`clientId` = on-ramp `orderId`, `fee` `0`). Not sent for withdrawals to a VelaFi address (internal transfers), stablecoin payment refunds, or non-final states.
- Key fields: `withdrawId` (= `orderId` from Create Crypto Withdrawal and withdrawal history), `clientId`, `merchantId`, `crypto`, `network`, `address`, `amount`, `fee`, `netAmount`, `status`, `statusCode`, `txHash`, `createTime`, `completeTime`.
- Security use: match each event to your own records by `withdrawId` or `clientId` and alert on withdrawals you did not initiate, unknown addresses or unusual amounts.
- Queued events go only to the webhook they were queued for: change the URL with `PUT /v2/webhook/{webhookId}`, do not delete and recreate.
- Dedupe: `withdrawId` + `status`. Reconcile with `GET /v2/assets/withdrawalOrders`.

## Delivery rules (all events)

https://docs.velafi.com/api-reference/webhooks/webhook-setup#delivery-and-retries

- Success = HTTP 2xx and a JSON object with `"callbackStatus":"SUCCESS"`. Timeouts: 60 s connect/write/read.
- 3 attempts in total: about 5–10 min after the first failure, then about 60–65 min after the second. Then dropped; no redelivery endpoint.
- Duplicates happen. Order is not guaranteed. For `ORDER_WEBHOOK`, `GLOBAL_PAYMENT_WEBHOOK`, `FUNDING_WEBHOOK` and `ON_RAMP_WITHDRAW_WEBHOOK`, an event whose record changed status before the attempt is discarded, so intermediate statuses can be skipped.
- Events are queued only while an active webhook exists for the type. Queued events survive a disable/delete and go to a new active webhook of the same type created within about 15 days (except `CRYPTO_WITHDRAW_WEBHOOK`).
- Not sent in the sandbox.
