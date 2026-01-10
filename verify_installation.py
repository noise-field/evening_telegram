#!/usr/bin/env python3
"""Simple script to verify the installation and imports."""

import sys


def verify_installation():
    """Verify that all required modules can be imported."""
    print("Verifying The Evening Telegram installation...\n")

    errors = []

    # Test core imports
    modules_to_test = [
        ("evening_telegram", "Core package"),
        ("evening_telegram.config", "Configuration module"),
        ("evening_telegram.telegram", "Telegram module"),
        ("evening_telegram.llm", "LLM module"),
        ("evening_telegram.processing", "Processing module"),
        ("evening_telegram.output", "Output module"),
        ("evening_telegram.state", "State management module"),
        ("evening_telegram.models", "Data models"),
    ]

    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            print(f"✓ {description}: OK")
        except ImportError as e:
            print(f"✗ {description}: FAILED - {e}")
            errors.append((module_name, e))

    # Test external dependencies
    print("\nVerifying external dependencies...\n")

    dependencies = [
        ("telethon", "Telegram MTProto client"),
        ("telegram", "Telegram Bot API"),
        ("openai", "OpenAI LLM client"),
        ("pydantic", "Configuration validation"),
        ("click", "CLI framework"),
        ("jinja2", "HTML templating"),
        ("aiosmtplib", "Async SMTP"),
        ("aiosqlite", "Async SQLite"),
        ("rich", "Terminal output"),
        ("dateutil", "Date parsing"),
        ("yaml", "YAML parsing"),
    ]

    for dep_name, description in dependencies:
        try:
            __import__(dep_name)
            print(f"✓ {description}: OK")
        except ImportError as e:
            print(f"✗ {description}: FAILED - {e}")
            errors.append((dep_name, e))

    print("\n" + "=" * 60)

    if errors:
        print(f"\n❌ Installation verification FAILED with {len(errors)} errors")
        print("\nTo fix, run:")
        print("  pip install -e .")
        return False
    else:
        print("\n✅ Installation verification PASSED!")
        print("\nNext steps:")
        print("  1. Copy examples/config.example.yaml to ~/.config/evening-telegram/config.yaml")
        print("  2. Edit the config with your credentials")
        print("  3. Run: evening-telegram")
        return True


if __name__ == "__main__":
    success = verify_installation()
    sys.exit(0 if success else 1)
