# Virtual account channels: `fieldList` keys and payer instructions

Source: https://docs.velafi.com/docs/use-cases/collect-with-virtual-accounts.md and
https://docs.velafi.com/api-reference/merchant/get-pending-fund-account#fieldlist-keys-by-payment-method

## Channels, alias rules and initial status

| Currency | `paymentId` | Channel | Alias rule | Status right after create |
|---|---|---|---|---|
| MXN | `105` | SPEI (Finco Pay) | Letters and digits, up to 64 | `1` pending |
| MXN | `72` | SPEI (Tesored) | Letters and digits, up to 64 | `1` pending |
| ARS | `63` | CBU/CVU (Momentum) | Letters and digits, up to 64 | `2` active |
| COP | `68` | Automatic ACH (payment link) | 6 to 21 uppercase letters or digits | `1` pending |
| COP | `69` | Bre-B | 6 to 21 uppercase letters or digits | `1` pending |
| BRL | `90` | Pix (Genial) | Letters and digits, up to 64 | `1` pending |
| BRL | `92` | Pix - Woovi (Avenia) | Letters and digits, up to 64 | `1` pending |

- `default` (any letter case) is reserved.
- A request is rejected if the same merchant already has a pending or active virtual account with the same `fiat`, `paymentId` and `alias` (`-5085` pending, `-5086` active).
- Virtual account status: `1` pending/authenticating, `2` active, `3` failed.
- Read `paymentId` from `GET /v2/merchant/accounts` for the environment you are in; sandbox IDs can differ.

## `fieldList` keys by channel

`GET /v2/merchant/virtual/addfunds` returns the same keys as `GET /v2/merchant/addfunds`. It takes no `amount`, so it never returns a deposit-specific QR or `txId`.

| `paymentId` | Keys | Notes |
|---|---|---|
| `105` SPEI (Finco Pay) | `Cuenta CLABE` | The CLABE |
| `72` SPEI (Tesored) | `clabeNumber` | The CLABE |
| `63` CBU/CVU (Momentum) | `CVU Number`, `CUIT`, `Alias` | `Alias` can be empty |
| `68` Automatic ACH | `alias`, `paymentLink` | `alias` can be empty |
| `69` Bre-B | `brebKey` | Listing works only after the merchant's Bre-B key exists |
| `90` Pix (Genial) | `Chave Pix - Random Pix`, `Pix copia e cola`, `Pix QR Code` | `Pix copia e cola` only when the merchant has a Pix QR code |
| `92` Pix - Woovi (Avenia) | `pixKey`, `qrCodeLink`, `qrCode` | `pixKey` omitted when there is none |

QR image links expire one hour after the response. Call the endpoint again for a fresh link each time you display it.

## What the payer does

| Rail | Payer action |
|---|---|
| MXN SPEI (`105`, `72`) | Sends a SPEI transfer to the CLABE (`Cuenta CLABE` or `clabeNumber`). |
| ARS CBU/CVU (`63`) | Sends a bank transfer to the `CVU Number` (or its `Alias`, when present). |
| COP Automatic ACH (`68`) | Opens the `paymentLink` and pays. |
| COP Bre-B (`69`) | Sends a Bre-B transfer to the `brebKey`. |
| BRL Pix Genial (`90`) | Pays to the Pix key (`Chave Pix - Random Pix`), the copy-and-paste code, or the QR code. |
| BRL Pix Woovi (`92`) | Pays the static Pix QR (`qrCodeLink`, `qrCode`) or the `pixKey`, when present. |

## Error codes seen in this flow

| Code | Meaning | Action |
|---|---|---|
| `-5084` | The currency account's channel does not support multiple virtual accounts | Use a supported channel |
| `-5085` | Alias already exists and is pending | Poll List Virtual Accounts |
| `-5086` | Alias already exists and is active | Read its details; do not recreate |
| `-5079` | Account not enabled for that currency and channel | Check the merchant account |
| `-5071` | Merchant's currency account on that channel not active | Activate it first (`velafi-onboard-merchants`) |

Full list: https://docs.velafi.com/docs/error-codes.md
