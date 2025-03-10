# Monzo Credit Card Pot Sync

![GitHub Release](https://img.shields.io/github/v/release/martadams89/monzo-credit-card-pot-sync?include_prereleases)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/martadams89/monzo-credit-card-pot-sync/ci.yml?branch=main)
![License](https://img.shields.io/github/license/martadams89/monzo-credit-card-pot-sync)

> This project is based on [mattgogerly/monzo-credit-card-pot-sync](https://github.com/mattgogerly/monzo-credit-card-pot-sync) with additional security features and performance improvements.

A powerful system to automatically keep your Monzo pots synchronized with credit card balances. This ensures you always have enough funds set aside to pay your credit card bills, supporting multiple credit card providers and both personal and joint Monzo accounts.

## Features

- **Automatic Fund Management:** Sync your Monzo pot balance with your credit card spending automatically.
- **Multiple Credit Card Support:** Connect various credit cards (American Express, Barclaycard, and more).
- **Joint Account Support:** Works with both personal and joint Monzo accounts.
- **Pending Transaction Tracking:** Includes pending transactions in balance calculations for supported providers.
- **Enhanced Security:**
   - Passkey (WebAuthn) support for passwordless login.
   - Two-factor authentication (TOTP).
   - Email verification.
- **Docker & Kubernetes Ready:** Easy deployment options with detailed guides.
- **Dark Mode Support:** Responsive UI with dark mode toggle.

## How It Works

The system uses sophisticated logic to ensure your Monzo pot always has enough money to cover your credit card balance.

### Normal Operations
- When you spend on a credit card, the system automatically deposits money into your designated Monzo pot to match the new card balance.
- If your pot balance exceeds your card balance (e.g., after making a payment to your credit card), the excess is automatically withdrawn.

### Cooldown Logic
- If your pot balance falls below your credit card balance without new spending detected (e.g., due to a direct payment from the pot), the system enters a cooldown period.
- This prevents continuous back-and-forth transfers when you're actively managing your finances.
- Once the cooldown expires (default: 3 hours), if the shortfall still exists, the system deposits the required amount.

### Override Spending
- If the "override cooldown spending" setting is enabled, new spending on your card while in a cooldown will trigger an immediate deposit for the additional amount spent.
- This ensures your pot always keeps up with new spending, while the original shortfall remains under cooldown.

## Setup and Installation

### Prerequisites

- Python 3.9+ (for manual installation)
- Docker and Docker Compose (for containerized installation)
- Node.js and npm (for CSS building)
- Monzo account
- Credit card(s) supported by TrueLayer (American Express, Barclaycard, etc.)
- Email account for notifications (optional)

### Using Docker (Recommended)

1. Clone the repository:
    ```bash
    git clone https://github.com/martadams89/monzo-credit-card-pot-sync.git
    cd monzo-credit-card-pot-sync
    ```

2. Create environment file:
    ```bash
    cp .env.example .env
    # Edit .env file with your settings
    ```

3. Build CSS assets (required for the UI):
    ```bash
    npm install
    npm run build:css
    ```

4. Start the container:
    ```bash
    docker compose up -d
    ```

5. Access the application:
    Open `http://localhost:8000` in your web browser.

### Manual Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/martadams89/monzo-credit-card-pot-sync.git
    cd monzo-credit-card-pot-sync
    ```

2. Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4. Install web dependencies and build CSS:
    ```bash
    npm install
    npm run build:css
    ```

5. Start the application:
    ```bash
    flask run
    ```

## CSS Development and Building

The application uses Tailwind CSS for styling. CSS files are built automatically in several ways:

### In Docker Container
- The CSS is built during Docker image creation using `npm run build:css`.
- An additional build occurs at container startup via the entrypoint script.

### For Local Development

You can build the CSS in two ways:

1. Using npm:
    ```bash
    npm install
    npm run build:css
    ```

2. Using development mode with auto-reload:
    ```bash
    npm run watch:css
    ```

The compiled CSS will be available at `app/static/css/dist/output.css`.

## Database Migrations

Database migrations run automatically when the application starts. No manual steps are required for setup or migration.

### First-Time Setup

- The database will be automatically created.
- All required tables will be set up.
- Migrations will run to keep the schema up to date.

### Upgrading from Previous Versions

1. **Back up your database** before upgrading.
2. Stop the old version of the application.
3. Deploy the new version.
4. Start the new version—migrations will run automatically.
5. Check the application logs to confirm successful migrations.

## Environment Variables

The application is configured through environment variables in the `.env` file:

| Variable                | Description                                         | Default                       | Required |
|-------------------------|-----------------------------------------------------|-------------------------------|----------|
| FLASK_APP               | Flask application entry point                       | app.wsgi:app                  | Yes      |
| FLASK_ENV               | Environment mode (development/production)           | production                    | Yes      |
| SECRET_KEY              | Secret key for session encryption                   | -                             | Yes      |
| BASE_URL                | Base URL for callbacks and emails                   | http://localhost:8000         | Yes      |
| MONZO_CLIENT_ID         | Monzo API client ID                                 | -                             | Yes      |
| MONZO_CLIENT_SECRET     | Monzo API client secret                             | -                             | Yes      |
| TRUELAYER_CLIENT_ID     | TrueLayer API client ID                             | -                             | Yes      |
| TRUELAYER_CLIENT_SECRET | TrueLayer API client secret                         | -                             | Yes      |
| MAIL_SERVER             | SMTP mail server                                    | -                             | No       |
| MAIL_PORT               | SMTP port                                           | 587                           | No       |
| MAIL_USE_TLS            | Use TLS for SMTP                                    | true                          | No       |
| MAIL_USERNAME           | SMTP username                                       | -                             | No       |
| MAIL_PASSWORD           | SMTP password                                       | -                             | No       |
| MAIL_DEFAULT_SENDER     | Default sender email                                | noreply@example.com           | No       |
| ADMIN_EMAIL             | Administrator email                                 | admin@example.com             | No       |
| LOG_LEVEL               | Logging level                                       | INFO                          | No       |
| DATABASE_URL            | Database connection string                          | sqlite:///app.db              | No       |

**Note:** The application automatically constructs redirect URIs for Monzo and TrueLayer using the BASE_URL. For example, if BASE_URL is set to `https://example.com`, the redirect URIs will be `https://example.com/auth/callback/monzo` and `https://example.com/auth/callback/truelayer`.

## API Configuration

### API Client Setup

1. **Monzo API Setup:**
    - Log in to the Monzo developer portal at [https://developers.monzo.com](https://developers.monzo.com).
    - Create a client with a redirect URL matching your environment (e.g., `https://your-domain.com/auth/callback/monzo` or `http://localhost:8000/auth/callback/monzo`).
    - Set confidentiality to Confidential and note the client ID and secret.

2. **TrueLayer API Setup:**
    - Log in to the TrueLayer console at [https://console.truelayer.com](https://console.truelayer.com).
    - Create an application and switch to the Live environment.
    - Add a redirect URI matching your environment (e.g., `https://your-domain.com/auth/callback/truelayer` or `http://localhost:8000/auth/callback/truelayer`).
    - Copy the client ID and client secret.

3. **Save in Application:**
    - Navigate to Settings in the application.
    - Save the Monzo and TrueLayer client IDs and secrets.
    - Accept the notification from Monzo to allow API access when prompted.

### Using a Reverse Proxy or Custom Domain

If deploying behind a reverse proxy or using a custom domain, set the BASE_URL environment variable to your external URL. This ensures the application generates correct callback URLs for Monzo and TrueLayer.

## Troubleshooting

- **CSS Not Loading:**
   - Ensure you've built the CSS using `npm run build:css`.
   - Verify that `app/static/css/dist/output.css` exists.
   - Check file permissions.

- **Docker Permission Issues:**
   - If encountering permission errors with Docker volumes, try adjusting the file or volume permissions.

- **Database Errors:**
   - Check logs for migration-related messages.
   - To reset the database, delete `app.db` and restart the application.

- **API Connection Issues:**
   - Confirm Monzo and TrueLayer API credentials.
   - Ensure redirect URLs match exactly.
   - Check for token refresh requirements.

- **Email Notification Issues:**
   - Verify proper SMTP settings.
   - Some providers may require specific API keys or settings like "Allow less secure apps."
   - Check for any rate limiting by your email provider.

For more troubleshooting help, please open an issue on GitHub.

## Security Considerations

- Utilizes OAuth 2.0 for authentication with Monzo and TrueLayer.
- Does not store credit card numbers or sensitive financial information.
- API tokens are stored encrypted in the database.
- Two-factor authentication is available and recommended.
- Regular backups of the database are advised.

## License

This project is licensed under the MIT License—see the LICENSE file for details.

## Acknowledgements

- Original project by Matt Gogerly
- Monzo API
- TrueLayer API
- Flask
- Tailwind CSS
