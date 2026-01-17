"""HTML output generation using Jinja2."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models.data import Newspaper

logger = structlog.get_logger(__name__)


def _to_timezone(dt: datetime, tz: str) -> datetime:
    """Convert datetime to specified timezone."""
    if tz == "local":
        return dt.astimezone()
    else:
        return dt.astimezone(ZoneInfo(tz))


def generate_html(
    newspaper: Newspaper, output_path: Path, channels: list[dict[str, str]], timezone: str = "local"
) -> str:
    """
    Generate HTML newspaper from data.

    Args:
        newspaper: Newspaper data
        output_path: Path to save HTML file
        channels: List of channel info dicts
        timezone: Target timezone for timestamp display ("local" or IANA timezone name)

    Returns:
        Path to generated HTML file as string
    """
    # Set up Jinja2 environment
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # Add custom filters
    env.filters["to_tz"] = lambda dt: _to_timezone(dt, timezone)
    env.filters["strftime"] = lambda dt, fmt: dt.strftime(fmt)

    template = env.get_template("newspaper.html")

    # Render template
    html_content = template.render(
        newspaper=newspaper,
        language=newspaper.language,
        channels=channels,
        timezone=timezone,
    )

    # Prepare output path (expand ~ and handle strftime formatting)
    output_path = Path(output_path).expanduser()

    # Handle strftime formatting in path
    if "%" in str(output_path):
        formatted_path = newspaper.edition_date.strftime(str(output_path))
        output_path = Path(formatted_path)

    # Create parent directories if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write HTML file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info("Generated HTML report", path=str(output_path))
    return str(output_path)
