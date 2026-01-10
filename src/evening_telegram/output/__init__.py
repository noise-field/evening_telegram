"""Output generation and delivery."""

from .email import send_email_report
from .html import generate_html

__all__ = [
    "generate_html",
    "send_email_report",
]
