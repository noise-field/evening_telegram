# The Evening Telegram

**A newspaper-style digest generator for Telegram channels**

> ⚠️ This project is entirely vibe-coded as a learning project getting to know Claude Code. While it works and is somthing useful to me, code quality is not guaranteed!

The Evening Telegram is a Python application that aggregates messages from Telegram channels, uses AI to deduplicate and cluster content, and generates a professionally-styled HTML newspaper. Say goodbye to information overload and FOMO-driven scrolling!

## Features

- **Smart Deduplication**: Uses LLM to identify duplicate stories across multiple sources
- **Topic Clustering**: Automatically groups related messages into coherent articles
- **Professional Output**: Beautiful HTML newspaper with proper typography and layout
- **Multi-Channel Support**: Monitor both public and private Telegram channels
- **Flexible Delivery**: Save HTML locally, send via Telegram bot, or email
- **Incremental Processing**: Track processed messages to avoid reprocessing
- **Cost-Transparent**: Reports token usage and API calls
- **Source Attribution**: Every claim links back to original Telegram messages

## Quick Start

### 1. Installation

#### Using uv (recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

```bash
# Clone the repository
git clone <repository-url>
cd EveningTelegram

# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package in development mode
uv pip install -e .

# Or install from requirements.txt (pinned versions)
uv pip install -r requirements.txt
```

#### Using pip

```bash
# Clone the repository
git clone <repository-url>
cd EveningTelegram

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 2. Get API Credentials

You'll need:
- **Telegram API credentials**: Get from https://my.telegram.org/apps
- **Telegram bot token**: Create a bot with @BotFather
- **LLM API key**: OpenAI, Anthropic, or any OpenAI-compatible provider
- **Your chat ID**: Use @userinfobot to find your Telegram user ID

### 3. Create Configuration

```bash
# Create config directory
mkdir -p ~/.config/evening-telegram

# Copy example config
cp examples/config.example.yaml ~/.config/evening-telegram/config.yaml

# Edit with your credentials
nano ~/.config/evening-telegram/config.yaml
```

### 4. First Run

```bash
# Run interactively for first-time Telegram authentication
evening-telegram

# Or with custom config
evening-telegram --config /path/to/config.yaml
```

On first run, you'll be prompted to enter your Telegram verification code. Subsequent runs will use the saved session.

## Configuration

The application uses a YAML configuration file (default: `~/.config/evening-telegram/config.yaml`). See [examples/config.example.yaml](examples/config.example.yaml) for a fully documented example.

### Essential Configuration Sections

#### Telegram Authentication
```yaml
telegram:
  api_id: 12345678
  api_hash: "your_api_hash"
  phone: "+1234567890"
  bot_token: "bot_token_from_botfather"
  report_chat_id: 123456789
```

#### Channels to Monitor
```yaml
channels:
  - "@channel_username"
  - "@another_channel"
  - -1001234567890  # Private channel by ID
```

#### LLM Configuration
```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "sk-..."
  model: "gpt-4o"
  temperature: 0.3
```

#### Output Settings
```yaml
output:
  language: "en"
  newspaper_name: "The Evening Telegram"
  html_path: "~/evening-telegram/editions/%Y-%m-%d.html"
  save_html: true
  send_telegram: true
  send_email: false
```

### Environment Variables

Sensitive values can be provided via environment variables:

```bash
export EVENING_TELEGRAM_API_ID=12345678
export EVENING_TELEGRAM_API_HASH="your_hash"
export EVENING_TELEGRAM_BOT_TOKEN="bot_token"
export EVENING_TELEGRAM_LLM_API_KEY="sk-..."
export EVENING_TELEGRAM_SMTP_PASSWORD="email_password"
```

## Usage

### Basic Usage

```bash
# Use default config
evening-telegram

# Specify custom config
evening-telegram --config /path/to/config.yaml

# Increase verbosity
evening-telegram -v   # Info level
evening-telegram -vv  # Debug level
```

### Time Period Options

```bash
# Override lookback period
evening-telegram --lookback "7 days"
evening-telegram --lookback "48 hours"

# Specify explicit time range
evening-telegram --from "2024-01-15" --to "2024-01-16"
```

### Output Options

```bash
# Custom HTML output path
evening-telegram --output ~/custom-output.html

# Skip Telegram delivery
evening-telegram --no-telegram

# Skip email delivery
evening-telegram --no-email

# Only send via Telegram (don't save HTML)
evening-telegram --telegram-only

# Process but don't output (testing)
evening-telegram --dry-run
```

### Channel Options

```bash
# Override channels from CLI
evening-telegram --channels "@channel1,@channel2,@channel3"
```

## Scheduled Runs

### Using Cron

```bash
# Edit crontab
crontab -e

# Daily evening edition at 6 PM
0 18 * * * /path/to/evening-telegram --config ~/.config/evening-telegram/config.yaml

# Weekly digest every Sunday at 10 AM
0 10 * * 0 /path/to/evening-telegram --lookback "7 days"
```

### Using systemd Timer

Create `/etc/systemd/system/evening-telegram.service`:

```ini
[Unit]
Description=The Evening Telegram

[Service]
Type=oneshot
User=your-username
ExecStart=/usr/local/bin/evening-telegram
Environment="EVENING_TELEGRAM_LLM_API_KEY=sk-..."
```

Create `/etc/systemd/system/evening-telegram.timer`:

```ini
[Unit]
Description=Run The Evening Telegram daily

[Timer]
OnCalendar=daily
OnCalendar=18:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable the timer:

```bash
sudo systemctl enable evening-telegram.timer
sudo systemctl start evening-telegram.timer
```

## How It Works

1. **Ingestion**: Connects to Telegram via MTProto and fetches messages from configured channels
2. **Normalization**: Extracts text, handles forwards, and identifies media/links
3. **Deduplication**: LLM identifies messages covering the same story
4. **Clustering**: Groups related messages into coherent topics
5. **Article Generation**: LLM writes newspaper-style articles with proper attribution
6. **Section Assignment**: Organizes articles into sections (Politics, Tech, World, etc.)
7. **Output**: Generates HTML newspaper and/or delivers via Telegram/email
8. **State Tracking**: Records processed messages to enable incremental runs

## Architecture

The application is designed as a thin wrapper around two APIs:
- **Telegram API** (MTProto for reading, Bot API for sending)
- **LLM API** (OpenAI-compatible for all semantic processing)

All "intelligence" is delegated to the LLM—no local ML models or heavy dependencies.

### Project Structure

```
evening-telegram/
├── src/evening_telegram/
│   ├── config/          # Configuration management
│   ├── telegram/        # Telegram client and fetching
│   ├── processing/      # Clustering and article generation
│   ├── llm/            # LLM client and prompts
│   ├── output/         # HTML, email, Telegram delivery
│   ├── state/          # SQLite state management
│   ├── models/         # Data models
│   └── templates/      # Jinja2 HTML templates
├── tests/              # Test suite
└── examples/           # Example configurations
```

## Troubleshooting

### "SessionPasswordNeededError"
Your Telegram account has 2FA enabled. Run the application interactively and enter your 2FA password when prompted.

### "ChannelPrivateError"
You're not subscribed to the private channel. Subscribe via the Telegram app first.

### Empty Output
All messages have already been processed. Try:
- Using `--lookback` with a longer period
- Changing `state.mode` to `"full"` in config

### High Token Usage
Too many messages in the lookback period. Reduce the period or set `max_messages` limit in config.

### Malformed JSON from LLM
The model is returning invalid JSON. Try:
- Using a more capable model
- Lowering the temperature
- Reducing batch size

## Development

### Setting Up Development Environment

#### With uv (recommended)

```bash
# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package with dev dependencies
uv pip install -e ".[dev]"

# Or install from requirements files
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt  # If you have one
```

#### Updating Dependencies

```bash
# Update requirements.txt from requirements.in
uv pip compile requirements.in -o requirements.txt

# Install updated dependencies
uv pip sync requirements.txt

# For development, add package in editable mode
uv pip install -e .
```

### Running Tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=evening_telegram
```

### Code Quality

```bash
# Format code
ruff format .

# Lint
ruff check .

# Type checking
mypy src/
```

### Why uv?

- **Speed**: 10-100x faster than pip for package installation
- **Reliability**: Built-in dependency resolution that avoids conflicts
- **Compatibility**: Drop-in replacement for pip with the same interface
- **Modern**: Written in Rust with a focus on performance and correctness

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

BSD 3-Clause License - see LICENSE file for details

## Acknowledgments

Built with:
- [Telethon](https://github.com/LonamiWebs/Telethon) - Telegram MTProto client
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API
- [OpenAI Python](https://github.com/openai/openai-python) - LLM API client
- [Jinja2](https://jinja.palletsprojects.com/) - HTML templating
- [Click](https://click.palletsprojects.com/) - CLI framework

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**The Evening Telegram** - All the news that's fit to aggregate
