# Beneficiaries for payouts from the balance

Sources:
- https://docs.velafi.com/docs/guides/managing-beneficiaries.md
- https://docs.velafi.com/api-reference/beneficiary/add-beneficiary.md
- https://docs.velafi.com/api-reference/beneficiary/get-payment-templates#beneficiary-fields-by-payment-method

## How to build `fieldJson`

1. Call `GET /v2/payments/templates?paymentId=<id>`. **The runtime response is authoritative**; the tables below are a guide only.
2. Key each field by its `indexCode` when it is non-empty, otherwise by its `title` (the **Key** column below).
3. Dropdown fields take one of the option `code`s the template returns. Any other value is rejected with `-4010`.
4. A missing required field is rejected with `-4010`.

`POST /v2/payments` body: `merchantId` (always send; the merchant that holds the balance), `paymentId`, `country` (full name), `fiat`, `realName`, `fieldJson`, optional `remark`.

Under the same `merchantId` and `paymentId`, one receiving account number can have only one valid record. A duplicate returns `status` `3` with `sameAccountNumberId` = the existing valid record. Use that ID.

Beneficiary `status`: `1` valid (use for payouts), `2` authenticating, `3` failed (`failReason`).

## Keys by payout channel

### MXN SPEI (Finco Pay) `105`, country `Mexico`
| Key | `indexCode` | Required | Value |
|---|---|---|---|
| `Account Type` | none | Required | Dropdown (`clabe` or `debit` card) |
| `Account Number` | none | Required | Digits |
| `Beneficiary Name` | none | Required | Text |
| `Bank Code` | none | Optional | Dropdown; needed only for `debit` |

### MXN SPEI (Tesored) `72`, country `Mexico`
| Key | `indexCode` | Required | Value |
|---|---|---|---|
| `Account Type` | `accountType` | Required | Dropdown (`clabe` or `spei_card`) |
| `Full Name` | `fullName` | Required | Text |
| `Bank Code` | `bankCode` | Optional | Dropdown; needed only for `spei_card` |
| `Bank Account Number` | `bankAccountNumber` | Required | Letters and digits |

### ARS CBU/CVU (Momentum) `63` (sandbox `18`), country `Argentina`
| Key | `indexCode` | Required | Value |
|---|---|---|---|
| `Account Number` | `accountNumber` | Required | Text |
| `CUIT` | `cuit` | Required | Text |
| `Account Type` | `accountType` | Required | Dropdown |

The docs show older example key sets for this channel, so always build it from the live template. To look up the holder of a CVU/CBU or an alias before saving: `GET /v2/merchant/check/cvu` (https://docs.velafi.com/api-reference/beneficiary/check-cvu.md) and `GET /v2/merchant/check/alias` (https://docs.velafi.com/api-reference/beneficiary/check-alias.md). `check/cvu` returns `code` `0` and `msg` `success` on success, not `200`.

### COP Automatic ACH `68`, country `Colombia`
| Key | Required | Value |
|---|---|---|
| `Account Type` | Required | Dropdown (`cc` checking, `ch` savings, `dp` electronic deposit) |
| `Full Name` | Required | Text |
| `ID Document Type` | Required | Dropdown (`cc`, `nit`, `ce`, `pa`, `ppt`, `ti`, `rc`, `te`, `die`, `nd`) |
| `ID Document Number` | Required | Letters and digits |
| `Bank Code` | Required | Dropdown |
| `Bank Account Number` | Required | Letters and digits |

### COP Bre-B `69`, country `Colombia`
| Key | `indexCode` | Required | Value |
|---|---|---|---|
| `Breb Key` | `brebKey` | Required | Text |
| `Email` | `email` | Optional | Text |
| `Phone Number` | `phone` | Optional | Text |

### BRL Pix (Genial) `90` and Pix - Woovi (Avenia) `92`, country `Brazil`
| Key | `indexCode` (92 only) | Required | Value |
|---|---|---|---|
| `Pix Type` | `pixType` | Required | Dropdown: `CPF` (11 digits), `CNPJ` (14 digits), `EMAIL`, `PHONE` (10-11 digits), `RANDOM_KEY` (with `-`) |
| `Pix Key` | `pixKey` | Required | Text |

### PEN Bank Transfer `95`, country `Peru` (minimum payout 10 PEN)
| Key | Required | Value |
|---|---|---|
| `Bank Name` | Required | Dropdown |
| `Account Type` | Required | Dropdown |
| `Account Number` | Required | Digits |
| `CCI Number` | Optional | Digits |
| `Email` | Required | Text |
| `Identification Type` | Required | Dropdown |
| `Identification Number` | Required | Digits |
| `Name` | Required | Text |
| `Phone Number` | Required | Digits |

## Other beneficiary endpoints

- List Beneficiaries `GET /v2/payments`: https://docs.velafi.com/api-reference/beneficiary/get-beneficiary.md
- Delete Beneficiary: https://docs.velafi.com/api-reference/beneficiary/delete-beneficiary.md
- List Supported Payment Methods `GET /v2/payments/support/templates`: https://docs.velafi.com/api-reference/beneficiary/get-supported-payment-methods.md
