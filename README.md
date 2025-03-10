# Monzo Credit Card Pot Sync

A service that automatically syncs your credit card payments with Monzo pots, making it easy to set aside money for upcoming credit card payments.

## Features

- Connect to Monzo and credit card accounts via secure APIs
- Create custom rules for syncing funds between accounts and pots
- Schedule automatic transfers based on your preferences
- Monitor sync history and account balances
- Get notifications about transfers and account activity

## Getting Started

### Prerequisites

- Docker and Docker Compose (for containerized setup)
- Monzo account with API access
- TrueLayer account for connecting other bank/credit card accounts

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/martadams89/monzo-credit-card-pot-sync.git
   cd monzo-credit-card-pot-sync
   ```

2. Set up environment variables:
   Create a `.env` file based on the provided `.env.example` and fill in your API credentials.

3. Start the service:
   ```bash
   docker-compose up -d
   ```

4. Access the web interface at http://localhost:8000 and follow the setup instructions.

### Development Setup

1. Clone the repository as above

2. Start the development container:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

3. Make changes and the application will automatically reload

## Configuration

All configuration options can be set through environment variables:

- `BASE_URL`: The base URL where the application is hosted
- `MONZO_CLIENT_ID` and `MONZO_CLIENT_SECRET`: Your Monzo API credentials
- `TRUELAYER_CLIENT_ID` and `TRUELAYER_CLIENT_SECRET`: Your TrueLayer API credentials
- See `docker-compose.yml` for other available options

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).