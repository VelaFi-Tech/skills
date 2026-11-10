# Risky-pattern greps

Run from the repository root. Define this helper first (works in bash and zsh); it skips dependency and build folders and binary files:

```bash
velafi_grep() { grep -rnIE --exclude-dir=node_modules --exclude-dir=vendor --exclude-dir=dist --exclude-dir=build \
  --exclude-dir=target --exclude-dir=.git --exclude-dir=.venv --exclude-dir=venv "$@"; }
```

Then run `velafi_grep '<pattern>' .` for each pattern. Every hit is a candidate: open the file, read the surrounding code, and decide. Report file:line, never the secret value (mask to the first 4 characters + `…`).

## 1. Hardcoded credentials (FAIL)

- `(api[_-]?secret|apiSecret|API_SECRET|secretKey)\s*[:=]\s*["'][A-Za-z0-9+/=_-]{16,}["']` — Secret literal in code or config
- `(api[_-]?key|apiKey|API_KEY)\s*[:=]\s*["'][A-Za-z0-9+/=_-]{16,}["']` — API key literal (check it is VelaFi's)
- `X-BH-APIKEY["']?\s*[,:]\s*["'][A-Za-z0-9_-]{12,}` — Key literal passed as header
- `X-BH-TOKEN["']?\s*[,:]\s*["'][0-9a-fA-F-]{20,}` — Token literal
- `hmac.{0,60}["'][A-Za-z0-9+/=_-]{24,}["']` — HMAC keyed with a literal
- `MIIBIjAN` — Webhook public key in source (WARN: move to config per environment; not a secret, but environment-specific)

Also:

```bash
git ls-files | grep -E '(^|/)\.env($|\.)' | grep -vE '\.env\.(example|sample|template)$'   # committed env files: FAIL
grep -nE '^\.env' .gitignore || echo "no .env rule in .gitignore"                             # WARN if missing
git log --all --oneline -S 'VELAFI_API_SECRET=' | head                                         # secret ever committed: FAIL, rotate the key
```

Pass: values come from env vars or a secrets manager; `.env*` ignored; `.env.example` holds placeholders only.

## 2. Secrets in logs, errors or URLs (FAIL)

- `(console\.(log|error|info)|logger\.\w+|log\.\w+|logging\.\w+|print\(|System\.out\.print|fmt\.Print).{0,120}(secret|apiSecret|API_SECRET|token|X-BH-TOKEN|X-BH-APIKEY|signature)` — Logging credentials or the token
- `(console\.(log|error)|logger\.\w+|log\.\w+|print\().{0,80}(headers|config)\b` — Logging whole header/config objects
- `[?&]token=` — Token in a query string

The `signature` query parameter of `/v2/token/generate` is expected in that one URL; logging that full URL is a WARN.

## 3. Webhook acknowledgement (FAIL)

First find the handler: `velafi_grep 'callbackStatus|_WEBHOOK|/webhooks?/' .`. If no `callbackStatus` appears anywhere while the flow relies on webhooks: FAIL (the handler cannot be acknowledging correctly).

- `callbackStatus["']?\s*[:=,]\s*["'](success|Success|ok|OK)["']` — Wrong case or value
- `(send|json|write|return|body)\s*\(?\s*["'](SUCCESS|success|OK|ok)["']` — Plain-text acknowledgement
- `received["']?\s*:\s*true|["']status["']\s*:\s*["']ok["']` — Generic JSON ack
- `sendStatus\(\s*20[04]\s*\)|status\(\s*204\s*\)|HttpStatus\.NO_CONTENT|ResponseEntity\.ok\(\)\.build\(\)|status_code\s*=\s*204|Response\(status_code=200\)` — Empty body

Also check in context: every verified path (including duplicates) returns `{"callbackStatus":"SUCCESS"}` with 2xx and `Content-Type: application/json`; no slow work (external calls, heavy DB transactions) happens before the response; exceptions do not fall through to a framework error page that returns 2xx with HTML.

## 4. Signature verification (FAIL)

In the handler file(s), look for a verifier:

`SHA256withRSA|RSA-SHA256|createVerify|crypto\.verify|PKCS1v15|pkcs1_15|Signature\.getInstance|openssl_verify|rsa\.VerifyPKCS1v15`

- None in the handler path: FAIL.
- Verifier exists but runs on re-serialized JSON: FAIL. Patterns: `JSON\.stringify\(req\.body\)`, `json\.dumps\(request\.(json|get_json)`, `objectMapper\.writeValueAsString\(` near the verifier, or a DTO-bound body (`@RequestBody SomeDto`, a Pydantic model parameter, `request.json` / `request.get_json()` before verification).
- Global `app.use(express.json())` / `bodyParser.json()` registered before the webhook route without `express.raw` or a `verify` callback that keeps the raw buffer: FAIL.
- Header read from the wrong name (must be `signature`), or base64-decoding the signature instead of hex-decoding: FAIL.
- Verification result ignored, logged only, or behind a flag that is off in production (`SKIP_SIGNATURE`, `verify=False`, `if (env !== "production")`): FAIL.
- Public key hardcoded rather than configured per environment: WARN.

## 5. clientId (FAIL)

- `clientId["']?\s*[:=]\s*["'][^"'${}]+["']` — Literal/static `clientId`
- `clientId.{0,60}(Date\.now\(\)|time\.time\(\)|currentTimeMillis|nanoTime|new Date\(\))` — Timestamp-only (collides under load; WARN unless combined with a unique ID)
- `clientId.{0,60}(amount|beneficiary|userPaymentId)` — Derived from business fields (repeats for identical payouts)

For each create call (`/v2/order/fiat_to_crypto`, `/v2/order/crypto_to_fiat`, `/v2/order/fiat_to_fiat`, `/v2/merchant/claimfunds`, `/v2/merchant/transfer`, `/v2/assets/withdraw`, `/v2/assets/internalTransfer`): check a fresh unique `clientId` is generated per operation, **persisted before** the request, reused on the retry of that request only, and replaced after a final failure. No `clientId` on a create call: FAIL.

## 6. Retries without a lookup (FAIL)

- `axios-retry|got\.extend\(.{0,40}retry|p-retry|async-retry|tenacity|backoff\.|@Retryable|RetryTemplate|Resilience4j|retry_on|maxRetries|max_retries|retries\s*[:=]` — Generic retry wrappers
- `-1001|-1006|-1007|30012|-1174` — Handling of outcome-unknown and duplicate codes
- `/v2/order/detail|/v2/orders|funding/records|withdrawalOrders|internalTransferOrders` — Lookup endpoints

FAIL when a create call is wrapped in a generic retry (or retried on timeout/5xx/`-1006`) without first looking up the `clientId`, or when a retry generates a new `clientId`. WARN when the outcome-unknown codes are not referenced at all. Retrying `GET` calls is fine.

## 7. Status handling (FAIL)

- `orderStatus.{0,40}(70|"70"|'70')` — Failure checks
- `\b(80|81)\b` near `orderStatus` — Review / risk-review rejections
- `\b72\b` near `orderStatus` — Refund after completion

- Polling code that treats `70` as the only failure and keeps waiting on `80`/`81` (ramp orders): FAIL. The webhook sends rejections as `70`; polling returns `80`/`81`.
- A `60` order treated as permanently final, with no handling of a later `72`: WARN for on-ramp, FAIL for off-ramp payouts.
- Ramp and global payment status codes mixed (`71`/`72` mean different things): FAIL.
- Global payment polling that ignores `90` (risk review rejected): FAIL.
- Crypto withdrawals: `7` / `FAILED` / `REFUNDED` and `9` / `CANCELLED` handled as final: required.

## 8. IP whitelist and auth alerts (WARN)

```bash
velafi_grep -i 'whitelist|allowlist|egress|static ip|nat gateway|outbound ip' README* docs/ deploy/ infra/ ops/ 2>/dev/null
velafi_grep -- '-1023|-2015|-2019|-1022' .
```

- No note listing the production egress IPs and the need to whitelist them (max 5 per key, no CIDR): WARN. Ask the developer; a serverless runtime without a fixed egress IP is a FAIL.
- No handling or alerting for `-1023`, `-2015`, `-2019`: WARN.
- No `-1022` refresh-and-resend, or a new token fetched on every request: WARN.

## 9. Other checks

- **VelaFi called from client code**: `api(-test)?\.velafi\.com|X-BH-` in `src/components`, `pages/` client code, `*.tsx`/`*.jsx` bundles, mobile app sources — FAIL
- **Branching on HTTP 401/429**: `status(Code)?\s*===?\s*(401|429)` in the VelaFi client — WARN (VelaFi returns 400 + `code`)
- **Matching on `msg` text**: `msg\s*===?\s*["']|\.msg\.(includes|contains|startsWith)` — WARN
- **Floats for amounts**: `parseFloat\(.{0,30}[Aa]mount|float\(.{0,30}[Aa]mount|Double\.parseDouble` — WARN
- **Production URL hardcoded**: `https://api\.velafi\.com` outside config — WARN
- **Sandbox URL in production config**: `api-test\.velafi\.com` in prod config files — FAIL
- **No reconciliation job**: no scheduler/cron hitting the lookup endpoints — FAIL for webhook-driven flows
