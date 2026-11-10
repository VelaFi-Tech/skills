# Currency account activation by channel

Endpoint for all channels: `POST /v2/merchant/accounts` with `merchantId` (string in the examples), `fiat`, `trench`, optional `fieldList`, optional `callbackUri` (Lead Bank only).

Sources:
- https://docs.velafi.com/docs/guides/activating-merchant-account.md
- https://docs.velafi.com/api-reference/merchant/activate-merchant-account-for-individual.md
- https://docs.velafi.com/api-reference/merchant/activate-merchant-account-for-business.md

The merchant must have passed KYC/KYB first (`status` `2` in List Merchants), otherwise `-5073`.

## Trench names

| `fiat` | `trench` | Rail | Payment IDs it gives (production) |
|---|---|---|---|
| MXN | `CLABE - FINCO PAY` | SPEI (Finco Pay) | `105` |
| MXN | `CLABE - TESORED` | SPEI (Tesored) | `72` |
| ARS | `CVU - Momentum` | CBU/CVU | `63` (sandbox `18`) |
| ARS | `QR Argentina` | 3.0 Transfer (QR) | `137` |
| COP | `COP Account` | PSE / ACH / Bre-B | `68`, `69` and others |
| BRL | `BANCO GENIAL` | Pix (Genial) | `90` |
| BRL | `Pix - Woovi` | Pix (Avenia) | `92` |
| PEN | `PEN Account` | Bank Transfer | `95` |
| USD / EUR | `Lead Bank` | ACH / Wire / SEPA | `81`-`85` |
| USD, HKD, EUR, SGD, NGN | `Circle Payment Network` | Payout only | `120`, `122`-`125`, `127` |

Always read the actual `paymentId` from `GET /v2/merchant/accounts` after activation.

## Individual merchants: `fieldList` and first status

| `trench` | `fieldList` (from the doc examples) | Status on first activation |
|---|---|---|
| `CLABE - FINCO PAY` | `alias` | `1` pending |
| `CLABE - TESORED` | `alias` | `1` pending |
| `CVU - Momentum` | `email`, `cuit`, `name`, `alias` | `1` pending |
| `QR Argentina` | `cuit` | `1` pending |
| `COP Account` | `alias` | `1` pending |
| `BANCO GENIAL` | none | `1` pending |
| `Pix - Woovi` | `personalInfo` object (see below); liveness first | `1` pending |
| `PEN Account` | `customerIdentificationType`, `customerIdentification`, `customerName`, `lastName`, `customerEmail`, `customerPhone` | `2` active immediately |
| `Lead Bank` | `email`, `firstName`, `lastName`; optional `callbackUri` | `4` incomplete + `verifyLink` (agreement) |
| `Circle Payment Network` | `accountName`, `nationality`, `idNumber`, `countryStateCode`, `city`, `street`, `postalCode`, `dateOfBirth`, `phoneNumber` | `2` active immediately |

### BRL Pix - Woovi for individuals

1. `POST /v2/merchant/woovi/liveness` with `merchantId` (merchant must be status `2` and have access to the channel). Response: `livenessUrl` (short-lived), `expiresAt` (Unix seconds), `status` `PENDING` / `COMPLETED` / `KYC_APPROVED` (channel already active). Send the merchant to `livenessUrl`. Call again for a new URL after expiry (`generateNewLiveness` is ignored).
   Doc: https://docs.velafi.com/api-reference/merchant/get-woovi-liveness-url.md
2. Upload the ID document images with `POST /v2/base/file/upload` (`multipart/form-data`, up to 5 files, 10 KB to 3 MB each, `jpg`/`jpeg`/`png`/`pdf`). Use the returned `fileUrl` (relative path), not `tempFileUrl`.
   Doc: https://docs.velafi.com/api-reference/basic-configuration/upload-file.md
3. Activate with `trench: "Pix - Woovi"` and `fieldList.personalInfo`: `firstName`, `lastName`, `email`, `taxIdentificationNumber` (letters and digits only), `nationality`, `dateOfBirth` (`yyyy-MM-dd`, at least 18), `street1`, `city`, `countryStateCode` (e.g. `BR-SP`), `postcode`, `idType` (`1` ID card, `2` driver's license, `3` passport), `govIdCountryAbbr`, `govIdFrontUrl` and `govIdBackUrl` (both required, both `fileUrl` values; public URLs are rejected).
4. Without a completed liveness check the activation fails with `-5059` (`Please first pass the Liveness authentication`). Then poll List Merchant Accounts until `2`.

### Lead Bank: calling again

| Situation | Status returned |
|---|---|
| Verification not finished and can be resumed | `4` with a new `verifyLink` |
| Verification not rejected and does not need redoing | `3` with `failReason` `Kyc is on processing or completed` |

Activating `EUR` via Lead Bank also enables `USD` through the same account.

## Business merchants

For `CLABE - FINCO PAY`, `CLABE - TESORED`, `COP Account`, `CVU - Momentum`, `QR Argentina`, `BANCO GENIAL` and `PEN Account`, a business activation normally returns `status: 0` with a `verifyLink` for an additional KYB verification of that channel. Send the business to the link. After VelaFi approves it, the channel opens automatically; do not call the endpoint again. On this path the `fieldList` is not used.

If VelaFi has enabled direct activation for the account, the channel opens from the request and `fieldList` must contain:

| `trench` | Required `fieldList` |
|---|---|
| `CLABE - FINCO PAY` | `alias` (up to 40 characters) |
| `CLABE - TESORED` | `alias` (up to 64 characters) |
| `COP Account` | `alias` (up to 64 characters) |
| `CVU - Momentum` | `cuit`, `name`; `alias` optional |
| `QR Argentina` | `cuit` (up to 40 characters) |
| `PEN Account` | `customerIdentificationType`, `customerIdentification`, `customerName`, `customerEmail`, `customerPhone` (digits only, up to 9) |
| `BANCO GENIAL` | none |

`Pix - Woovi` for businesses needs `fieldList.companyInfo` (company details, address, purpose, source of funds, size, revenue and volume, registration and tax numbers, and `fileUrl`s for the tax identification document and certificate of incorporation) and `fieldList.companyUbosInfo` (array of UBOs with identity, address, ownership and government ID `fileUrl`). Copy the full field list from the Activate Business page; do not guess field names.

`Lead Bank` for businesses: `fieldList` with `email`, `companyName`; returns `4` + `verifyLink` for the agreement.

Some channels need extra documents. The docs direct developers to contact@velafi.com for the full document list per country and account type.

## Activation status

`0` initialized (with `verifyLink`: business verification needed), `1` pending, `2` active, `3` failed (`failReason`), `4` incomplete (finish the steps at `verifyLink`).

## Errors instead of a status

| Code | When |
|---|---|
| `-5074` | Channel already active for this merchant |
| `-5062` | Channel activation already pending |
| `-5076` | Channel closed |
| `-5078` | Channel disabled |
| `-5079` | No activation permission for this channel |
| `-5073` | Merchant has not passed KYC |
| `-5077` | Merchant disabled |
| `-4010` | Required `fieldList` field missing or invalid |
| `-5059` | Provider could not register the merchant (channel recorded as failed, `3`); for `Pix - Woovi`, liveness not complete |
| `-5066` | `Pix - Woovi` only: already under review |
| `-5067` | `Pix - Woovi` only: already active |
