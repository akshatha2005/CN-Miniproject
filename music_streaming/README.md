# Online Music Streaming Server
### TCP-Based Client-Server Audio Streaming | Python
---
## Project Structure
```
music_streaming/
├── server.py          # Member 1 – TCP server, multi-client streaming
├── client.py          # Member 2 – Client app, buffering, playback
├── qos.py             # Member 3 – QoS evaluation (latency, throughput, buffer)
├── music/             # Place your .mp3 / .wav / .ogg files here
├── downloads/         # Client-saved files appear here (auto-created)
└── README.md
```
---
## Requirements
- Python 3.7+
- pygame (for audio playback)
Install dependencies:
```bash
pip install pygame
```
---
## How to Run
### Step 1 – Add Music Files
Put your `.mp3`, `.wav`, or `.ogg` audio files into the `music/` folder:
```
music_streaming/
└── music/
    ├── song1.mp3
    ├── song2.wav
    └── ...
```
### Step 2 – Start the Server

Open a terminal and run:
```bash
python server.py
```
You should see:
```
==================================================
  Music Streaming Server started on port 5000
  Music folder : ./music/
  Chunk size   : 4096 bytes
  Songs found  : 2
    • song1.mp3
    • song2.wav
==================================================
Waiting for clients...
```
### Step 3 – Start the Client

Open a **second terminal** and run:
```bash
python client.py
```
You will see the song list and can select a track to stream.
### Step 4 – QoS Latency Test
To measure latency separately (while server is running):
```bash
python qos.py --ping 127.0.0.1 5000
```
---
## Testing with Multiple Clients

Open multiple terminals and run `python client.py` in each.  
The server handles each client in its own thread simultaneously.
---
## Configuration

Edit the top of each file to change defaults:

| File | Variable | Default | Description |
|------|----------|---------|-------------|
| server.py | `HOST` | `0.0.0.0` | Listen on all interfaces |
| server.py | `PORT` | `5000` | Server port |
| server.py | `CHUNK_SIZE` | `4096` | Bytes per packet |
| server.py | `BUFFER_DELAY` | `0.01` | Delay between chunks (s) |
| client.py | `SERVER_HOST` | `127.0.0.1` | Server IP address |
| client.py | `SERVER_PORT` | `5000` | Server port |
| client.py | `BUFFER_FILL_THRESHOLD` | `8` | Chunks to buffer before playback |

---

## QoS Parameters Measured

| Metric | How | Where |
|--------|-----|-------|
| **Latency** | TCP connect RTT (5 samples) | `qos.py --ping` |
| **Throughput** | Bytes received ÷ elapsed time | Shown after each stream |
| **Buffer Delay** | Time from connect to playback start | Shown after each stream |
| **Packet Integrity** | Chunks expected vs received | Shown after each stream |
| **Server Throughput** | Bytes sent ÷ stream duration | Shown in server logs |
---
## How It Works

```
CLIENT                          SERVER
  |                               |
  |──── TCP Connect ─────────────►|
  |◄─── Song List (JSON) ─────────|
  |                               |
  |──── Request: song.mp3 ───────►|
  |◄─── stream_start (metadata) ──|
  |◄═══ Audio chunks (4KB each) ══|  ← streaming
  |  [buffer fills → playback]    |
  |◄─── stream_end (stats) ───────|
  |                               |
  |  [QoS report printed]         |
  |──── disconnect ──────────────►|
```
---
## Team
| Member | Role | Files |
|--------|------|-------|
| Member 1 | Server-side streaming + multi-client management | `server.py` |
| Member 2 | Client app + audio playback + buffering | `client.py` |
| Member 3 | QoS evaluation + packet management + documentation | `qos.py`, `README.md` |
