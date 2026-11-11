# VelaFi Agent Skills

Agent skills that help AI coding assistants (Claude Code, Codex, Cursor and others) build correct integrations with the [VelaFi API](https://docs.velafi.com): crypto-fiat on-ramps and off-ramps, local collections and payouts, cross-border payments and the crypto wallet.

Each skill is a folder with a `SKILL.md` (instructions the agent follows) and, where useful, `references/` (detail loaded on demand). The skills follow the [Agent Skills](https://agentskills.io) format and are built from the published [VelaFi API documentation](https://docs.velafi.com).

## Install

**Claude Code CLI**

In a Claude Code session in your terminal:

```
/plugin marketplace add VelaFi-Tech/skills
/plugin install velafi-skills@velafi
```

Or from your shell:

```bash
claude plugin marketplace add VelaFi-Tech/skills
claude plugin install velafi-skills@velafi
```

**Claude desktop app**

The `/plugin` commands do not work in the desktop app. Open **Customize** → **Plugins**, click **Add**, choose **Add marketplace**, and paste the repository URL `https://github.com/VelaFi-Tech/skills`. Then install **velafi-skills** from the VelaFi marketplace. Menu names can differ slightly between app versions; if the option is missing, install from the CLI instead.

The plugin also connects the [VelaFi docs MCP server](https://docs.velafi.com/docs/developer-tools/build-with-ai) (`https://docs.velafi.com/mcp`), so the agent can look up any page while it works.

**Codex**

```bash
codex plugin marketplace add VelaFi-Tech/skills
codex plugin add velafi-skills@velafi
```

The plugin installs all VelaFi skills and connects the docs MCP server.

**Other agents** (Cursor, Windsurf and others supported by the [skills CLI](https://github.com/vercel-labs/skills))

```
npx skills add VelaFi-Tech/skills
```

Update later with `/plugin marketplace update` (Claude Code), `codex plugin marketplace upgrade` (Codex) or `npx skills update`. In Claude Code you can also turn on auto-update for the VelaFi marketplace: open `/plugin` and go to **Marketplaces**.

Before it writes any code, the agent asks a few setup questions, such as the country and currency, your merchant IDs and the environment. Answer them, or tell it which ones to skip.

## Skills

| Skill | Use it to |
| --- | --- |
| `velafi-api-setup` | Set up credentials, generate and refresh tokens, handle errors and `clientId` rules. Includes a sandbox credential check. |
| `velafi-webhooks` | Register webhooks, verify signatures, acknowledge correctly and deduplicate events. Includes a local self-test for your endpoint. |
| `velafi-collect-virtual-accounts` | Collect local payments into your fiat balance with virtual accounts. |
| `velafi-payouts-from-balance` | Pay out local currency from your balance and move balance between merchants. |
| `velafi-onramp` | Convert local currency to stablecoins (prefunded or pay-per-order). |
| `velafi-offramp-payouts` | Pay out local currency funded with stablecoins, including USD and EUR payouts. |
| `velafi-onboard-merchants` | Onboard your own customers as merchants with KYC/KYB links and activate their currency accounts. |
| `velafi-crypto-wallet` | Deposit addresses, whitelist, crypto withdrawals and transfers, and withdrawal monitoring. |
| `velafi-global-payments` | Fiat-to-fiat cross-border payments. |
| `velafi-go-live-check` | Review an integration against the go-live checklist before production. |

## Example prompts

- "Integrate VelaFi so our customers in Mexico can pay us by SPEI, with one CLABE per customer."
- "Add a VelaFi webhook endpoint to this service and test it locally."
- "Pay out BRL by Pix from our USDT balance with VelaFi."
- "Run the VelaFi go-live check on this repository."

## Safety

- The skills are instructions only (Markdown). They never contain credentials, and they tell the agent to keep your API key and secret in environment variables or a secrets manager, never in code or logs.
- The agent works against the sandbox (`https://api-test.velafi.com`) by default and must ask you before calling production or moving money.
- The credential check calls only `GET /v2/token/generate` (and optionally `GET /v2/user/account`) on the sandbox unless you explicitly ask for production, and never prints your secret or the full token. The webhook self-test only sends signed test events to your own local endpoint and never contacts VelaFi.
- You stay in control of what gets built. Review generated code and test it in the sandbox before going live. Webhooks are not sent in the sandbox.

## Data and services

The plugin stores no data of its own. When you use it, the agent contacts only these services:

| Service | When | What is sent |
| --- | --- | --- |
| VelaFi docs MCP server (`https://docs.velafi.com/mcp`, the plugin's declared connector) | When the agent looks up the docs | Search queries and page paths. The optional `submit_feedback` tool sends the documentation feedback you choose to submit. No credentials. |
| VelaFi API sandbox (`https://api-test.velafi.com`) | When you ask the agent to test against the sandbox, run the credential check, or run the optional go-live sandbox run | Your own sandbox API key and signed requests, and the test data you create (for example test merchants, virtual accounts, orders and payouts). Responses can include merchant names and emails from your sandbox account. |
| VelaFi API production (`https://api.velafi.com`) | Only if you explicitly approve a production call | The same as the sandbox, with your production credentials. |

The webhook self-test sends test events only to your own local webhook endpoint. Data you send to VelaFi is handled under the [VelaFi Privacy Policy](https://help.velafi.com/en-001/articles/privacy-policy-46596314230036) and [Terms and Conditions](https://help.velafi.com/en-001/articles/terms-and-conditions-46592435609492).

## Optional scripts

The `tools/` folder in this repository has two standalone scripts that run the same self-checks with the safety rules built into the code. They are not part of the plugin; download and run them yourself if you prefer a ready-made check:

- `tools/check_token.py`: checks your credentials against the sandbox (Python 3 standard library). It calls only `GET /v2/token/generate`, refuses any host other than the sandbox unless you pass `--production`, and never prints your secret or the full token.

  ```bash
  VELAFI_API_KEY=... VELAFI_API_SECRET=... python3 tools/check_token.py
  ```

- `tools/check_webhook_endpoint.py`: sends signed test events to your local webhook endpoint and checks the acknowledgement, duplicates, signature verification and response time (needs `pip install cryptography`). It only targets localhost unless you pass `--allow-remote`, and never contacts VelaFi.

  ```bash
  python3 tools/check_webhook_endpoint.py http://localhost:3000/webhooks/velafi --key-file .velafi-selftest-key.pem
  ```

## Feedback

Found something wrong or missing in a skill? Open an issue in this repository. Issues are public: never include API keys, secrets, tokens, merchant IDs or transaction details. For account or integration support, contact VelaFi.

## License

Apache-2.0. See [LICENSE](LICENSE). The skills are provided as is; generated code may contain errors and is your responsibility to review.
