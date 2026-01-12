"""
Gmail Message Parser

Parses Gmail API message format into our internal Email model.
"""

import base64
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header
import html

import structlog

logger = structlog.get_logger()


class GmailParser:
    """
    Parser for Gmail API messages
    """

    @staticmethod
    def parse_message(gmail_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Gmail API message format into our internal format.

        Args:
            gmail_message: Raw message from Gmail API

        Returns:
            Parsed email data
        """
        message_id = gmail_message["id"]
        thread_id = gmail_message["threadId"]

        # Extract headers
        headers = GmailParser._extract_headers(gmail_message)

        # Extract body
        body, snippet = GmailParser._extract_body(gmail_message)

        # Parse timestamp
        timestamp = datetime.fromtimestamp(
            int(gmail_message.get("internalDate", 0)) / 1000
        )

        # Extract labels
        labels = gmail_message.get("labelIds", [])

        # Determine flags
        is_read = "UNREAD" not in labels
        is_flagged = "STARRED" in labels
        has_attachments = GmailParser._has_attachments(gmail_message)

        parsed = {
            "id": message_id,
            "thread_id": thread_id,
            "from_address": headers.get("from", ""),
            "to_addresses": GmailParser._parse_addresses(headers.get("to", "")),
            "cc_addresses": GmailParser._parse_addresses(headers.get("cc", "")),
            "subject": headers.get("subject", "(No Subject)"),
            "body": body,
            "snippet": snippet or gmail_message.get("snippet", ""),
            "timestamp": timestamp,
            "labels": labels,
            "is_read": is_read,
            "is_flagged": is_flagged,
            "has_attachments": has_attachments,
            "metadata": {
                "history_id": gmail_message.get("historyId"),
                "size_estimate": gmail_message.get("sizeEstimate", 0),
                "message_id_header": headers.get("message-id", ""),
                "in_reply_to": headers.get("in-reply-to", ""),
                "references": headers.get("references", ""),
            },
        }

        logger.debug(
            "gmail_message_parsed",
            message_id=message_id,
            from_address=parsed["from_address"],
            subject=parsed["subject"][:50],
        )

        return parsed

    @staticmethod
    def _extract_headers(gmail_message: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract headers from Gmail message.

        Args:
            gmail_message: Raw Gmail message

        Returns:
            Dictionary of headers
        """
        headers = {}

        payload = gmail_message.get("payload", {})
        header_list = payload.get("headers", [])

        for header in header_list:
            name = header.get("name", "").lower()
            value = header.get("value", "")
            headers[name] = value

        return headers

    @staticmethod
    def _extract_body(gmail_message: Dict[str, Any]) -> tuple[str, Optional[str]]:
        """
        Extract body content from Gmail message.
        Handles both plain text and HTML emails.

        Args:
            gmail_message: Raw Gmail message

        Returns:
            Tuple of (body_text, snippet)
        """
        payload = gmail_message.get("payload", {})

        # Try to get plain text body
        body_text = GmailParser._get_body_from_parts(payload, "text/plain")

        # If no plain text, try HTML
        if not body_text:
            html_body = GmailParser._get_body_from_parts(payload, "text/html")
            if html_body:
                body_text = GmailParser._html_to_text(html_body)

        # Get snippet (short preview)
        snippet = gmail_message.get("snippet", "")

        return body_text or "", snippet

    @staticmethod
    def _get_body_from_parts(payload: Dict[str, Any], mime_type: str) -> Optional[str]:
        """
        Recursively extract body of specific MIME type from message parts.

        Args:
            payload: Message payload
            mime_type: MIME type to extract (e.g., 'text/plain', 'text/html')

        Returns:
            Body text or None
        """
        # Check if this payload is the type we want
        if payload.get("mimeType") == mime_type:
            body_data = payload.get("body", {}).get("data")
            if body_data:
                return GmailParser._decode_base64(body_data)

        # Check parts recursively
        parts = payload.get("parts", [])
        for part in parts:
            result = GmailParser._get_body_from_parts(part, mime_type)
            if result:
                return result

        return None

    @staticmethod
    def _decode_base64(data: str) -> str:
        """
        Decode base64 URL-safe encoded data.

        Args:
            data: Base64 encoded string

        Returns:
            Decoded string
        """
        try:
            decoded_bytes = base64.urlsafe_b64decode(data)
            return decoded_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("base64_decode_error", error=str(e))
            return ""

    @staticmethod
    def _html_to_text(html_content: str) -> str:
        """
        Convert HTML to plain text.
        Simple implementation - strips tags and decodes entities.

        Args:
            html_content: HTML string

        Returns:
            Plain text
        """
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", html_content)

        # Decode HTML entities
        text = html.unescape(text)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    @staticmethod
    def _parse_addresses(address_string: str) -> List[str]:
        """
        Parse comma-separated email addresses.

        Args:
            address_string: String with email addresses

        Returns:
            List of email addresses
        """
        if not address_string:
            return []

        # Simple email extraction using regex
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, address_string)

        return emails

    @staticmethod
    def _has_attachments(gmail_message: Dict[str, Any]) -> bool:
        """
        Check if message has attachments.

        Args:
            gmail_message: Raw Gmail message

        Returns:
            True if message has attachments
        """
        payload = gmail_message.get("payload", {})

        # Check if any part is an attachment
        def check_parts(parts: List[Dict[str, Any]]) -> bool:
            for part in parts:
                # Check if this part is an attachment
                if part.get("filename") and part.get("body", {}).get("attachmentId"):
                    return True

                # Check nested parts
                if "parts" in part:
                    if check_parts(part["parts"]):
                        return True

            return False

        parts = payload.get("parts", [])
        return check_parts(parts)

    @staticmethod
    def parse_thread(gmail_thread: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse all messages in a Gmail thread.

        Args:
            gmail_thread: Raw thread from Gmail API

        Returns:
            List of parsed email messages
        """
        messages = gmail_thread.get("messages", [])
        parsed_messages = []

        for message in messages:
            try:
                parsed = GmailParser.parse_message(message)
                parsed_messages.append(parsed)
            except Exception as e:
                logger.error(
                    "thread_message_parse_error",
                    error=str(e),
                    message_id=message.get("id", "unknown"),
                )

        logger.info(
            "gmail_thread_parsed",
            thread_id=gmail_thread.get("id"),
            message_count=len(parsed_messages),
        )

        return parsed_messages

    @staticmethod
    def decode_header_value(header_value: str) -> str:
        """
        Decode RFC 2047 encoded header value.

        Args:
            header_value: Raw header value

        Returns:
            Decoded string
        """
        decoded_parts = decode_header(header_value)
        decoded_string = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    decoded_string += part.decode(encoding, errors="replace")
                else:
                    decoded_string += part.decode("utf-8", errors="replace")
            else:
                decoded_string += part

        return decoded_string
