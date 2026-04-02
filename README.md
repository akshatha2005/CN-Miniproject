#  Online Music Streaming Server
### Secure TCP-Based Client-Server Audio Streaming | Python | SSL/TLS

---

## Requirements Met

| Requirement | Status |
|-------------|--------|
| TCP sockets (low-level) |  `socket.SOCK_STREAM` |
| SSL/TLS secure communication |  All data encrypted |
| Multiple concurrent clients |  Threading per client |
| Network sockets only (no IPC) |  |
| Python |  |
| GitHub documentation | This README |

---

## Project Structure

```
music_streaming/
├── server.py       # Member 1 — TCP server, SSL, multi-client streaming
├── client.py       # Member 2 — SSL client, buffering, pygame playback
├── qos.py          # Member 3 — latency, throughput, buffer delay, QoS report
├── cert.pem        # SSL certificate (generate — see below)
├── key.pem         # SSL private key  (generate — see below)
├── music/          # Place .mp3 / .wav / .ogg files here
├── downloads/      # Received files saved here (auto-created)
└── README.md
```

---

## Setup

### 1. Install Dependencies
```bash
pip install pygame
```

### 2. Generate SSL Certificate (Self-Signed)
Run this once in the project folder:
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```
When prompted, you can press Enter for all fields or fill them in.

This creates:
- `cert.pem` — the public certificate (shared with clients)
- `key.pem` — the private key (kept on server only)

### 3. Add Music Files
Place `.mp3`, `.wav`, or `.ogg` files into the `music/` folder.

---

## How to Run

### Terminal 1 — Start Server
```bash
python server.py
```

### Terminal 2 — Start Client
```bash
python client.py
```

### QoS Latency Test (while server is running)
```bash
python qos.py --ping 127.0.0.1 5000
```

### Multiple Clients (open more terminals)
```bash
python client.py   # Terminal 3
python client.py   # Terminal 4
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    SERVER                           │
│                                                     │
│  start_server()                                     │
│    └─► SSL wrap socket (cert.pem + key.pem)         │
│    └─► accept() loop                                │
│          └─► new thread → handle_client()           │
│                └─► send song list                   │
│                └─► receive request                  │
│                └─► stream_file() in chunks          │
└─────────────────────────────────────────────────────┘
           ▲ SSL/TLS encrypted tunnel ▼
┌─────────────────────────────────────────────────────┐
│                    CLIENT                           │
│                                                     │
│  run_client()                                       │
│    └─► SSL wrap socket (cert.pem for verification)  │
│    └─► connect()                                    │
│    └─► receive song list → display menu             │
│    └─► send request                                 │
│    └─► receive_and_buffer()                         │
│          └─► accumulate chunks                      │
│          └─► after 8 chunks → start playback thread │
│    └─► print QoS report                             │
└─────────────────────────────────────────────────────┘
```

---

## Protocol Design

All control messages use a **length-prefix JSON protocol**:

```
┌──────────────┬──────────────────────────────┐
│  4 bytes     │  N bytes                     │
│  (length)    │  (JSON payload)              │
└──────────────┴──────────────────────────────┘
```

### Message Types

| Direction | Type | Fields |
|-----------|------|--------|
| Server → Client | `song_list` | `songs: []` |
| Client → Server | `request` | `filename` |
| Server → Client | `stream_start` | `filename, file_size, chunk_size` |
| Server → Client | `stream_end` | `bytes_sent, duration` |
| Client → Server | `disconnect` | — |
| Server → Client | `error` | `msg` |

After `stream_start`, raw audio bytes are sent directly (no JSON wrapper) in `chunk_size` packets until `file_size` bytes are transferred.

---

## SSL/TLS Implementation

- **Protocol**: TLS 1.2 minimum (`ssl.TLSVersion.TLSv1_2`)
- **Certificate**: Self-signed X.509 (RSA 4096-bit)
- **Scope**: ALL communication encrypted — song list, requests, audio chunks
- **Verification**: Client verifies server certificate via `cert.pem`

```python
# Server wraps socket with SSL
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('cert.pem', 'key.pem')
secure_sock = context.wrap_socket(raw_sock, server_side=True)

# Client connects via SSL
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_verify_locations('cert.pem')
conn = context.wrap_socket(raw_sock, server_hostname=host)
```

---

## QoS Parameters

| Metric | Method | Where |
|--------|--------|-------|
| **Latency** | SSL TCP connect RTT (5 samples) | `python qos.py --ping` |
| **Throughput** | bytes ÷ elapsed time → KB/s, Mbps | After each stream |
| **Buffer Delay** | Time from connect → playback start | After each stream |
| **Packet Loss** | Chunks expected vs received | After each stream |
| **Server Throughput** | Bytes sent ÷ stream duration | Server terminal logs |

---

## TCP vs UDP — Design Decision

**TCP was chosen** because:
- Audio streaming requires **reliable, ordered delivery** — dropped packets cause audio corruption
- TCP handles retransmission automatically
- SSL/TLS is built on top of TCP

UDP would require custom retransmission logic and is better suited for real-time video calls where latency matters more than completeness.

---

## Team

| Member | Role | File |
|--------|------|------|
| Member 1 | Server, SSL setup, multi-client threading | `server.py` |
| Member 2 | Client, SSL connection, buffering, playback | `client.py` |
| Member 3 | QoS metrics, latency test, documentation | `qos.py`, `README.md` |
