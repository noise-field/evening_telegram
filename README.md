# The Evening Telegram

**A newspaper-style digest generator for Telegram channels**

> ⚠️ This project is entirely vibe-coded as a learning project getting to know Claude Code. While it works and is something useful to me, code quality is not guaranteed!

The Evening Telegram is a Python daemon application that aggregates messages from Telegram channels, uses AI to deduplicate and cluster content, and generates professionally-styled HTML newspapers. Say goodbye to information overload and FOMO-driven scrolling!

## Features

- **Daemon Mode**: Runs continuously as a background service with configurable schedules
- **Multiple Subscriptions**: Each subscription has its own channels, schedule, and delivery settings
- **Flexible Scheduling**: Daily (multiple times per day) or weekly report generation
- **Smart Deduplication**: Uses LLM to identify duplicate stories across multiple sources
- **Topic Clustering**: Automatically groups related messages into coherent articles
- **Professional Output**: Beautiful HTML newspaper with proper typography and layout
- **Multi-Channel Support**: Monitor both public and private Telegram channels
- **Flexible Delivery**: Save HTML locally, send via Telegram bot, or email
- **Incremental Processing**: Track processed messages per subscription to avoid reprocessing
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
- **Telegram bot token(s)**: Create bot(s) with @BotFather (one per subscription or share one)
- **LLM API key**: OpenAI, Anthropic, or any OpenAI-compatible provider
- **Your chat ID(s)**: Use @userinfobot to find your Telegram user ID(s)

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
# Test a subscription (one-off run) for first-time Telegram authentication
evening-telegram run --subscription YOUR_SUBSCRIPTION_NAME

# List configured subscriptions
evening-telegram list-subscriptions

# Test schedule
evening-telegram test-schedule --subscription YOUR_SUBSCRIPTION_NAME

# Start daemon mode (runs continuously)
evening-telegram daemon

# Or with custom config
evening-telegram daemon --config /path/to/config.yaml
```

On first run, you'll be prompted to enter your Telegram verification code. Subsequent runs will use the saved session.

## Configuration

The application uses a YAML configuration file (default: `~/.config/evening-telegram/config.yaml`). See [example.config.yaml](example.config.yaml) for a fully documented example.

### Key Changes from v0.x

If you're upgrading from an earlier version, **the configuration format has changed**. See [MIGRATION.md](MIGRATION.md) for migration instructions. The main changes:
- Configuration is now subscription-based (daemon mode)
- `bot_token` and `chat_id` moved to subscription level
- Schedules configured per subscription
- Support for multiple subscriptions with different settings

### Essential Configuration Sections

#### Telegram Authentication
```yaml
telegram:
  api_id: 12345678
  api_hash: "your_api_hash"
  phone: "+1234567890"
  session_file: "~/.config/evening-telegram/telegram.session"
```

#### LLM Configuration (Global Default)
```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "sk-..."
  model: "gpt-4o"
  temperature: 0.3
```

#### Subscriptions (Multiple Supported)
```yaml
subscriptions:
  politics_daily:
    name: "Daily Politics & Finance"

    channels:
      - "@politics_channel"
      - "@financial_news"

    schedule:
      lookback: "12 hours"
      times: ["10:00", "22:00"]  # Morning and evening

    output:
      language: "en"
      newspaper_name: "Politics & Finance Daily"
      tagline: "Your daily briefing on politics and markets"
      html_path: "~/evening-telegram/politics/%Y-%m-%d-%H%M.html"

      save_html: true
      send_telegram: true
      send_email: false

      telegram:
        bot_token: "123456:ABC-DEF..."
        chat_id: 123456789  # Or [id1, id2] for multiple recipients

  ai_weekly:
    name: "AI Weekly Digest"

    channels:
      - "@ai_news"
      - "@ml_research"

    schedule:
      lookback: "7 days"
      day_of_week: 0  # Monday
      time: "09:00"

    output:
      language: "en"
      newspaper_name: "AI Weekly"
      html_path: "~/evening-telegram/ai-weekly/%Y-W%U.html"
      send_telegram: true
      telegram:
        bot_token: "123456:ABC-DEF..."
        chat_id: 987654321
```

### Environment Variables

Sensitive values can be provided via environment variables and referenced in config using `$VAR_NAME:default` syntax:

```yaml
telegram:
  api_id: $TELEGRAM_API_ID:12345678
  api_hash: $TELEGRAM_API_HASH:your_api_hash_here

llm:
  api_key: $ANTHROPIC_API_KEY:sk-...
```

Supported environment variables:
- `TELEGRAM_API_ID`: Telegram MTProto API ID
- `TELEGRAM_API_HASH`: Telegram MTProto API hash
- `TELEGRAM_BOT_TOKEN`: Bot token for sending messages
- `ANTHROPIC_API_KEY`: LLM API key (OpenAI, Anthropic, etc.)
- `EVENING_TELEGRAM_SMTP_PASSWORD`: SMTP password for email delivery

## Usage

### Daemon Mode (Primary)

```bash
# Start daemon (runs continuously)
evening-telegram daemon

# Specify custom config
evening-telegram daemon --config /path/to/config.yaml

# Increase verbosity
evening-telegram daemon -v   # Info level
evening-telegram daemon -vv  # Debug level
```

### One-Off Runs (Testing/Manual)

```bash
# Run a specific subscription once
evening-telegram run --subscription politics_daily

# Run all subscriptions once
evening-telegram run-all

# Run with custom lookback period
evening-telegram run --subscription ai_weekly --lookback "14 days"

# Dry run (process but don't send/save)
evening-telegram run --subscription politics_daily --dry-run

# Override output options
evening-telegram run --subscription politics_daily --output ~/custom.html
evening-telegram run --subscription politics_daily --no-telegram --no-email
```

### Utility Commands

```bash
# List configured subscriptions
evening-telegram list-subscriptions

# Test schedule for a subscription (shows next execution times)
evening-telegram test-schedule --subscription politics_daily
```

## Running as a Service

### Using systemd (Recommended)

Create `/etc/systemd/system/evening-telegram.service`:

```ini
[Unit]
Description=The Evening Telegram - News digest daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username
ExecStart=/usr/local/bin/evening-telegram daemon --config /home/your-username/.config/evening-telegram/config.yaml
Restart=always
RestartSec=10

# Environment variables for secrets
Environment="ANTHROPIC_API_KEY=your-key-here"
Environment="EVENING_TELEGRAM_SMTP_PASSWORD=your-password-here"

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable evening-telegram
sudo systemctl start evening-telegram
sudo systemctl status evening-telegram
```

View logs:

```bash
sudo journalctl -u evening-telegram -f
```

### Using Screen/Tmux

```bash
# Using screen
screen -S evening-telegram
evening-telegram daemon
# Detach with Ctrl+A, D

# Reattach
screen -r evening-telegram

# Using tmux
tmux new -s evening-telegram
evening-telegram daemon
# Detach with Ctrl+B, D

# Reattach
tmux attach -t evening-telegram
```

## How It Works

### Daemon Mode
1. **Initialization**: Loads config, connects to Telegram, initializes state DB per subscription
2. **Scheduling**: Monitors configured schedules for each subscription
3. **Execution**: When scheduled time arrives for a subscription:
   - Fetches messages from subscription's channels
   - Processes and generates newspaper
   - Delivers via configured methods
   - Tracks state separately per subscription
4. **Continuous**: Returns to monitoring, handling multiple subscriptions independently

### Processing Pipeline (Per Subscription Run)
1. **Ingestion**: Connects to Telegram via MTProto and fetches messages from subscription's channels
2. **Normalization**: Extracts text, handles forwards, and identifies media/links
3. **Deduplication**: LLM identifies messages covering the same story
4. **Clustering**: Groups related messages into coherent topics
5. **Article Generation**: LLM writes newspaper-style articles with proper attribution
6. **Section Assignment**: Organizes articles into sections (Politics, Tech, World, etc.)
7. **Output**: Generates HTML newspaper and/or delivers via Telegram/email
8. **State Tracking**: Records processed messages for this subscription to enable incremental runs

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

### "Configuration file not found"
Specify path explicitly:
```bash
evening-telegram daemon --config config.yaml
```
Or move config to: `~/.config/evening-telegram/config.yaml`

### "Subscription not found"
Check spelling with:
```bash
evening-telegram list-subscriptions
```
Ensure subscription ID matches YAML key.

### "SessionPasswordNeededError"
Your Telegram account has 2FA enabled. Run a test command interactively and enter your 2FA password when prompted:
```bash
evening-telegram run --subscription YOUR_SUBSCRIPTION_NAME
```

### "ChannelPrivateError"
You're not subscribed to the private channel. Subscribe via the Telegram app first.

### Schedule not triggering
Verify with:
```bash
evening-telegram test-schedule --subscription YOUR_SUBSCRIPTION_NAME
```
Check daemon logs for errors. Ensure times are in 24-hour format ("HH:MM").

### Empty Output
All messages have already been processed for this subscription. Try:
- Using `--lookback` with a longer period in one-off run
- Changing `state.mode` to `"full"` in config
- Deleting the state database to start fresh

### High Token Usage
Too many messages in the lookback period. Reduce the period or set `max_messages` limit in subscription's `processing` section.

### Malformed JSON from LLM
The model is returning invalid JSON. Try:
- Using a more capable model
- Lowering the temperature
- Reducing batch size in subscription's `processing` section

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
