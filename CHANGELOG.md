# Changelog

All notable changes to The Evening Telegram will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Future features will be listed here

## [0.1.0] - 2024-01-10

### Added
- Initial release of The Evening Telegram
- Telegram channel message fetching via MTProto (Telethon)
- LLM-based message deduplication and clustering
- Article generation with proper attribution
- HTML newspaper output with professional styling
- Telegram bot delivery
- Email delivery via SMTP
- SQLite-based state management for incremental runs
- Token usage tracking and reporting
- Configuration via YAML with environment variable overrides
- CLI interface with Click
- Comprehensive documentation and examples

### Features
- Smart deduplication of duplicate stories across sources
- Topic clustering with section assignment
- Multiple article types: Hard News, Opinion, Brief, Feature
- Responsive HTML design with newspaper-style typography
- Source attribution with links back to original messages
- Flexible time period configuration (lookback or explicit range)
- Dry-run mode for testing
- Verbose logging options
- Support for both public and private Telegram channels
- Forward tracking and attribution

### Documentation
- Complete README with installation and usage instructions
- Example configuration file with detailed comments
- CONTRIBUTING.md with development guidelines
- AGENTSPEC.md with detailed project specification
- Installation verification script

[Unreleased]: https://github.com/yourusername/EveningTelegram/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/EveningTelegram/releases/tag/v0.1.0
