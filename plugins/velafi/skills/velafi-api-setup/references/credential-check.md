# Credential check

Confirms that the developer's API key, secret, IP whitelist and API access work, before any integration code depends on them. Run it in the developer's own project, in their language, as a small check (for example a `check-velafi-token` command or a test) that reuses the token code you are building.

## Rules

- **Sandbox only.** Call `https://api-test.velafi.com`. Call `https://api.velafi.com` only if the developer explicitly asks for a production check in this conversation, and say which environment you are calling before you call it.
- **Token endpoint only.** The check calls `GET /v2/token/generate`, and optionally `GET /v2/user/account` with the token. Nothing that creates, changes or moves anything.
- **Credentials from the environment.** Read `VELAFI_API_KEY` and `VELAFI_API_SECRET` (and `VELAFI_BASE_URL` if set) from environment variables or the developer's secrets manager. Never ask the developer to paste the secret into the chat, never write it into code or files, and never pass it on a command line.
- **Never print the secret or the full token.** Print at most the first 6 characters of the token, followed by `…`, and the `expireTime`.
- **Warn on whitespace.** If the key or secret has leading or trailing spaces or a newline, say so: it is the most common cause of `-1022`.

## Steps

1. `timestamp` = current Unix time in milliseconds.
2. `signature` = HMAC-SHA256 of the exact string `timestamp=<timestamp>`, keyed with the API secret, as 64-character lowercase hex.
3. `GET {base}/v2/token/generate?timestamp=<timestamp>&signature=<signature>` with header `X-BH-APIKEY: <api key>`. Send only these two query parameters, in this order.
4. Success is HTTP `200`, `code` `200` (or `0`) and a `data.token`. Report `OK: token received`, the masked token and `expireTime` as a UTC time.
5. Optional: `GET {base}/v2/user/account` with header `X-BH-TOKEN: <token>`. A `200` confirms key, secret, whitelist and API access together.
6. On failure, report the HTTP status, `code` and `msg`, and the meaning from the table below.

## What the error codes mean

| Code | Meaning | What to do |
|---|---|---|
| `-1002` | The `X-BH-APIKEY` header is missing or not a valid API key format. | Check the header name and value. |
| `-1004` | The `signature` parameter is missing, or `timestamp` is missing while other parameters are sent. | Send both `timestamp` and `signature`. |
| `-1103` | The request has no query parameters, or `signature` is the only one. | Send `timestamp` and `signature`. |
| `-1022` | The signature does not match, or the API key does not exist. | Check the key and secret belong to the environment being called (sandbox keys only work on `https://api-test.velafi.com`, production keys only on `https://api.velafi.com`) and that the secret has no extra spaces or newlines. |
| `-1023` | The API key has no IP whitelist. | Add this server's public IP on the API Management page (Whitelist): up to 5 IPv4/IPv6 addresses per key, no CIDR ranges. |
| `-2015` | The key or account is disabled, or the request IP is not on the key's whitelist. | Check the whitelist contains this server's public egress IP. |
| `-5033` | API access is not enabled on the account. | Contact VelaFi (contact@velafi.com). |
| `-1000` | The credentials could not be verified for another reason. | Recheck the key, secret and whitelist; if it persists, contact VelaFi. |
| `-1001`, `-1007` | Internal error or backend timeout. | Retry later. |
| `-1006`, `30012` | Status unknown or network busy (rate limit). | Back off, then retry. |

Any other code: see https://docs.velafi.com/docs/error-codes.md.

## Run it yourself

Developers who prefer a ready-made script can run `tools/check_token.py` from https://github.com/VelaFi-Tech/skills themselves. It follows the same rules and refuses any host other than the sandbox unless `--production` is passed.
