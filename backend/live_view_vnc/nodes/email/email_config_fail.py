import asyncio
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple
from urllib import error, request

from utils.workflow_graph_state import WorkflowGraphState

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM_EMAIL = "hello@notify.processzero.co.uk"
DEFAULT_FROM_NAME = "Process Zero AI Automation"
DEFAULT_TIMEOUT_SECONDS = 20
HARDCODED_RESEND_API_KEY = "re_Q3RbGgxf_CC7yEFV67dpRiabHgpR93WsH"


def _load_schema_notification_email() -> str:
    """
    Read the single notification email from transformation rules store.
    Returns empty string when unavailable.
    """
    schema_store_path = Path(__file__).resolve().parents[2] / "transformation_rules.json"
    if not schema_store_path.exists():
        return ""

    try:
        payload = json.loads(schema_store_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    single_email = str(metadata.get("notification_email", "")).strip()
    if single_email:
        return single_email

    emails = metadata.get("notification_emails", [])
    if isinstance(emails, list) and emails:
        candidate = str(emails[0]).strip()
        return candidate
    if isinstance(emails, str):
        return emails.strip()
    return ""


def _resolve_notification_emails(state: WorkflowGraphState) -> List[str]:
    """Resolve recipient from env, then state config, then schema store."""
    configured = os.getenv("RESEND_TO_EMAILS") or os.getenv("RESEND_TO_EMAIL") or ""
    recipients = [item.strip() for item in configured.split(",") if item.strip()]
    if recipients:
        return [recipients[0]]

    global_settings = state.get("global_settings") or {}
    configured_from_state = (
        global_settings.get("failure_notification_emails")
        or global_settings.get("notification_emails")
        or []
    )
    if isinstance(configured_from_state, str):
        state_recipients = [item.strip() for item in configured_from_state.split(",") if item.strip()]
        if state_recipients:
            return [state_recipients[0]]
    if isinstance(configured_from_state, list):
        state_recipients = [str(item).strip() for item in configured_from_state if str(item).strip()]
        if state_recipients:
            return [state_recipients[0]]

    schema_email = _load_schema_notification_email()
    if schema_email:
        return [schema_email]

    return []


def _build_sender_identity() -> str:
    sender_name = os.getenv("RESEND_FROM_NAME", DEFAULT_FROM_NAME).strip() or DEFAULT_FROM_NAME
    sender_email = os.getenv("RESEND_FROM_EMAIL", DEFAULT_FROM_EMAIL).strip() or DEFAULT_FROM_EMAIL
    return f"{sender_name} <{sender_email}>"


def _send_failure_email(
    api_key: str,
    recipients: List[str],
    subject: str,
    html_body: str,
) -> Tuple[int, str]:
    payload = {
        "from": _build_sender_identity(),
        "to": recipients,
        "subject": subject,
        "html": html_body,
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    req = request.Request(
        RESEND_API_URL,
        data=payload_bytes,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
            return int(response.status), body
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), body


def _build_failure_html(step: str, error_message: str) -> str:
    now_utc = datetime.now(timezone.utc).isoformat()
    return (
        "<h2>Process Zero AI Automation - Workflow Failure</h2>"
        f"<p><strong>Time (UTC):</strong> {html.escape(now_utc)}</p>"
        f"<p><strong>Failed Step:</strong> {html.escape(step)}</p>"
        f"<p><strong>Error:</strong> {html.escape(error_message)}</p>"
    )


async def email_failure_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Send failure email and gracefully stop workflow.
    """
    print("📧 Node: Sending failure notification email...")

    browser_instance = state.get("browser_instance")
    if browser_instance is not None:
        try:
            await browser_instance.stop()
        except Exception as exc:
            print(f"  ⚠️ Failed to stop browser cleanly: {exc}")

    error_message = str(state.get("error_message", "Unknown error"))
    step = str(state.get("current_step", "unknown_step"))

    print(f"  ⚠️ Failure at step: {step}")
    print(f"  ⚠️ Error: {error_message}")

    api_key = (os.getenv("RESEND_API_KEY") or HARDCODED_RESEND_API_KEY).strip()
    recipients = _resolve_notification_emails(state)

    if not api_key:
        print("  ⚠️ RESEND_API_KEY not configured. Skipping failure email.")
        return {
            **state,
            "current_step": "email_sent",
            "email_delivery_status": "skipped_missing_api_key",
        }

    if not recipients:
        print(
            "  ⚠️ No recipient emails configured. Set RESEND_TO_EMAILS or "
            "global_settings.notification_emails."
        )
        return {
            **state,
            "current_step": "email_sent",
            "email_delivery_status": "skipped_missing_recipients",
        }

    subject = f"[Process Zero AI Automation] Workflow failure at step: {step}"
    html_body = _build_failure_html(step=step, error_message=error_message)
    status_code, body = await asyncio.to_thread(
        _send_failure_email,
        api_key,
        recipients,
        subject,
        html_body,
    )

    if 200 <= status_code < 300:
        print(f"  ✓ Failure email sent to {', '.join(recipients)}")
        print(f"  ℹ️ Resend response: {body}")
        return {
            **state,
            "current_step": "email_sent",
            "email_delivery_status": "sent",
        }

    print(f"  ✗ Failed to send email (HTTP {status_code}): {body}")
    return {
        **state,
        "current_step": "email_sent",
        "email_delivery_status": f"failed_http_{status_code}",
    }
