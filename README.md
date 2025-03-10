# Monzo Credit Card Pot Sync

A Flask-based web application that synchronizes your credit card balances with Monzo pots, helping you stay on top of your finances automatically.

## Features

- Connect multiple credit cards to your Monzo account
- Automatically keep track of credit card spending
- Move money to designated Monzo pots based on spending
- Support for both personal and joint accounts
- Customizable sync rules and schedules
- User-friendly web interface with dark mode support

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

2. Install dependencies:
   ```bash
   # Python dependencies
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt

   # JavaScript dependencies
   npm install
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```

5. For testing:
   ```bash
   pytest
   ```

## Configuration

All configuration options can be set through environment variables:

- `BASE_URL`: The base URL where the application is hosted
- `MONZO_CLIENT_ID` and `MONZO_CLIENT_SECRET`: Your Monzo API credentials
- `TRUELAYER_CLIENT_ID` and `TRUELAYER_CLIENT_SECRET`: Your TrueLayer API credentials
- See `docker-compose.yml` for other available options

## Testing

The project uses pytest for testing. Run the test suite with:
   ```bash
   pytest
   ```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).