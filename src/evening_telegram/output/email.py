"""Email delivery for newspaper reports."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import structlog

from ..config.models import EmailConfig
from ..models.data import Newspaper

logger = structlog.get_logger(__name__)


async def send_email_report(
    newspaper: Newspaper,
    html_content: str,
    config: EmailConfig,
) -> None:
    """
    Send newspaper as HTML email.

    Args:
        newspaper: Generated newspaper
        html_content: Complete HTML content
        config: Email configuration
    """
    subject = f"{newspaper.title} - {newspaper.edition_date.strftime('%B %d, %Y')}"

    # Create multipart message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{config.from_name} <{config.from_address}>"
    message["To"] = ", ".join(config.to)

    # Create plain text version (simplified)
    text_content = _generate_text_version(newspaper)
    text_part = MIMEText(text_content, "plain", "utf-8")
    message.attach(text_part)

    # Attach HTML version
    html_part = MIMEText(html_content, "html", "utf-8")
    message.attach(html_part)

    # Send email
    try:
        if config.use_tls:
            await aiosmtplib.send(
                message,
                hostname=config.smtp_host,
                port=config.smtp_port,
                username=config.smtp_user,
                password=config.smtp_password,
                start_tls=True,
            )
        else:
            await aiosmtplib.send(
                message,
                hostname=config.smtp_host,
                port=config.smtp_port,
                username=config.smtp_user,
                password=config.smtp_password,
            )

        logger.info("Successfully sent email report", recipients=config.to)
    except Exception as e:
        logger.error("Failed to send email report", error=str(e), error_type=type(e).__name__)
        raise


def _generate_text_version(newspaper: Newspaper) -> str:
    """
    Generate plain text version of newspaper.

    Args:
        newspaper: Newspaper data

    Returns:
        Plain text representation
    """
    lines = [
        newspaper.title,
        newspaper.tagline,
        newspaper.edition_date.strftime("%B %d, %Y"),
        "",
        "=" * 60,
        "",
    ]

    for section in newspaper.sections:
        lines.append(f"\n{section.name}")
        lines.append("-" * len(section.name))
        lines.append("")

        for article in section.articles:
            lines.append(f"• {article.headline}")
            if article.subheadline:
                lines.append(f"  {article.subheadline}")
            lines.append("")

    lines.extend(
        [
            "=" * 60,
            "",
            f"{newspaper.total_articles} articles from {newspaper.total_channels} channels",
            "",
            "This is a plain text version. View the HTML version for the complete experience.",
        ]
    )

    return "\n".join(lines)
