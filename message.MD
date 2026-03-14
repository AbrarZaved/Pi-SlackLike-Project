Here is a clean **Markdown (`.md`) version** of your documentation. You can save it as something like `websocket_protocol.md`.

````md
# Realtime Chat WebSocket Protocol

This document describes the WebSocket message protocol used for realtime chat features such as sending messages, reactions, history loading, and people search.

---

# 1. Send a Chat Message

Client → Server  
(Channel / Group / DM all use the same payload)

```json
{
  "type": "message.send",
  "content": "Hello"
}
````

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
    "reactions": []
  }
}
```

---

# 2. Message Reactions

## Add Reaction

Client → Server

```json
{
  "type": "reaction.add",
  "message_id": 456,
  "emoji": "👍"
}
```

## Remove Reaction

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
  "reactions": [
    {
      "emoji": "👍",
      "count": 2,
      "me": true
    }
  ]
}
```

---

# 3. Message History (On Connect)

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

---

# 4. People Search Socket

## Search Users

Client → Server

```json
{
  "type": "people.search",
  "query": "john"
}
```

## Search Results

Server → Client

```json
{
  "type": "people.results",
  "results": [
    {
      "id": 7,
      "name": "John",
      "email": "john@example.com",
      "phone_number": "..."
    }
  ]
}
```

---

# Notes

* All real-time features use WebSocket communication.
* Messages are broadcast to all members of the room/channel.
* Reaction updates always return the full aggregated reaction list for the message.
* Message history is automatically sent when the connection is established.

```

If you want, I can also help you turn this into **a professional API spec style (like Slack / Discord docs)** with:

- message schemas  
- event tables  
- state diagrams  
- Django Channels implementation structure  

which would be **much better for maintaining your Slack-like project backend**.
```
