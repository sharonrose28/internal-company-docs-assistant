from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

import emoji
import tiktoken


@dataclass(frozen=True, slots=True)
class SlackMessage:
    channel: str
    username: str
    timestamp: str
    text: str
    thread_ts: str | None


@dataclass(frozen=True, slots=True)
class SlackConversation:
    channel: str
    thread: str | None
    participants: tuple[str, ...]
    messages: tuple[SlackMessage, ...]


@dataclass(frozen=True, slots=True)
class SlackChunk:
    text: str
    channel: str
    thread: str | None
    participants: tuple[str, ...]
    token_count: int


class SlackExportError(RuntimeError):
    pass


class SlackExportParser:
    """Normalizes Slack JSON, reconstructs threads, and groups unthreaded channel sessions."""

    _alias_emoji = re.compile(r"(?<!\w):[+\-\w]+:(?!\w)")
    _image_url = re.compile(r"<?https?://\S+?\.(?:png|jpe?g|gif|webp)(?:\?\S*)?>?", re.IGNORECASE)

    def __init__(self, session_gap_minutes: int = 30):
        self.session_gap_seconds = session_gap_minutes * 60

    def parse(self, path: Path) -> list[SlackConversation]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SlackExportError("Slack export must be valid UTF-8 JSON") from exc

        raw_messages = self._message_sets(payload, path.stem)
        messages: list[SlackMessage] = []
        for channel, items, users in raw_messages:
            for item in items:
                parsed = self._parse_message(item, channel, users)
                if parsed:
                    messages.append(parsed)
                for reply in item.get("replies", []) if isinstance(item, dict) else []:
                    if isinstance(reply, dict):
                        nested = dict(reply)
                        nested.setdefault("thread_ts", item.get("thread_ts") or item.get("ts"))
                        parsed_reply = self._parse_message(nested, channel, users)
                        if parsed_reply:
                            messages.append(parsed_reply)
        return self._conversations(self._deduplicate(messages))

    def _message_sets(self, payload, default_channel: str) -> list[tuple[str, list[dict], dict[str, str]]]:
        users: dict[str, str] = {}
        if isinstance(payload, dict):
            users = self._users(payload.get("users", []))
            if isinstance(payload.get("messages"), list):
                channel = self._channel_name(payload, default_channel)
                return [(channel, payload["messages"], users)]
            if isinstance(payload.get("channels"), list):
                sets = []
                for channel_data in payload["channels"]:
                    if isinstance(channel_data, dict) and isinstance(channel_data.get("messages"), list):
                        sets.append((self._channel_name(channel_data, default_channel), channel_data["messages"], users))
                if sets:
                    return sets
        if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
            return [(default_channel, payload, users)]
        raise SlackExportError("Expected a message array or an object containing messages/channels")

    @staticmethod
    def _users(raw_users: list) -> dict[str, str]:
        result = {}
        for user in raw_users if isinstance(raw_users, list) else []:
            if not isinstance(user, dict) or not user.get("id"):
                continue
            profile = user.get("profile") if isinstance(user.get("profile"), dict) else {}
            result[user["id"]] = (
                profile.get("display_name") or profile.get("real_name") or user.get("name") or user["id"]
            )
        return result

    @staticmethod
    def _channel_name(payload: dict, fallback: str) -> str:
        value = payload.get("channel_name") or payload.get("name") or payload.get("channel") or fallback
        return str(value).lstrip("#")[:255]

    def _parse_message(self, item: dict, channel: str, users: dict[str, str]) -> SlackMessage | None:
        if not isinstance(item, dict) or item.get("subtype") not in {None, ""}:
            return None
        timestamp = str(item.get("ts") or item.get("timestamp") or "").strip()
        if not self._valid_timestamp(timestamp):
            return None
        text = self._clean_text(str(item.get("text") or ""))
        if not text or self._emoji_only(text):
            return None
        profile = item.get("user_profile") if isinstance(item.get("user_profile"), dict) else {}
        user_id = str(item.get("user") or "")
        username = str(
            item.get("username") or profile.get("display_name") or profile.get("real_name")
            or users.get(user_id) or user_id or "unknown"
        )[:255]
        thread_ts = str(item.get("thread_ts") or "").strip() or None
        return SlackMessage(channel, username, timestamp, text, thread_ts)

    def _clean_text(self, text: str) -> str:
        text = self._image_url.sub("", text)
        return re.sub(r"\s+", " ", text).strip()

    def _emoji_only(self, text: str) -> bool:
        without_unicode = emoji.replace_emoji(text, replace="")
        without_aliases = self._alias_emoji.sub("", without_unicode)
        return not re.sub(r"[\s\W_]+", "", without_aliases)

    @staticmethod
    def _valid_timestamp(value: str) -> bool:
        try:
            Decimal(value)
            return True
        except InvalidOperation:
            return False

    @staticmethod
    def _deduplicate(messages: list[SlackMessage]) -> list[SlackMessage]:
        unique = {(message.channel, message.timestamp, message.username, message.text): message for message in messages}
        return sorted(unique.values(), key=lambda message: (message.channel, Decimal(message.timestamp)))

    def _conversations(self, messages: list[SlackMessage]) -> list[SlackConversation]:
        threaded: dict[tuple[str, str], list[SlackMessage]] = {}
        thread_roots = {(message.channel, message.thread_ts) for message in messages if message.thread_ts}
        unthreaded: dict[str, list[SlackMessage]] = {}
        for message in messages:
            key = (message.channel, message.thread_ts or message.timestamp)
            if message.thread_ts or key in thread_roots:
                threaded.setdefault(key, []).append(message)
            else:
                unthreaded.setdefault(message.channel, []).append(message)

        result = [self._conversation(channel, thread, items) for (channel, thread), items in threaded.items()]
        for channel, items in unthreaded.items():
            session: list[SlackMessage] = []
            previous: Decimal | None = None
            for message in items:
                current = Decimal(message.timestamp)
                if session and previous is not None and current - previous > self.session_gap_seconds:
                    result.append(self._conversation(channel, None, session))
                    session = []
                session.append(message)
                previous = current
            if session:
                result.append(self._conversation(channel, None, session))
        return sorted(result, key=lambda conversation: Decimal(conversation.messages[0].timestamp))

    @staticmethod
    def _conversation(channel: str, thread: str | None, messages: list[SlackMessage]) -> SlackConversation:
        ordered = tuple(sorted(messages, key=lambda message: Decimal(message.timestamp)))
        participants = tuple(dict.fromkeys(message.username for message in ordered))
        return SlackConversation(channel, thread, participants, ordered)


class SlackConversationChunker:
    """Chunks formatted messages without crossing conversation or thread boundaries."""

    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("Require chunk_size > overlap >= 0")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def split(self, conversations: list[SlackConversation]) -> list[SlackChunk]:
        chunks: list[SlackChunk] = []
        for conversation in conversations:
            rendered = "\n".join(self._render(message) for message in conversation.messages)
            tokens = self.encoding.encode(rendered)
            start = 0
            while start < len(tokens):
                end = min(start + self.chunk_size, len(tokens))
                text = self.encoding.decode(tokens[start:end]).strip()
                if text:
                    chunks.append(SlackChunk(
                        text=text,
                        channel=conversation.channel,
                        thread=conversation.thread,
                        participants=conversation.participants,
                        token_count=end - start,
                    ))
                if end == len(tokens):
                    break
                start = end - self.overlap
        return chunks

    @staticmethod
    def _render(message: SlackMessage) -> str:
        timestamp = datetime.fromtimestamp(float(message.timestamp), tz=UTC).isoformat()
        return f"[{timestamp}] {message.username}: {message.text}"
