# Quick Start Guide

Get The Evening Telegram daemon running in 5 minutes!

## Prerequisites

- Python 3.11+
- A Telegram account
- An LLM API key (OpenAI, Anthropic, or compatible)
- Basic understanding of YAML configuration

## Step 1: Install

```bash
cd /home/user/Code/EveningTelegram
pip install -e .
```

## Step 2: Verify Installation

```bash
python verify_installation.py
```

If you see errors, install missing dependencies:
```bash
pip install -e .
```

## Step 3: Get Credentials

### Telegram API (MTProto)
1. Visit https://my.telegram.org/apps
2. Log in with your phone number
3. Create a new application
4. Note your `api_id` and `api_hash`

### Telegram Bot Token(s)
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Note the bot token (looks like `123456:ABC-DEF...`)
4. Create one bot per subscription, or share one bot across subscriptions

### Your Chat ID(s)
1. Search for `@userinfobot` in Telegram
2. Send it `/start`
3. Note your user ID (a number like `123456789`)
4. You can send to multiple chat IDs per subscription

### LLM API Key
- **OpenAI**: Get from https://platform.openai.com/api-keys
- **Anthropic**: Get from https://console.anthropic.com/
- **Others**: Check your provider's documentation

## Step 4: Create Configuration

```bash
# Create config directory
mkdir -p ~/.config/evening-telegram

# Copy example config
cp example.config.yaml ~/.config/evening-telegram/config.yaml

# Edit with your favorite editor
nano ~/.config/evening-telegram/config.yaml
```

### Minimal Configuration

Replace these values in your config:

```yaml
telegram:
  api_id: YOUR_API_ID          # From step 3
  api_hash: "YOUR_API_HASH"    # From step 3
  phone: "+1234567890"         # Your phone number
  session_file: "~/.config/evening-telegram/telegram.session"

llm:
  api_key: "YOUR_LLM_API_KEY"  # From step 3
  model: "gpt-4o"              # Or your preferred model

subscriptions:
  my_first_subscription:       # Subscription ID (your choice)
    name: "My Daily Digest"    # Display name

    channels:
      - "@example_channel"     # Replace with real channels

    schedule:
      lookback: "24 hours"
      times: ["18:00"]         # Daily at 6 PM

    output:
      language: "en"
      newspaper_name: "My Evening Telegram"
      tagline: "Your daily news digest"
      html_path: "~/evening-telegram/%Y-%m-%d.html"

      save_html: true
      send_telegram: true

      telegram:
        bot_token: "YOUR_BOT_TOKEN"  # From step 3
        chat_id: YOUR_CHAT_ID        # From step 3
```

## Step 5: Test Configuration

```bash
# List configured subscriptions
evening-telegram list-subscriptions

# Test schedule for your subscription
evening-telegram test-schedule --subscription my_first_subscription
```

## Step 6: First Run (Authentication)

```bash
# Run subscription once interactively for Telegram authentication
evening-telegram run --subscription my_first_subscription -vv
```

You'll be prompted to:
1. Enter verification code sent to Telegram
2. Enter 2FA password if enabled

The session will be saved for future runs.

## Step 7: Test with Dry Run

```bash
# Process but don't send/save
evening-telegram run --subscription my_first_subscription --dry-run -v
```

This will:
- Fetch messages
- Cluster and generate articles
- Show statistics
- NOT save or send anything

## Step 8: Start Daemon

```bash
# Start daemon mode (runs continuously)
evening-telegram daemon
```

The daemon will:
1. Monitor all configured subscriptions
2. Generate newspapers at scheduled times
3. Deliver via configured methods
4. Track state per subscription
5. Continue running until stopped

## Common First-Run Issues

### "Configuration file not found"
Specify path: `evening-telegram daemon --config config.yaml` or move to `~/.config/evening-telegram/config.yaml`

### "Subscription not found"
Check with: `evening-telegram list-subscriptions`

### "SessionPasswordNeededError"
Your account has 2FA enabled. Enter your password when prompted during `run` command.

### "ChannelPrivateError"
Subscribe to the private channel via Telegram app first.

### "No messages to process"
Normal if no new messages. Try `evening-telegram run --subscription my_first_subscription --lookback "7 days"` to test.

### "PeerIdInvalid"
Check your channel usernames. Public channels need `@` prefix.

### Schedule not triggering
Verify with `evening-telegram test-schedule --subscription my_first_subscription`. Check times are in 24-hour format.

## Next Steps

### Run as a System Service

For production use, set up as a systemd service (see [README.md](README.md#running-as-a-service) for full instructions):

```bash
# Create service file at /etc/systemd/system/evening-telegram.service
sudo systemctl enable evening-telegram
sudo systemctl start evening-telegram
```

Or use screen/tmux for simple background running:
```bash
screen -S evening-telegram
evening-telegram daemon
# Detach with Ctrl+A, D
```

### Add More Subscriptions

Edit config to add additional subscriptions:
```yaml
subscriptions:
  my_first_subscription:
    # ... existing config ...

  ai_weekly:
    name: "AI Weekly Digest"
    channels:
      - "@ai_news"
    schedule:
      lookback: "7 days"
      day_of_week: 0  # Monday
      time: "09:00"
    output:
      # ... output config ...
```

### Add More Channels to a Subscription

Edit the subscription's `channels:` section:
```yaml
subscriptions:
  my_first_subscription:
    channels:
      - "@channel1"
      - "@channel2"
      - "@channel3"
      - -1001234567890  # Private channel by ID
```

### Customize Subscription Output

Edit subscription's `output:` section to:
- Change newspaper name and tagline
- Set preferred language
- Adjust sections
- Configure email delivery
- Set multiple Telegram recipients

### View Your Newspaper

Open the HTML file in a browser:
```bash
open ~/evening-telegram/YYYY-MM-DD.html
```

## CLI Options Cheat Sheet

```bash
# Daemon mode
evening-telegram daemon
evening-telegram daemon --config /path/to/config.yaml
evening-telegram daemon -vv  # Verbose

# One-off runs
evening-telegram run --subscription my_first_subscription
evening-telegram run --subscription my_first_subscription --lookback "48 hours"
evening-telegram run --subscription my_first_subscription --dry-run
evening-telegram run-all  # Run all subscriptions once

# Utility
evening-telegram list-subscriptions
evening-telegram test-schedule --subscription my_first_subscription

# Override output (one-off runs only)
evening-telegram run --subscription my_first_subscription --output ~/custom.html
evening-telegram run --subscription my_first_subscription --no-telegram
```

## Configuration Tips

### For Testing
```yaml
subscriptions:
  test_subscription:
    # ... other config ...
    processing:
      max_messages: 20  # Limit messages to save tokens
      clustering_batch_size: 30

state:
  mode: "full"  # Always reprocess (ignore state)
```

### For Production
```yaml
subscriptions:
  production_subscription:
    # ... other config ...
    processing:
      max_messages: 0  # No limit
      min_sources_for_article: 2
      clustering_batch_size: 50

state:
  mode: "since_last"  # Only new messages (default)
```

### For Cost Control
```yaml
llm:
  model: "gpt-4o-mini"  # Cheaper model
  temperature: 0.0      # More deterministic

subscriptions:
  cost_effective:
    schedule:
      lookback: "12 hours"  # Shorter lookback
    processing:
      max_messages: 50  # Hard limit
      clustering_batch_size: 30
```

## Getting Help

- **Documentation**: See [README.md](README.md)
- **Examples**: Check [examples/](examples/) directory
- **Issues**: Open a GitHub issue
- **Verbose logs**: Run with `-vv` flag

## Success Checklist

- ✅ Installation verified
- ✅ Credentials obtained
- ✅ Config file created with at least one subscription
- ✅ Subscriptions listed successfully
- ✅ Schedule tested
- ✅ First test run successful (authentication complete)
- ✅ HTML output generated
- ✅ Telegram delivery working
- ✅ Daemon started (or systemd service configured)

Enjoy your newspapers! 📰
