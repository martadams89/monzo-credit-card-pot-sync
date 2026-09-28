# Monzo Credit Card Pot Sync

![GitHub Release](https://img.shields.io/github/v/release/martadams89/monzo-credit-card-pot-sync?include_prereleases)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/martadams89/monzo-credit-card-pot-sync/build.yml?branch=main)
![Coveralls](https://img.shields.io/coverallsCoverage/github/martadams89/monzo-credit-card-pot-sync?branch=main)

This project provides a robust system to keep your Monzo pot in sync with your credit card spending. It allows you to spend on your credit cards day-to-day while ensuring there are always enough funds in your Monzo pot to pay off bills. The system supports multiple credit card providers and seamlessly manages personal, joint, and business Monzo accounts.

## Features

- **Automatic Fund Management:** Automatically deposits to or withdraws from your selected Monzo pot to match your credit card spending.
- **Flexible Pot Selection:** Easily choose and switch the designated Monzo pot that stays in sync.
- **Multiple Provider Support:** Connect various credit cards. Providers such as American Express and Barclaycard now include pending transaction calculations.
- **Multiple Connections per Provider:** Connect two or more independently authorised cards from the same provider, with a separate Monzo pot mapping for each connection.
- **Multi-Account Support:** Sync funds across personal, joint, and business Monzo accounts.
- **Cooldown & Override Logic:**  
  - **Normal Operations:**  
    - When you spend on a card, the pot is increased to match the new card balance.
    - If the pot balance exceeds your card balance, the excess is automatically withdrawn.
  - **Cooldown Scenario:**  
    - When the pot falls below the card balance with no new spending detected (perhaps due to a direct payment from the pot), a cooldown period is triggered.
    - Once the cooldown expires and if the card balance remains above the pot, the shortfall is deposited automatically.
  - **Override Spending:**  
    - If override spending is enabled while a cooldown is active and the card balance increases, the additional difference is deposited immediately.
    - The original shortfall remains under cooldown and will be addressed upon expiration.
- **Dashboard:** The home page shows each card's balance, its pot, whether the pot is in sync (or short/over and by how much), any cooldown and when it ends, and when the last sync ran. Until everything is connected it shows a setup checklist instead. **Sync now** runs a sync straight away.
- **Per-card Cooldown:** Each card can have its own cooldown on the Accounts page (for example 72 hours for a direct debit that takes a day or more to clear), falling back to **Deposit Cooldown** in Settings.
- **Reconnect Reminders:** Open banking consent lasts at most 90 days. Pot Sync reads each card's expiry from TrueLayer, shows it on the Accounts page and dashboard, and sends a Monzo notification (at most once a day) in the week before it runs out. **Reconnect** re-authorises the existing connection, keeping its pot and settings.
- **Optional Sign In:** Off by default for installs behind a reverse proxy that already handles sign in. Turn it on under **Settings > Security** to require a password, optionally with an authenticator app (2FA), and add passkeys (Face ID, Touch ID, Windows Hello, security keys) to sign in without a password. See [Security](#security).
- **Health Check:** `GET /health` returns 200 while syncs are completing and 503 when none has finished recently, for Docker (the image has a `HEALTHCHECK`) or an uptime monitor.
- **Detailed Logging:** Every step—from token refreshes to pot adjustments and cooldown checks—is logged for visibility and troubleshooting.
- **Log History in the Web UI:** The **Logs** page shows each sync run's output with search, level filtering and a period picker. Back-to-back runs with identical output are grouped into one entry (e.g. "×720 identical runs"), lines that changed since the previous group are highlighted, and **Only what changed** turns the history into a timeline of changes. History is kept for 7 days by default (**Log History (days)** in Settings).

## Extended Logic for Credit Card Providers

For American Express and Lloyds, pending transactions are taken into account to calculate the true balance: pending charges are added, and pending refunds and payments are taken off, so the pot is neither short while a charge is pending nor over-funded while a refund is pending. Each Amex or Lloyds connection has a **Count pending refunds & payments** toggle on the Accounts page (on by default): switch it off for a connection if its provider takes a payment off the balance while it is still pending, which would otherwise count it twice. Barclaycard adds pending charges to its balance quickly, so its reported balance is used as is. Halifax balances are worked out as credit limit minus available credit.

A card that is in credit (overpaid, or with pending refunds larger than what is owed) counts as £0 owed, so it never reduces the amount set aside for your other cards.

## Security

Sign in is **off** by default. Leave it off only if something in front of Pot Sync, such as a reverse proxy with authentication, already controls who can reach it; otherwise anyone who can open the page can move money between your pots and read your settings.

To turn it on, open **Settings > Security**, set a password, then press **Turn on sign in**. From there you can also:

- **Two-factor authentication:** scan the QR code with an authenticator app and confirm a code. Signing in with the password then also asks for a code.
- **Passkeys:** add one or more passkeys. A passkey signs in on its own (it already checks your face, fingerprint or device PIN). Passkeys are tied to the host in `POT_SYNC_LOCAL_URL` and need https (or `localhost`), so set that variable to the address you open Pot Sync on.

Five wrong passwords or codes pause sign in from that address for 15 minutes (behind a reverse proxy, set `POT_SYNC_TRUSTED_PROXIES` so this applies per visitor rather than to the proxy). Adding or removing a passkey, changing the password, turning off 2FA or turning off sign in all ask for the current password. Changing the password or turning sign in off signs out every other session.

**Locked out?** Restart Pot Sync with the environment variable `POT_SYNC_DISABLE_AUTH=true`. Sign in is skipped and **Settings > Security** lets you reset the password, 2FA and passkeys without the old password. Remove the variable and restart afterwards.

Session cookies are signed with `SECRET_KEY` if you set it; otherwise a random key is generated on first start and kept in the database. Client secrets saved in Settings are never sent back to the browser: leave a secret field blank to keep the saved value.

## Upgrade Notice

Existing databases are upgraded automatically. Connected accounts, tokens, pot mappings, cooldowns, and balance history are retained.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/mattgogerly/monzo-credit-card-pot-sync.git
    ```
2. Navigate to the project directory:
    ```bash
    cd monzo-credit-card-pot-sync
    ```
3. Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4. Install web dependencies:
    ```bash
    npm install
    ```
5. Build static web assets:
    ```bash
    npm run build-css
    ```

## Usage

1. Start the application:
    ```bash
    npm start
    ```
2. Open your browser and navigate to `http://localhost:1337`

## Configuration

1. Log in to the Monzo developer portal at `https://developers.monzo.com` (note you'll need to approve the login in the app)
2. Create a client, entering the redirect URL as `http://localhost:1337/auth/callback/monzo` and confidentiality as `Confidential`
3. Make a note of the client ID and client secret
4. Login to the TrueLayer console at `https://console.truelayer.com`
5. Create an application
6. Switch to the `Live` environment and add `http://localhost:1337/auth/callback/truelayer` as a redirect URI
7. Copy the client ID and client secret
8. Navigate to `http://localhost:1337/settings` and save the Monzo and TrueLayer client IDs and secrets
9. When prompted, accept the notification from Monzo to allow the application API access.

## Docker

Releases are also published as container images on GitHub Container Registry.

1. Start the container:
   ```bash
   docker compose up -d
   ```

### Using a Reverse Proxy

If you are using a reverse proxy, set the environment variable `POT_SYNC_LOCAL_URL` in your Docker Compose file or Docker run command to the external URL of your application. For example:

```yaml
environment:
  - POT_SYNC_LOCAL_URL=https://subdomain.fulldomain.com
```

When setting up Monzo or TrueLayer redirect URLs, use the URL that was set in the `POT_SYNC_LOCAL_URL` variable to enable the accounts to successfully link. The same URL is used for passkeys, and when it starts with `https://` the session cookie is marked secure.

### Environment variables

| Variable | Purpose |
| --- | --- |
| `POT_SYNC_LOCAL_URL` | The URL you open Pot Sync on. Used for OAuth callbacks and passkeys. Default `http://localhost:1337`. |
| `DATABASE_URI` | SQLAlchemy database URL. Defaults to a SQLite file in the app folder. |
| `SECRET_KEY` | Signs session cookies. Optional; generated and stored if unset. |
| `POT_SYNC_DISABLE_AUTH` | Set to `true` to skip sign in temporarily if you're locked out. |
| `POT_SYNC_TRUSTED_PROXIES` | Number of reverse proxies in front of Pot Sync (usually `1`). Trusts their `X-Forwarded-For`/`-Proto`/`-Host` headers so sign-in throttling applies per visitor and https is detected. Leave unset if Pot Sync is reached directly. |

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For any questions or feedback, please open an issue on GitHub.
