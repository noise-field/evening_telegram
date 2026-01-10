# Migration to Daemon Mode

This document describes the changes made to transform The Evening Telegram from a cron-based single-run application to a daemon with multiple subscription support.

## What Changed

### 1. Architecture
- **Before**: Single configuration, run via cron, one-off execution
- **After**: Daemon mode with multiple subscriptions, each with independent schedules

### 2. Configuration Structure

#### Old Format (No Longer Supported)
```yaml
telegram:
  api_id: 12345
  api_hash: "..."
  phone: "+1234567890"
  bot_token: "..."
  report_chat_id: 123456

channels:
  - "@channel1"
  - "@channel2"

period:
  lookback: "24 hours"

llm:
  base_url: "..."
  api_key: "..."
  model: "gpt-4o"

output:
  language: "en"
  newspaper_name: "..."
  # ...
```

#### New Format (Required)
```yaml
telegram:
  api_id: 12345
  api_hash: "..."
  phone: "+1234567890"
  # Note: bot_token and report_chat_id moved to subscription level

llm:
  base_url: "..."
  api_key: "..."
  model: "gpt-4o"

subscriptions:
  my_subscription:
    name: "My Subscription"
    channels:
      - "@channel1"
      - "@channel2"
    
    schedule:
      lookback: "24 hours"
      times: ["10:00", "22:00"]  # OR day_of_week + time for weekly
    
    output:
      language: "en"
      newspaper_name: "..."
      telegram:
        bot_token: "..."
        chat_id: 123456
      # ...
```

### 3. CLI Commands

#### Old Commands (Removed)
```bash
evening-telegram                    # Run once
evening-telegram --lookback "7 days"
```

#### New Commands
```bash
# Daemon mode (runs continuously)
evening-telegram daemon

# Run a specific subscription once
evening-telegram run --subscription my_subscription

# Run all subscriptions once
evening-telegram run-all

# List configured subscriptions
evening-telegram list-subscriptions

# Test schedule
evening-telegram test-schedule --subscription my_subscription
```

### 4. Database Schema Changes

The state database now tracks subscriptions separately:

**runs table**: Added `subscription_id` column
**processed_messages table**: Added `subscription_id` column and updated primary key

This allows the same message to be processed by multiple subscriptions independently.

## Migration Steps

### If You Have No Existing Data

1. Update your config.yaml using the new format (see example.config.yaml)
2. Delete the old state database: `rm ~/.config/evening-telegram/state.db`
3. Run: `evening-telegram run --subscription <name>` to test
4. Start daemon: `evening-telegram daemon`

### If You Have Existing Data

**Option 1: Fresh Start (Recommended)**
1. Back up your old config and state database
2. Create new config.yaml in the new format
3. Delete state database to start fresh
4. Run and test

**Option 2: Manual Migration**
The database schema will auto-upgrade on first run (subscription_id columns allow NULL).
However, old data won't have subscription associations, so it's recommended to start fresh.

## Key Features

### Scheduling

**Daily schedules:**
```yaml
schedule:
  lookback: "12 hours"
  times: ["10:00", "22:00"]  # Morning and evening
```

**Weekly schedules:**
```yaml
schedule:
  lookback: "7 days"
  day_of_week: 0  # 0=Monday, 6=Sunday
  time: "09:00"
```

### Per-Subscription Configuration

Each subscription can have:
- Its own channels
- Independent schedule
- Separate output settings (language, newspaper name, etc.)
- Different delivery methods (Telegram, email, or both)
- Custom processing options

### Running as a Service

See AGENTSPEC.md Appendix A for systemd setup instructions.

## Testing

```bash
# List subscriptions
evening-telegram list-subscriptions --config config.yaml

# Test schedule
evening-telegram test-schedule --subscription ai_security_weekly --config config.yaml

# Run once to test
evening-telegram run --subscription ai_security_weekly --config config.yaml
```

## Troubleshooting

**"Configuration file not found"**
- Specify path: `--config config.yaml`
- Or move config to: `~/.config/evening-telegram/config.yaml`

**"Subscription not found"**
- Check spelling with: `evening-telegram list-subscriptions`
- Ensure subscription ID matches YAML key

**Schedule not triggering**
- Verify with: `evening-telegram test-schedule --subscription <name>`
- Check daemon logs for errors
- Ensure times are in 24-hour format ("HH:MM")

## Recent Updates

### Multiple Telegram Recipients (2026-01-10)

The `chat_id` field now supports both single and multiple recipients:

**Single recipient (backward compatible):**
```yaml
telegram:
  bot_token: "..."
  chat_id: 123456789
```

**Multiple recipients:**
```yaml
telegram:
  bot_token: "..."
  chat_id: [123456789, 987654321, 111222333]
```

When sending to multiple chat IDs, the bot will send the report to each recipient independently. If sending to one recipient fails, it will continue to the next ones.

### Telegram Client Fix

Fixed an issue where the daemon couldn't access Telegram client methods. The wrapper now properly exposes the underlying `TelegramClient` instance.
