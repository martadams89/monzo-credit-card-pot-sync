# Monzo Credit Card Pot Sync

![GitHub Release](https://img.shields.io/github/v/release/mattgogerly/monzo-credit-card-pot-sync?include_prereleases)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mattgogerly/monzo-credit-card-pot-sync/build.yml?branch=main)
![Coveralls](https://img.shields.io/coverallsCoverage/github/mattgogerly/monzo-credit-card-pot-sync?branch=main)

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
- **Detailed Logging:** Every step—from token refreshes to pot adjustments and cooldown checks—is logged for visibility and troubleshooting.
- **Log History in the Web UI:** The **Logs** page shows each sync run's output with search, level filtering and a period picker. Back-to-back runs with identical output are grouped into one entry (e.g. "×720 identical runs"), lines that changed since the previous group are highlighted, and **Only what changed** turns the history into a timeline of changes. History is kept for 7 days by default (**Log History (days)** in Settings).

## Extended Logic for Credit Card Providers

For American Express and Lloyds, pending transactions are taken into account to calculate the true balance: pending charges are added, and pending refunds and payments are taken off, so the pot is neither short while a charge is pending nor over-funded while a refund is pending. Each Amex or Lloyds connection has a **Count pending refunds & payments** toggle on the Accounts page (on by default): switch it off for a connection if its provider takes a payment off the balance while it is still pending, which would otherwise count it twice. Barclaycard adds pending charges to its balance quickly, so its reported balance is used as is. Halifax balances are worked out as credit limit minus available credit.

A card that is in credit (overpaid, or with pending refunds larger than what is owed) counts as £0 owed, so it never reduces the amount set aside for your other cards.

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

When setting up Monzo or TrueLayer redirect URLs, use the URL that was set in the `POT_SYNC_LOCAL_URL` variable to enable the accounts to successfully link.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For any questions or feedback, please open an issue on GitHub.
