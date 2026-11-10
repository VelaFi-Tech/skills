# Crypto wallet endpoints

All endpoints need the `X-BH-TOKEN` header; POST bodies are JSON (`Content-Type: application/json`). Base URL `https://api.velafi.com` (sandbox `https://api-test.velafi.com`).

| Purpose | Method and path | Doc |
| --- | --- | --- |
| Balances | `GET /v2/assets/account/assets` | https://docs.velafi.com/api-reference/merchant/get-crypto-assets-balance.md |
| Deposit address | `GET /v2/assets/depositAddress` | https://docs.velafi.com/api-reference/merchant/get-crypto-deposit-address.md |
| Deposit history | `GET /v2/assets/depositOrders` | https://docs.velafi.com/api-reference/crypto-wallet/get-crypto-deposit-history.md |
| Withdrawal quota | `GET /v2/assets/withdrawQuota` | https://docs.velafi.com/api-reference/crypto-wallet/get-withdrawal-quota.md |
| Add whitelist address | `POST /v2/user/whitelistAddress` | https://docs.velafi.com/api-reference/crypto-wallet/add-whitelist-address.md |
| List whitelist | `GET /v2/user/whitelistAddress` | https://docs.velafi.com/api-reference/crypto-wallet/get-whitelist-addresses.md |
| Delete whitelist entry | `DELETE /v2/user/whitelistAddress/{addressId}` | https://docs.velafi.com/api-reference/crypto-wallet/delete-whitelist-address.md |
| Create withdrawal | `POST /v2/assets/withdraw` | https://docs.velafi.com/api-reference/crypto-wallet/create-crypto-withdrawal.md |
| Withdrawal history | `GET /v2/assets/withdrawalOrders` | https://docs.velafi.com/api-reference/crypto-wallet/get-crypto-withdrawal-history.md |
| Internal transfer | `POST /v2/assets/internalTransfer` | https://docs.velafi.com/api-reference/merchant/crypto-transfer.md |
| Internal transfer history | `GET /v2/assets/internalTransferOrders` | https://docs.velafi.com/api-reference/merchant/query-crypto-transfers.md |

## Balances

Query `merchantId` (required; `0` = sum of all merchants on the account). Response `data.canDeposit` and `data.balances[]` with `asset`, `assetId`, `assetName`, `total`, `free`, `locked`.

## Deposit address

Query `tokenId`, `chainType`, `merchantId` (all required). Response: `allowDeposit`, `address`, `addressExt`, `minQuantity`, `needAddressTag`, `requiredConfirmNum` (confirmations before credit), `canWithdrawConfirmNum` (confirmations before withdrawable), `tokenType`. If `allowDeposit` is `false`, funds sent may not be credited.

| tokenId | chainType | Network |
| --- | --- | --- |
| `USDT` | `TRC20` | Tron |
| `USDT` | `ERC20` | Ethereum |
| `USDT` | `BEP20` | BNB Smart Chain |
| `USDT` | `POL` | Polygon |
| `USDT` | `SPL20` | Solana |
| `USDC` | `ERC20` | Ethereum |
| `USDC` | `POL` | Polygon |
| `USDC` | `SPL20` | Solana |
| `BTC` | `BTC` | Bitcoin |
| `COPM` | `POL` | Polygon (POS) |
| `BRL1` | `POL` | Polygon (POS) |
| `MXNB` | `Arbitrum` | Arbitrum |
| `MMXN` | `ERC20` | Ethereum |
| `MMXN` | `TRC20` | Tron |

## Deposit history

Query (all optional): `merchantId`, `crypto`, `txId`, `startTime`, `endTime` (ms), `pageSize` (1-1000, default 10). Newest first; narrow the time window to look further back. Items: `orderId`, `merchantId`, `time`, `crypto`, `cryptoAmount`, `fromAddress`, `status` (`1` in progress, `2` successful, `3` failed/cancelled, `4` other), `txId`, `txIdUrl`. Note: `address` currently returns the sending address, not your deposit address.

## Withdrawal quota

Query `crypto` (required), `chainType` (optional). Response: `crypto`, `minCryptoAmount` (`0` = no minimum, external addresses), `chainTypeInfo[]` with `chainType`, `allowWithdraw` (`false` = external withdrawals rejected; `true` does not guarantee acceptance), `fee`, `feeCrypto` (same as `crypto`). Errors: `Token not found`, `Chain type not found`.

## Whitelist

Add body: `crypto` (enabled token), `chainType`, `address` (must be valid for the network), `addressTag` (optional; withdrawals must then use the same tag), `remark`. A duplicate of the same `crypto`/`chainType`/`address`/`addressTag` is rejected. Returns `addressId`.

List query: `crypto`, `chainType`, `address`, `addressTag`, `currentPage` (default 1), `pageSize` (1-1000, default 10). Delete returns `data: true`; API withdrawals to that address are rejected afterwards.

## Create withdrawal

Body: `merchantId`, `clientId` (required), `crypto`, `chainType`, `address`, `addressTag` (optional), `cryptoAmount` (> 0), `remark` (optional). Response `data.orderId`.

- Rejected unless an active whitelist entry matches `address`, `chainType`, `addressTag` and covers `crypto`. Account controls such as a withdrawal freeze can also reject it.
- Reusing a `clientId` of the same kind (external or VelaFi destination) for this merchant: `Duplicate withdrawal request`.
- Counts toward the merchant's crypto limit; over-limit requests are rejected.
- External addresses only:
  - amount truncated to the token's decimal precision;
  - must exceed the network fee, else `The quantity cannot be less than the handling fee`;
  - must be at least `minCryptoAmount` when > 0, else `Order amount is too small`;
  - above the token's maximum single amount: `The quantity cannot exceed the maximum quantity`;
  - `allowWithdraw` false: `Withdrawals are temporarily unavailable due to system maintenance.`
- VelaFi wallet addresses: no on-chain transaction, zero fee, booked as an internal transfer; appears in internal transfer history, not withdrawal history, and sends no `CRYPTO_WITHDRAW_WEBHOOK`.

## Withdrawal history

Query `merchantId` (required), `crypto`, `clientId`, `startTime`, `endTime`, `pageSize` (1-1000). Items: `orderId`, `merchantId`, `time`, `crypto`, `address`, `addressTag`, `cryptoAmount`, `fee`, `feeCrypto`, `arriveCryptoAmount`, `status`, `txId`, `txIdUrl`, `remark`.

`status`: `5` in progress (including VelaFi internal audit), `6` successful, `7` failed, `9` cancelled, `0` other (for example sub-account approval or RFI). The list can include mass payout items and stablecoin payment refunds (refunds do not send the webhook).

## Internal transfer

Body: `fromMerchantId`, `toMerchantId`, `tokenId` (`USDT`, `USDC`, `BTC`, `MMXN`), `amount`, `clientId` (optional but always send it). Response: `id`, `tokenId`, `amount` (negative = sender debit), `clientId`, `merchantId`, `fromMerchantId`, `toMerchantId`. Reused `clientId` from the same sender: `-4040` `Duplicate withdrawal request`, no second transfer.

History query: `merchantId`, `tokenId`, `clientId`, `startTime`, `endTime`, `pageSize`. Each transfer produces two records; `merchantId` tells you whose side the record is.
