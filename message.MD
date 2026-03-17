# Realtime Chat WebSocket Protocol

This document describes the WebSocket message protocol used for realtime chat features such as sending messages, reactions, and history loading.

---

## 1) Send a Chat Message

Client → Server (Channel / Group / DM all use the same payload shape)

```json
{
  "type": "message.send",
  "content": "Hello"
}
```

### Optional: Reply to a Message

```json
{
  "type": "message.send",
  "content": "Replying to you",
  "reply_to": 123
}
```

### Optional: Forward a Message

You can forward a message even with empty content.

```json
{
  "type": "message.send",
  "forward_from": 123
}
```

### Server Broadcast

Server sends the new message to everyone in the room.

```json
{
  "type": "message.new",
  "message": {
    "id": 456,
    "content": "Hello",
    "created_at": "2026-03-14T08:40:12.123456+00:00",
    "sender": {
      "id": 1,
      "name": "Alice",
      "email": "a@example.com"
    },
    "reply_to": null,
    "forwarded_from": null,
    "reactions": [],
    "attachments": []
  }
}
```

---

## 2) Media / Attachments

Binary data is uploaded over HTTP; chat messages reference uploaded attachments by `attachment_ids`.

### 2.1 Upload

Client → Server (HTTP)

`POST /api/v1/communication/chat/uploads/` (multipart form)

- `file`: the uploaded file
- `kind`: one of `image`, `audio`, `video`, `file` (optional, defaults to `file`)

Response (example):

```json
{
  "id": 10,
  "kind": "file",
  "url": "http://localhost:8000/media/chat_attachments/<...>",
  "original_name": "hello.txt",
  "content_type": "text/plain",
  "size": 11,
  "created_at": "2026-03-17T12:00:00.000000+00:00"
}
```

### 2.2 Send a message with attachments

Client → Server (WebSocket)

```json
{
  "type": "message.send",
  "content": "",
  "attachment_ids": [10]
}
```

The broadcast message includes an `attachments` array:

```json
{
  "type": "message.new",
  "message": {
    "id": 457,
    "content": "",
    "created_at": "2026-03-17T12:00:01.000000+00:00",
    "sender": { "id": 1, "name": "Alice", "email": "a@example.com" },
    "reply_to": null,
    "forwarded_from": null,
    "reactions": [],
    "attachments": [
      {
        "id": 10,
        "kind": "file",
        "url": "/media/chat_attachments/<...>",
        "original_name": "hello.txt",
        "content_type": "text/plain",
        "size": 11,
        "created_at": "2026-03-17T12:00:00.000000+00:00"
      }
    ]
  }
}
```

---

## 3) Mentions (@name)

Mentions are done by including `@` + the target user's display name inside the message `content`.

Client → Server (same `message.send` event)

```json
{
  "type": "message.send",
  "content": "Hello @Alice"
}
```

Mentions also support spaces in the name:

```json
{
  "type": "message.send",
  "content": "Hello @Alice Smith"
}
```

### Matching rules (how the backend detects mentions)

- Mention token format: `@Name` (spaces allowed inside the name, but not at the beginning/end).
- Matching is against `User.name` for users who are participants in the room.
  - Channels: members of the channel
  - Groups: members of the group
- Matching is case-insensitive and ignores whitespace.
  - Example: `@AliceSmith`, `@Alice Smith`, and `@ALICE   SMITH` all match the same user name.

### Notifications websocket (mention alert)

If a user is mentioned and is not already connected to the same room websocket, they receive a notification on `/ws/notifications/` with `notification_type = chat.mention`.

Server → Client

```json
{
  "type": "notification.new",
  "notification": {
    "id": 123,
    "notification_type": "chat.mention",
    "title": "New message",
    "body": "Hello @Alice Smith",
    "data": {
      "channel_id": 1,
      "channel_name": "General",
      "message_id": 456,
      "sender_id": 10,
      "is_mention": true
    },
    "is_read": false,
    "read_at": null,
    "created_at": "2026-03-17T12:00:00.000000+00:00"
  }
}
```

---

## 4) Message Reactions

### Add Reaction

Client → Server

```json
{
  "type": "reaction.add",
  "message_id": 456,
  "emoji": "👍"
}
```

### Remove Reaction

Client → Server

```json
{
  "type": "reaction.remove",
  "message_id": 456,
  "emoji": "👍"
}
```

### Server Broadcast

```json
{
  "type": "reaction.updated",
  "message_id": 456,
  "reactions": [{ "emoji": "👍", "count": 2, "me": true }]
}
```

---

## 5) Message History (On Connect)

Immediately after a client connects, the server sends recent messages.

Server → Client

```json
{
  "type": "history",
  "items": [
    /* message objects */
  ]
}
```
