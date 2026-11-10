# Payout and transfer error codes

Source: https://docs.velafi.com/docs/use-cases/payouts-from-balance#handle-failures and https://docs.velafi.com/docs/error-codes.md

Errors come back as HTTP 400 with a negative `code`. If `claimfunds` returns an error, no funding record was created and nothing was debited.

| Code | Cause | What to do |
|---|---|---|
| `-1131` | Not enough balance from this channel to cover `amount` + `fee` | Wait for deposits, or lower the amount |
| `-1174` | `clientId` already used by a funding record under your account (payout or transfer) | The operation already exists: look it up by `clientId` in funding records. Never create another with the same ID |
| `-4027` | `userPaymentId` does not exist or belongs to another account | Check the beneficiary ID |
| `-5017` | Beneficiary not valid (not status `1`) | Use a valid beneficiary, or save it again |
| `-4001` | Validation failed, e.g. the merchant's currency account on that channel does not support payouts or is not active | Check the channel against the supported table and the account status |
| `-1181` | Payouts disabled for this merchant | Contact VelaFi support |
| `-5051` | Beneficiary currency differs from `fiat` | Use a beneficiary for the same currency |
| `-5070` | Beneficiary does not belong to this merchant's currency account on that channel | Save the beneficiary under the same merchant and channel as the balance |
| `-5030` | Payout exceeds the account's withdrawal limit | Contact VelaFi to review the limit |
| `-5050` | Amount below the minimum (PEN: 10) | Raise the amount |
| `-1146` | Another payout or transfer for the same merchant and currency was being processed | Retry after a short wait with the same `clientId` |

Beneficiary creation errors: `-4010` (missing or invalid field, missing `merchantId` for a manual method, or a dropdown value that is not an option `code`) and `-5070` (missing `merchantId` for an automatic method).

## Outcome-unknown responses

On a timeout, a network error, or an outcome-unknown code (for example `-1007`), the payout may or may not exist. Do not generate a new `clientId`. Query `GET /v2/merchant/funding/records?clientId=...` first, then resend with the same `clientId` only if no record exists.
