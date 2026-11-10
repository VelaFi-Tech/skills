# Optional sandbox run

The flow trace reads the code. The sandbox run executes it: the developer's own code runs each launching flow against the sandbox, and the report records the sandbox IDs as evidence. It is **optional**. Many teams build without the sandbox; for them the flow trace is the main evidence and this step is marked "not run".

## When to run it

Only when all of these are true:

- The developer says yes to it in this review.
- Sandbox credentials are available, and the code's base URL can be set to `https://api-test.velafi.com` through configuration.
- The developer can start the app (or call its service layer) locally against sandbox config.

Never point the run at `https://api.velafi.com`. If anything in the run would call production, stop and mark the step "not run".

## How to run it

For each launching flow:

1. Ask the developer how to trigger the flow in their app (an API route, a CLI command, a test, a job), and use that. The point is to exercise **their** code, not to call VelaFi directly from the review. Calling VelaFi directly is only for setup and checking results (funding a test merchant, reading a record).
2. Fund the test merchant if the flow needs it, with the simulators on https://docs.velafi.com/docs/sandbox.md#sandbox-testing-tools:
   - Fiat: `POST /v2/platform/test/deposit` (pass `depositAlias` to credit a virtual account; up to 100,000 per deposit).
   - Crypto: `POST /v2/platform/test/crypto/deposit` (`USDT` or `USDC`; up to 10,000 per deposit).
   If a simulator returns `Request rejected`, test deposits are not enabled for this sandbox account. Ask the developer to contact VelaFi (contact@velafi.com) to enable them, and mark the funded flows "not run" for now.
3. Trigger the flow and record each ID (`clientId`, `orderId`, `txId`, `userPaymentId`, `merchantId`).
4. Poll the record until it is final or the wait below has passed. Webhooks are not sent in the sandbox, so poll and use the webhook self-test for the handler.
5. Check the developer's own system: the record reached the expected state and the ledger moved once, by the right amount.
6. Run the idempotency check once per create call: send the same `clientId` again and expect the duplicate rejection (`-1174`, or `Duplicate withdrawal request` for crypto withdrawals), and check the code then looks the record up instead of failing.

## What the sandbox can show

| Flow | What to expect in the sandbox |
| --- | --- |
| Collect with virtual accounts | A simulated deposit to the alias appears in funding records (`type=DEPOSIT`, `status` `2`) and raises the balance. |
| Pay out from your balance | Payouts usually reach a final status within a few minutes. Some sandbox payouts fail on purpose, so a failed payout is expected sometimes and is a chance to check the failure path, not a bug. |
| Convert to stablecoins, prefunded | Orders are approved automatically in review and usually complete. Automatic withdrawal is shown as successful, but nothing is sent on chain: do not check the `txHash` on a block explorer. |
| Convert to stablecoins, pay-per-order | Paying a specific order in the sandbox may not be possible. Test the unpaid path instead: create an order, do not pay it, and check your code handles `70`. |
| Pay out funded with stablecoins | Orders can reach `60`, and some fail on purpose; both outcomes test your code. |
| Onboard your customers | Use the pre-configured test merchants. Do not expect a new merchant, especially a business, to be approved in the sandbox, and channel activation may not reach `status: 2`. Write the status handling against the documented codes. |
| Global payments | The order may not reach a final status in the sandbox, especially USD or EUR routes. |
| Crypto withdrawals | Withdrawals may not complete in the sandbox. Check request validation, the whitelist rejection and the duplicate `clientId` rejection. |

Wait up to 15 minutes for a record to become final. Sandbox behaviour can change; when the table and the sandbox disagree, the sandbox result is the evidence.

## How to report it

Add one card per flow to the report's Sandbox run section (`report-template.html`) with: how it was triggered, the IDs (`clientId`, `orderId` or `txId`), the final status and how long it took, the state and ledger change in the developer's system, how a duplicate `clientId` was handled, and the result:

- **PASS**: the flow reached a final status and the developer's system matched it.
- **FAIL**: the developer's code caused the problem: a request rejected with an error code, a status the code mishandled, a wrong ledger movement, or a duplicate `clientId` that was not handled. Every FAIL here is blocking.
- **NOT PROVABLE IN SANDBOX**: the sandbox could not take the flow to a final state for reasons outside the developer's code (see the table). This is not a FAIL. The flow trace stays the evidence for that flow.
- **not run**: the developer chose to skip it, or it could not run safely.

A sandbox run never proves VelaFi's side of the integration (production whitelist, production webhooks, limits, channel setup). Say so in the report.
