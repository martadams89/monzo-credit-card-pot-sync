# Monzo Credit Card Pot Sync

![GitHub Release](https://img.shields.io/github/v/release/martadams89/monzo-credit-card-pot-sync?include_prereleases)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/martadams89/monzo-credit-card-pot-sync/build.yml?branch=main)
![License](https://img.shields.io/github/license/martadams89/monzo-credit-card-pot-sync)

> This project is based on [mattgogerly/monzo-credit-card-pot-sync](https://github.com/mattgogerly/monzo-credit-card-pot-sync) with additional security features and performance improvements.

A powerful system to automatically keep your Monzo pots synchronized with credit card balances. This ensures you always have enough funds set aside to pay your credit card bills, supporting multiple credit card providers and both personal and joint Monzo accounts.

## Features

- **Automatic Fund Management:** Sync your Monzo pot balance with your credit card spending automatically
- **Multiple Credit Card Support:** Connect various credit cards (American Express, Barclaycard, and more)
- **Joint Account Support:** Works with both personal and joint Monzo accounts
- **Pending Transaction Tracking:** Includes pending transactions in balance calculations for supported providers
- **Enhanced Security:**
  - Passkey (WebAuthn) support for passwordless login
  - Two-factor authentication (TOTP)
  - Email verification
- **Docker & Kubernetes Ready:** Easy deployment options with detailed guides
- **Dark Mode Support:** Responsive UI with dark mode toggle

## How It Works

The system uses sophisticated logic to ensure your Monzo pot always has enough money to cover your credit card balance:

### Normal Operations
- When you spend on a credit card, the system automatically deposits money into your designated Monzo pot to match the new card balance
- If your pot balance exceeds your card balance (e.g., after making a payment to your credit card), the excess is automatically withdrawn

### Cooldown Logic
- If your pot balance falls below your credit card balance without new spending detected (e.g., due to a direct payment from the pot), the system enters a cooldown period
- This prevents continuous back-and-forth transfers when you're actively managing your finances
- Once the cooldown expires (default: 3 hours), if the shortfall still exists, the system deposits the required amount

### Override Spending
- If the "override cooldown spending" setting is enabled, new spending on your card while in a cooldown will trigger an immediate deposit for the additional amount spent
- This ensures your pot always keeps up with new spending, while the original shortfall remains under cooldown

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
   cp env.sample .env
   # Edit .env file with your settings
   ```

3. Build CSS assets (required for the UI):
   ```bash
   npm install
   npm run build-css
   ```

4. Start the container using development mode:
   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```
   
   Or for production:
   ```bash
   docker compose up -d
   ```

5. Access the application:
   Development: Open `http://localhost:8000` in your web browser
   Production: Configure your reverse proxy to the exposed port

### Using Kubernetes

See the detailed [Kubernetes Deployment Guide](k8s/README.md) for instructions on deploying to a Kubernetes cluster.

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
   npm run build-css
   ```

5. Start the application:
   ```bash
   npm run dev  # Development mode with auto-reloading
   # OR
   npm start    # Production mode
   ```

## CSS Development and Building

The application uses Tailwind CSS for styling. CSS files are built automatically in several ways:

### In Docker Container

The CSS is automatically built during:
1. Docker image creation (using `npm run build-css`)
2. Container startup (via the entrypoint script, with fallbacks if Node.js is not available)

No manual steps are required when running in Docker.

### For Local Development

When developing locally, you can build the CSS in several ways:

1. Using npm:
   ```bash
   npm install
   npm run build-css
   ```

2. Using the provided script:
   ```bash
   ./build-css.sh
   ```

3. Using development mode with auto-reload:
   ```bash
   npm run build-css-live
   ```

The compiled CSS will be available at `app/static/css/dist/output.css`.

### CSS Fallback Mechanism

If Node.js/npm is not available, the application includes a fallback Python-based CSS generator
that creates a minimal CSS file to ensure the application remains functional.

## Database Migrations

Database migrations run automatically when the application starts. No manual steps are required for database setup or migration.

### First-Time Setup

When you first run the application:

1. The database will be automatically created
2. All required tables will be created
3. Migrations will run to ensure the database schema is up to date

### Upgrading from Previous Versions

When upgrading from a previous version of the application:

1. **Back up your database** before upgrading
2. Stop the old version of the application
3. Deploy the new version
4. Start the new version - migrations will run automatically
5. Check the application logs to confirm migrations completed successfully

If you encounter any database issues after upgrading, you may need to restore from the backup and perform a fresh installation.

## API Configuration

### API Client Setup

1. **Monzo API Setup:**
   - Log in to the Monzo developer portal at [https://developers.monzo.com](https://developers.monzo.com)
   - Create a client with redirect URL matching your environment:
     - If using a custom domain: `https://your-domain.com/auth/callback/monzo`
     - If using locally: `http://localhost:8000/auth/callback/monzo`
   - Set confidentiality to `Confidential` and note the client ID and secret

2. **TrueLayer API Setup:**
   - Login to the TrueLayer console at [https://console.truelayer.com](https://console.truelayer.com)
   - Create an application and switch to the `Live` environment
   - Add a redirect URI matching your environment:
     - If using a custom domain: `https://your-domain.com/auth/callback/truelayer`
     - If using locally: `http://localhost:8000/auth/callback/truelayer`
   - Copy the client ID and client secret

3. **Save in Application:**
   - Navigate to Settings in the application
   - Save the Monzo and TrueLayer client IDs and secrets
   - Accept the notification from Monzo to allow API access when prompted

### Using a Reverse Proxy or Custom Domain

If you're deploying behind a reverse proxy or using a custom domain, set the `POT_SYNC_LOCAL_URL` environment variable to the external URL of your application:

```yaml
environment:
  - POT_SYNC_LOCAL_URL=https://your-domain.com
```

This ensures the application generates correct URLs for callbacks when connecting to Monzo and TrueLayer APIs.

## Troubleshooting

### Common Issues

1. **CSS Not Loading:**
   - Make sure you've built the CSS files: `npm run build-css`
   - Check that the output file exists: `app/static/css/dist/output.css`
   - Verify the permissions on the CSS file

2. **Docker Permission Issues:**
   - If you're seeing permission errors with Docker volumes, try:
     ```bash
     sudo chown -R 1000:1000 ./instance
     ```

3. **Database Errors:**
   - If you encounter database errors, check the logs for specific migration issues
   - To reset the database: delete the `instance/app.db` file and restart the application

4. **API Connection Issues:**
   - Make sure your Monzo and TrueLayer API credentials are correctly set up
   - Verify the redirect URLs match exactly (including http/https)
   - Check if your tokens need to be refreshed

For more troubleshooting help, please open an issue on GitHub.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- Original project by [Matt Gogerly](https://github.com/mattgogerly/monzo-credit-card-pot-sync)
- [Monzo API](https://docs.monzo.com)
- [TrueLayer API](https://docs.truelayer.com)
- [Flask](https://flask.palletsprojects.com)
- [Tailwind CSS](https://tailwindcss.com)