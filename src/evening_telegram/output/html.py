"""HTML output generation using Jinja2."""

import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models.data import Newspaper

logger = logging.getLogger(__name__)


def generate_html(newspaper: Newspaper, output_path: Path, channels: list[dict[str, str]]) -> str:
    """
    Generate HTML newspaper from data.

    Args:
        newspaper: Newspaper data
        output_path: Path to save HTML file
        channels: List of channel info dicts

    Returns:
        Path to generated HTML file as string
    """
    # Set up Jinja2 environment
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )

    template = env.get_template("newspaper.html")

    # Render template
    html_content = template.render(
        newspaper=newspaper,
        language=newspaper.language,
        channels=channels,
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

    logger.info(f"Generated HTML report at {output_path}")
    return str(output_path)
