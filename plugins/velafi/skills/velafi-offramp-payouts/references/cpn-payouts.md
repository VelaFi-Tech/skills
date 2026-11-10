# Payouts through Circle Payment Network (CPN)

Sources: https://docs.velafi.com/docs/use-cases/payouts-funded-by-stablecoins.md, https://docs.velafi.com/docs/payment-methods.md, https://docs.velafi.com/api-reference/merchant/activate-merchant-account-for-business.md, https://docs.velafi.com/api-reference/merchant/activate-merchant-account-for-individual.md, https://docs.velafi.com/api-reference/beneficiary/get-payment-templates.md

CPN is **payout only**: no collections, no `fiat_to_crypto` orders. A CPN account supports USD, HKD, EUR, SGD and NGN. Do not offer other currencies on CPN.

## Steps

1. **Activate a CPN account** for the merchant and currency with `POST /v2/merchant/accounts` and `"trench": "Circle Payment Network"`. A business merchant sends only `merchantId`, `fiat` and `trench`. An individual merchant must also send a `fieldList` with `accountName`, `nationality`, `idNumber`, `countryStateCode`, `city`, `street`, `postalCode`, `dateOfBirth` and `phoneNumber` (see the individual activation page).
2. **Register the beneficiary** on a CPN payment method (`POST /v2/payments`, fields from `GET /v2/payments/templates?paymentId=...`).
3. **Create the `crypto_to_fiat` order** with `fiat` set to the CPN currency and the CPN beneficiary's `userPaymentId`, the same way as any payout.

A CPN order can go into risk review (`11`). Upload the requested documents with `POST /v2/order/invoice`; the order moves to `12` and waits for a decision.

## CPN payment methods

| `paymentId` | Name | Currencies |
| --- | --- | --- |
| `120` | Wire (CPN) | USD, EUR, HKD |
| `122` | FPS (CPN) | HKD |
| `123` | CHATS (CPN) | USD, HKD |
| `124` | SEPA (CPN) | EUR |
| `125` | BANK-TRANSFER (CPN) | SGD, NGN |
| `127` | FEDWIRE (CPN) | USD |

## Beneficiary fields

All CPN templates share these keys (send the `indexCode` or the title as the key):

| Key (`indexCode`) | Required | Value |
| --- | --- | --- |
| `beneficiaryName` | Yes | Text |
| `country` (title "Nationality") | Yes | ISO 3166-1 alpha-2 |
| `stateProvince` (title "Country of Residence") | Yes | ISO 3166-2, e.g. `US-CA` |
| `city`, `street`, `postalCode` | Yes | Text |
| `dateOfBirth` | No | `yyyy-MM-dd` (date of birth or incorporation) |
| `idNumber` | No | ID number or tax ID |
| `idExpirationDate` | No | `yyyy-MM-dd` |
| `useCase` | Yes | Dropdown: an option `code` |
| `reasonForPayment` | Yes | Dropdown: an option `code` |

Plus, per method:

| Method | Additional required keys |
| --- | --- |
| `120` Wire | `bankName`, `bankCountry`, `swiftCode`, `accountNumber` |
| `122` FPS | `recipientEmail`, `recipientPhoneNumber` (international dialing code), `fpsId`, `bankCode`, `accountNumber` |
| `123` CHATS | `bankCode`, `bankName`, `swiftCode`, `accountNumber`, `recipientCity`, `recipientAddressStreet`, `recipientAddressCity`, `recipientAddressCountry`, `recipientAddressStateProvince`, `recipientAddressPostalCode` |
| `124` SEPA | `bankName`, `bankCountry`, `swiftCode`, `accountNumber` (the IBAN) |
| `125` Bank Transfer | `bankName`, `bankCountry`, `swiftCode`, `accountNumber` |
| `127` FEDWIRE | `bankName`, `bankCountry`, `accountNumber`, `routingNumber`, `recipientCity`, `recipientAddressStreet`, `recipientAddressCity`, `recipientAddressCountry`, `recipientAddressStateProvince`, `recipientAddressPostalCode` |

A request that omits a required field, or sends a dropdown value that is not an option `code`, is rejected with `-4010`. The template endpoint's response is authoritative at runtime; fetch it rather than hardcoding.
