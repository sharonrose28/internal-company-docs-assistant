import json
from pathlib import Path

from app.ingestion.slack import SlackConversationChunker, SlackExportParser


def test_parser_filters_noise_and_reconstructs_threads(tmp_path: Path):
    path = tmp_path / "engineering.json"
    path.write_text(json.dumps({
        "channel_name": "engineering",
        "users": [
            {"id": "U1", "profile": {"display_name": "alice"}},
            {"id": "U2", "profile": {"display_name": "bob"}},
        ],
        "messages": [
            {"user": "U1", "ts": "1700000000.000001", "text": "Deploy starts now"},
            {"user": "U2", "ts": "1700000001.000001", "thread_ts": "1700000000.000001", "text": "Watching metrics"},
            {"user": "U1", "ts": "1700000002.000001", "thread_ts": "1700000000.000001", "text": ":white_check_mark:"},
            {"user": "U1", "ts": "1700000003.000001", "text": "uploaded", "subtype": "file_share", "files": [{}]},
            {"user": "U1", "ts": "1700000004.000001", "text": "https://example.com/screenshot.png"},
            {"ts": "1700000005.000001", "text": "Alice joined", "subtype": "channel_join"},
        ],
    }), encoding="utf-8")

    conversations = SlackExportParser().parse(path)

    assert len(conversations) == 1
    assert conversations[0].channel == "engineering"
    assert conversations[0].thread == "1700000000.000001"
    assert conversations[0].participants == ("alice", "bob")
    assert [message.text for message in conversations[0].messages] == [
        "Deploy starts now", "Watching metrics"
    ]


def test_unthreaded_messages_split_on_inactivity(tmp_path: Path):
    path = tmp_path / "general.json"
    path.write_text(json.dumps([
        {"username": "alice", "ts": "1000.0", "text": "First"},
        {"username": "bob", "ts": "1100.0", "text": "Second"},
        {"username": "alice", "ts": "4000.0", "text": "Later"},
    ]), encoding="utf-8")
    conversations = SlackExportParser(session_gap_minutes=30).parse(path)
    assert len(conversations) == 2
    assert [len(item.messages) for item in conversations] == [2, 1]


def test_chunker_never_crosses_conversation_boundaries(tmp_path: Path):
    path = tmp_path / "support.json"
    path.write_text(json.dumps([
        {"username": "alice", "ts": "1000.0", "text": "First conversation"},
        {"username": "bob", "ts": "4000.0", "text": "Second conversation"},
    ]), encoding="utf-8")
    conversations = SlackExportParser().parse(path)
    chunks = SlackConversationChunker(chunk_size=100, overlap=20).split(conversations)
    assert len(chunks) == 2
    assert all(not ("First conversation" in chunk.text and "Second conversation" in chunk.text) for chunk in chunks)
