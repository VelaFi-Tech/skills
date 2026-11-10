---
name: velafi-go-live-check
description: Review a VelaFi integration before production and produce a pass/fail go-live report. Walks the VelaFi go-live checklist and each use-case checklist (collections, payouts, on-ramp, off-ramp, onboarding, global payments), greps the codebase for risky patterns (hardcoded keys, secrets in logs, wrong webhook acknowledgement, missing signature verification, static or reused clientId, retries without a lookup, status handling that ignores 80/81, no IP whitelist note), traces each launching flow step by step through the code (call order, request fields, response handling, status-to-state mapping, ledger movements), runs the sandbox token check and the local webhook self-test, and optionally runs each flow end to end in the sandbox. Never calls production. Use when the developer asks "are we ready to go live", before switching to https://api.velafi.com, or for a VelaFi integration review.
license: Apache-2.0
---

# VelaFi go-live check

## Overview

A review the agent runs over the developer's VelaFi integration before it goes to production. It checks two things: that the integration is safe (credentials, webhooks, idempotency, errors) and that each flow is built correctly from the first call to the final state in the developer's system. It reads the code and never changes it. The only calls it makes are to the sandbox, and only with the developer's OK. It produces a report with PASS / FAIL / WARN / N/A per item, file:line evidence, and the fix with a doc link. It does not change code unless the developer asks afterwards.

It relies on the sibling skills:

- `velafi-api-setup` — token, errors, `clientId` rules; provides `scripts/check_token.py`.
- `velafi-webhooks` — receiver rules; provides `scripts/check_webhook_endpoint.py`.
- The flow skills describe each flow in detail: `velafi-onboard-merchants`, `velafi-collect-virtual-accounts`, `velafi-payouts-from-balance`, `velafi-onramp`, `velafi-offramp-payouts`, `velafi-global-payments`, `velafi-crypto-wallet`.

Source checklist: https://docs.velafi.com/docs/use-cases/go-live-checklist.md. Most production incidents come from three gaps: webhook endpoints that do not acknowledge in the required format, retries without a `clientId`, and no reconciliation job.

## Hard limits

- **Never call `https://api.velafi.com`.** Do not run `check_token.py --production`, do not run the app, tests or scripts against production config, and do not register, update or delete webhooks. If a test suite or script targets production, skip it and note it in the report.
- Never print, copy or commit secrets you find. Report the file and line, and mask the value (first 4 characters + `…`).
- Do not read secret values out of `.env` files into the conversation; ask the developer to export sandbox credentials in the shell if the token check should run.
- Do not edit code during the review. Offer fixes at the end.

## Before you start

**Ask first, then review.** Before you start the review, ask the developer the questions in this section and wait for their answers. If you have a tool for asking the developer multiple-choice questions, use it for questions with a few clear choices, such as environment, corridor, amount mode or funding crypto, and ask them in rounds if there are more than the tool takes at once. Ask open questions, such as merchant IDs, IP addresses or file paths, as text. Without such a tool, ask all the questions together in one message. If the request already answers a question, state your understanding in one line and ask them to confirm it.

Ask the developer:

1. Which flows are launching: collect with virtual accounts, payouts from balance, convert to stablecoins (on-ramp, prefunded or pay-per-order), payouts funded by stablecoins (off-ramp), onboard customers (sub-merchants), global payments (fiat-to-fiat), crypto withdrawals, stablecoin payments.
2. Which event types they subscribe to.
3. Where the VelaFi client, webhook handler, reconciliation job and config live (paths), and the language/framework.
4. Whether sandbox credentials are available as `VELAFI_API_KEY` / `VELAFI_API_SECRET` in the shell (for the token check).
5. Whether the webhook handler can run locally (for the self-test), and how to set its verification key in dev.
6. The production servers' public egress IPs and where they are documented.
7. Whether they want the optional sandbox run (step 6): their own code runs each launching flow against the sandbox. Skip it if they do not develop against the sandbox.

## Workflow

### 1. Map the integration

Find the VelaFi surface in the codebase (exclude `node_modules`, `vendor`, `dist`, `build`, `target`, `.git`):

```bash
grep -rnIE "velafi|/v2/(token|order|merchant|assets|webhook|user)|X-BH-(TOKEN|APIKEY)|callbackStatus|_WEBHOOK" . \
  --exclude-dir={node_modules,vendor,dist,build,target,.git,.venv,venv}
```

List: HTTP client and token code, each create call (`/v2/order/fiat_to_crypto`, `/crypto_to_fiat`, `/fiat_to_fiat`, `/v2/merchant/claimfunds`, `/v2/merchant/transfer`, `/v2/assets/withdraw`, `/v2/assets/internalTransfer`, `/v2/merchants`), status polling, webhook route(s), reconciliation jobs, config files.

### 2. Grep for risky patterns

Run every pattern group in `references/risky-patterns.md` and inspect each hit in context (grep finds candidates; you decide). Groups:

1. Hardcoded API key, secret, token or webhook public key; committed `.env` files.
2. Secrets or tokens in logs, error messages or URLs.
3. Webhook handler that returns the wrong body or status.
4. Missing or wrong signature verification (none, or over re-serialized JSON).
5. Static, reused, timestamp-only or missing `clientId`.
6. Retries on create calls without a `clientId` lookup; no handling of outcome-unknown codes.
7. Status handling that ignores `80`/`81` when polling, or `72` after `60`.
8. No IP whitelist / egress IP note; no handling of `-1023`, `-2015`, `-2019`.
9. Other: VelaFi called from browser/mobile code, branching on HTTP 401/429, floats for amounts, production URL hardcoded instead of configured, no token caching or no `-1022` refresh.

### 3. Walk the checklists

Evaluate every item in the shared checklist below, then the per-flow checklist in `references/use-case-checklists.md` for each flow that is launching. Mark an item PASS only with evidence (file:line, config, or the developer's explicit answer). Unknown is WARN, not PASS.

**Credentials and authentication**
- Sandbox and production credentials are separate and configured per environment; sandbox → `https://api-test.velafi.com`, production → `https://api.velafi.com`.
- Every production server's public IP is on the key's whitelist (max 5, no CIDR); a note lists them and says to update before moving servers or changing egress.
- Key, secret and tokens are server-side only; not in client code, logs or source control; `.env*` git-ignored.
- Token cached and refreshed before `expireTime`; `-1022` → new token and one resend.
- Key rotation plan exists (new key, whitelist, switch, delete old).

**Webhooks**
- A production webhook is planned per event type in use, registered before the first live transaction.
- Each webhook's `publicKey` is stored in config and the `signature` header is verified over the raw body bytes before parsing.
- Every accepted delivery is acknowledged with HTTP 2xx and exactly `{"callbackStatus":"SUCCESS"}`; failed verification returns `{"callbackStatus":"FAIL"}`.
- Handler verifies, stores, acknowledges, and processes asynchronously.
- Idempotent on event type + record id (`orderId`, `txId`, `withdrawId`) + status.
- Does not rely on order or on seeing every status; reads current state before acting.
- Reconciliation covers events dropped after 3 attempts.
- Handler response tested (self-test, step 4).

**Idempotency** — a new unique `clientId` per create call, stored before sending, reused only for the retry of the same request; a duplicate rejection (`-1174`, `Duplicate withdrawal request`) triggers a lookup. `POST /v2/merchants` retries look up by `email` first.

**Error handling** — branches on `code`, not HTTP status or `msg`; `-1001`, `-1006`, `-1007`, `30012` on create calls → lookup by `clientId`, then retry with the same `clientId`; backs off on `-1006` from rate-limited endpoints and on `30012`; logs `failCode`/`failReason` and acts on status.

**Reconciliation** — scheduled job re-checks non-final records against funding records, fiat flows, orders, crypto withdrawals and deposits; alerts on records stuck past expected time; daily balance reconciliation.

**Limits** — merchant and channel limits checked; `-5050`, `-5060`, `-5029`, `-5030`, `-5081` handled; higher limits requested if needed; rate limits respected.

**Monitoring** — requests logged with `clientId` and VelaFi IDs; alerts on token failures, webhook silence or non-acknowledgement, error-rate spikes, outcome-unknown codes, stuck records, and low balances.

### 4. Trace each flow end to end

For every launching flow, follow `references/flow-trace.md`: take the flow skill's Workflow steps as the expected sequence, find each step in the code, and check the call order, the request fields against the API reference, the response handling, the mapping of every status to a state in the developer's system, and the ledger movements. Report one table per flow. Any FAIL in a flow trace is blocking.

This is what shows whether the integration is correct, not only safe. A flow can pass every checklist item and still send the wrong `paymentId`, read the wrong field, or never record the final status.

### 5. Run the scripts (sandbox and local only)

Run these from the root of the developer's repository, using the full path to each script inside the installed skills (the `velafi-api-setup` and `velafi-webhooks` folders next to this skill). Keep the test key out of version control:

1. **Token check** (only if the developer has exported **sandbox** credentials):

   ```bash
   python3 <skills-dir>/velafi-api-setup/scripts/check_token.py
   ```

   Never pass `--production` and never set `VELAFI_BASE_URL` to production for this review. A failure code maps to a config item (IP whitelist, disabled key, API access). If credentials are not available, mark "not run".

2. **Webhook self-test** (only if the handler runs locally; needs `pip install cryptography`):

   ```bash
   python3 <skills-dir>/velafi-webhooks/scripts/check_webhook_endpoint.py http://localhost:<port>/<path> \
     --key-file .velafi-selftest-key.pem   # add .velafi-selftest-key.pem to .gitignore
   ```

   The developer configures the printed test public key temporarily in dev. Do not use `--allow-remote` against anything but an environment the developer owns. Record each PASS/FAIL line. Remind the developer to restore the real key and git-ignore the key file.

### 6. Optional: run each flow in the sandbox

Only if the developer said yes in "Before you start". Follow `references/sandbox-run.md`: trigger each launching flow through the developer's own code against `https://api-test.velafi.com`, fund test merchants with the simulators, poll to a final status, check the developer's system and ledger, and test one duplicate `clientId` per create call. A flow the sandbox cannot finish is NOT PROVABLE IN SANDBOX, not a FAIL; its flow trace stays the evidence. If the developer skips this step, mark it "not run" and rely on the flow trace.

### 7. Write the report

Use this structure:

```markdown
# VelaFi go-live report — <project> — <date>

Verdict: NOT READY | READY WITH WARNINGS | READY
Flows reviewed: ...   Event types: ...
Scripts: check_token.py <PASS/FAIL/not run> · check_webhook_endpoint.py <PASS/FAIL/not run>
Sandbox run: <done / not run>

## Flow traces
(one table per flow, from references/flow-trace.md)

## Sandbox runs
(one block per flow, from references/sandbox-run.md, or "not run")

## Blocking (FAIL)
| # | Item | Evidence | Fix | Doc |

## Warnings (WARN)
| # | Item | Evidence | Fix | Doc |

## Passed
- item — evidence

## Not applicable / not run
- item — reason
```

Verdict rules: any FAIL → NOT READY. No FAIL but any WARN → READY WITH WARNINGS. Always FAIL: hardcoded or committed secrets, secrets in logs, VelaFi called from client code, missing signature verification, wrong acknowledgement body, create-call retries without a `clientId` lookup, no reconciliation for webhook-driven flows, polling logic that treats `80`/`81` as non-final, a flow step the flow needs that is missing or wrong, and a sandbox run that failed because of the developer's code. A sandbox run marked "not run" or NOT PROVABLE IN SANDBOX is never a FAIL on its own.

State in the report that it reviews the developer's side only: it cannot check VelaFi's side (production IP whitelist, production webhooks, limits, channel setup).

End with the offer to fix the FAIL items, one at a time, and the reminder that webhooks do not fire in the sandbox, so the first real deliveries arrive in production: start with low-value transactions after the developer approves.

## Rules

- Never change the developer's code during the review; never call production; never register or change webhooks. Call the sandbox only in the optional sandbox run, with the developer's OK.
- Evidence or it is not a PASS.
- Mask any secret found; recommend rotating any key that was ever committed.
- Do not claim the integration is ready if any blocking item fails or the scripts could not run and nothing else covers those items.

## Reference links

- Go-live checklist: https://docs.velafi.com/docs/use-cases/go-live-checklist.md
- Authentication: https://docs.velafi.com/api-reference/authentication.md
- Error codes: https://docs.velafi.com/docs/error-codes.md
- Webhook setup: https://docs.velafi.com/api-reference/webhooks/webhook-setup.md
- Order statuses: https://docs.velafi.com/docs/order-statuses.md
- Transaction limits: https://docs.velafi.com/docs/limits.md
- Rate limits: https://docs.velafi.com/api-reference/overview#rate-limits
- Sandbox: https://docs.velafi.com/docs/sandbox.md
