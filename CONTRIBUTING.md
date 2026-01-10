# Contributing to The Evening Telegram

Thank you for your interest in contributing to The Evening Telegram! This document provides guidelines and instructions for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- A Telegram account
- Access to an LLM API (OpenAI, Anthropic, or compatible)

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/EveningTelegram.git
   cd EveningTelegram
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Development Dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify Installation**
   ```bash
   python verify_installation.py
   ```

5. **Set Up Configuration**
   ```bash
   mkdir -p ~/.config/evening-telegram
   cp examples/config.example.yaml ~/.config/evening-telegram/config.yaml
   # Edit with your credentials
   ```

## Development Workflow

### Code Style

We use:
- **Ruff** for linting and formatting
- **MyPy** for type checking
- **Type hints** throughout the codebase

Run code quality checks:
```bash
# Format code
ruff format .

# Lint
ruff check .

# Type checking
mypy src/
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=evening_telegram --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v
```

### Making Changes

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Write clear, documented code
   - Add type hints
   - Follow existing code patterns
   - Update docstrings

3. **Add Tests**
   - Write tests for new features
   - Ensure existing tests pass
   - Aim for good coverage

4. **Update Documentation**
   - Update README.md if needed
   - Update docstrings
   - Add example configurations if relevant

5. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

   Use conventional commit messages:
   - `feat:` - New features
   - `fix:` - Bug fixes
   - `docs:` - Documentation changes
   - `refactor:` - Code refactoring
   - `test:` - Test additions/changes
   - `chore:` - Maintenance tasks

6. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a Pull Request on GitHub.

## Project Structure

```
evening-telegram/
├── src/evening_telegram/
│   ├── config/          # Configuration management
│   │   ├── models.py    # Pydantic config models
│   │   └── loader.py    # Config loading logic
│   ├── telegram/        # Telegram integration
│   │   ├── client.py    # Telethon wrapper
│   │   ├── fetcher.py   # Message fetching
│   │   └── bot.py       # Bot delivery
│   ├── processing/      # Core processing
│   │   ├── clusterer.py # LLM clustering
│   │   └── generator.py # Article generation
│   ├── llm/            # LLM integration
│   │   ├── client.py    # OpenAI-compatible client
│   │   ├── prompts.py   # Prompt templates
│   │   └── tracker.py   # Token tracking
│   ├── output/         # Output generation
│   │   ├── html.py      # HTML generation
│   │   ├── email.py     # Email delivery
│   │   └── telegram.py  # Telegram delivery
│   ├── state/          # State management
│   │   └── db.py        # SQLite operations
│   ├── models/         # Data models
│   │   └── data.py      # Core data structures
│   └── templates/      # Jinja2 templates
│       └── newspaper.html
└── tests/              # Test suite
```

## Areas for Contribution

### High Priority

- [ ] Unit tests for all modules
- [ ] Integration tests
- [ ] Error handling improvements
- [ ] Performance optimizations
- [ ] Better logging and debugging

### Features

- [ ] RSS feed output format
- [ ] PDF generation
- [ ] Custom CSS themes
- [ ] Multi-language output (single run)
- [ ] Keyword filtering
- [ ] Web UI for configuration
- [ ] Webhook support for real-time updates

### Documentation

- [ ] API documentation
- [ ] Architecture diagrams
- [ ] Video tutorials
- [ ] Deployment guides
- [ ] Troubleshooting guide

### Integrations

- [ ] Discord bot support
- [ ] Slack integration
- [ ] Matrix support
- [ ] RSS feed inputs
- [ ] Twitter/X integration

## Code Guidelines

### Python Style

- Follow PEP 8
- Use type hints everywhere
- Maximum line length: 100 characters
- Use descriptive variable names
- Add docstrings to all public functions/classes

### Docstring Format

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When something goes wrong
    """
```

### Error Handling

- Use specific exception types
- Add helpful error messages
- Log errors appropriately
- Clean up resources (use context managers)

### Async/Await

- Use `async def` for I/O operations
- Use `await` for async calls
- Use `asyncio.gather()` for parallel operations
- Close clients/connections properly

## Testing Guidelines

### Test Structure

```python
import pytest
from evening_telegram.module import function


def test_function_success():
    """Test successful execution."""
    result = function(valid_input)
    assert result == expected_output


def test_function_failure():
    """Test error handling."""
    with pytest.raises(ValueError):
        function(invalid_input)


@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function()
    assert result is not None
```

### Fixtures

Create reusable fixtures in `tests/conftest.py`:

```python
import pytest


@pytest.fixture
def sample_config():
    """Provide sample configuration."""
    return Config(...)


@pytest.fixture
def mock_llm_client():
    """Provide mocked LLM client."""
    # Mock implementation
    pass
```

## Pull Request Process

1. **Update Documentation**
   - README.md for user-facing changes
   - Docstrings for code changes
   - CHANGELOG.md if applicable

2. **Ensure Tests Pass**
   - All existing tests pass
   - New tests for new features
   - Coverage doesn't decrease

3. **Code Quality Checks**
   - Ruff formatting passes
   - Ruff linting passes
   - MyPy type checking passes

4. **PR Description**
   - Clear description of changes
   - Link to related issues
   - Screenshots if UI-related
   - Breaking changes highlighted

5. **Review Process**
   - Address reviewer comments
   - Keep PR focused and atomic
   - Squash commits if requested

## Reporting Bugs

### Before Reporting

- Check existing issues
- Verify it's not a configuration issue
- Test with latest version

### Bug Report Template

```markdown
## Description
Brief description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11.5]
- Installation method: [e.g., pip, source]
- Config snippet (redacted): [relevant config]

## Logs
```
Paste relevant log output here
```

## Additional Context
Any other relevant information
```

## Feature Requests

We welcome feature requests! Please:

1. Check if it's already been requested
2. Describe the use case clearly
3. Explain why it would be useful
4. Suggest implementation if possible

## Community Guidelines

- Be respectful and inclusive
- Help others learn and grow
- Give constructive feedback
- Follow the code of conduct

## Questions?

- Open a GitHub Discussion
- Check existing issues
- Read the documentation
- Ask in pull request comments

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to The Evening Telegram!
