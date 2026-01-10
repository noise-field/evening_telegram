# Quick Start Guide

Get The Evening Telegram running in 5 minutes!

## Prerequisites

- Python 3.11+
- A Telegram account
- An LLM API key (OpenAI, Anthropic, or compatible)

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

### Telegram Bot Token
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Note the bot token (looks like `123456:ABC-DEF...`)

### Your Chat ID
1. Search for `@userinfobot` in Telegram
2. Send it `/start`
3. Note your user ID (a number like `123456789`)

### LLM API Key
- **OpenAI**: Get from https://platform.openai.com/api-keys
- **Anthropic**: Get from https://console.anthropic.com/
- **Others**: Check your provider's documentation

## Step 4: Create Configuration

```bash
# Create config directory
mkdir -p ~/.config/evening-telegram

# Copy example config
cp examples/config.example.yaml ~/.config/evening-telegram/config.yaml

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
  bot_token: "YOUR_BOT_TOKEN"  # From step 3
  report_chat_id: YOUR_CHAT_ID # From step 3

channels:
  - "@example_channel"         # Replace with real channels

llm:
  api_key: "YOUR_LLM_API_KEY" # From step 3
  model: "gpt-4o"              # Or your preferred model
```

## Step 5: First Run

```bash
# Run interactively
evening-telegram -vv
```

You'll be prompted to:
1. Enter verification code sent to Telegram
2. Enter 2FA password if enabled

The session will be saved for future runs.

## Step 6: Test with Dry Run

```bash
# Process but don't send/save
evening-telegram --dry-run -v
```

This will:
- Fetch messages
- Cluster and generate articles
- Show statistics
- NOT save or send anything

## Step 7: Normal Run

```bash
# Full run
evening-telegram
```

This will:
1. Fetch new messages
2. Generate newspaper
3. Save HTML to `~/evening-telegram/editions/YYYY-MM-DD.html`
4. Send via Telegram bot
5. Mark messages as processed

## Common First-Run Issues

### "SessionPasswordNeededError"
Your account has 2FA enabled. Enter your password when prompted.

### "ChannelPrivateError"
Subscribe to the private channel via Telegram app first.

### "No messages to process"
Normal if no new messages. Try `--lookback "7 days"` to test.

### "PeerIdInvalid"
Check your channel usernames. Public channels need `@` prefix.

## Next Steps

### Schedule Daily Runs

Add to crontab:
```bash
crontab -e
```

Add line:
```
0 18 * * * /usr/local/bin/evening-telegram
```

### Customize Output

Edit config to:
- Change newspaper name and tagline
- Set preferred language
- Adjust clustering thresholds
- Configure email delivery

### Add More Channels

Edit config `channels:` section:
```yaml
channels:
  - "@channel1"
  - "@channel2"
  - "@channel3"
  - -1001234567890  # Private channel by ID
```

### View Your Newspaper

Open the HTML file in a browser:
```bash
open ~/evening-telegram/editions/$(date +%Y-%m-%d).html
```

## CLI Options Cheat Sheet

```bash
# Custom config
evening-telegram --config /path/to/config.yaml

# Time period
evening-telegram --lookback "48 hours"
evening-telegram --from "2024-01-15" --to "2024-01-16"

# Output
evening-telegram --output ~/custom.html
evening-telegram --no-telegram      # Skip Telegram
evening-telegram --telegram-only    # Only Telegram

# Testing
evening-telegram --dry-run          # Don't save/send
evening-telegram -vv                # Verbose debug

# Specific channels
evening-telegram --channels "@channel1,@channel2"
```

## Configuration Tips

### For Testing
```yaml
processing:
  max_messages: 20  # Limit messages to save tokens

state:
  mode: "full"      # Always reprocess (ignore state)
```

### For Production
```yaml
processing:
  max_messages: 0   # No limit
  min_sources_for_article: 2

state:
  mode: "since_last"  # Only new messages
```

### For Cost Control
```yaml
llm:
  model: "gpt-4o-mini"  # Cheaper model
  temperature: 0.0      # More deterministic

processing:
  clustering_batch_size: 30  # Smaller batches
```

## Getting Help

- **Documentation**: See [README.md](README.md)
- **Examples**: Check [examples/](examples/) directory
- **Issues**: Open a GitHub issue
- **Verbose logs**: Run with `-vv` flag

## Success Checklist

- ✅ Installation verified
- ✅ Credentials obtained
- ✅ Config file created
- ✅ First run successful
- ✅ HTML output generated
- ✅ Telegram delivery working
- ✅ Cron job scheduled (optional)

Enjoy your newspaper! 📰
