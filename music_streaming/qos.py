"""
QoS Evaluation Module
Member 3: Packet management, latency/throughput/buffer delay measurement
"""
import time
import socket
import struct
import json
# ─────────────────────────────────────────────────────────────
# QoS Metrics
# ─────────────────────────────────────────────────────────────
def measure_latency(host: str, port: int, samples: int = 5) -> dict:
    """
    Measure round-trip latency to the server by timing a TCP connect.
    Returns min, max, avg latency in milliseconds.
    """
    latencies = []
    for i in range(samples):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            t_start = time.time()
            sock.connect((host, port))
            t_end = time.time()
            sock.close()
            rtt_ms = (t_end - t_start) * 1000
            latencies.append(rtt_ms)
            time.sleep(0.1)
        except Exception as e:
            print(f"[QoS] Latency sample {i+1} failed: {e}")
    if not latencies:
        return {'min_ms': None, 'max_ms': None, 'avg_ms': None, 'samples': 0}
    return {
        'min_ms': round(min(latencies), 3),
        'max_ms': round(max(latencies), 3),
        'avg_ms': round(sum(latencies) / len(latencies), 3),
        'samples': len(latencies),
        'all_ms': [round(l, 3) for l in latencies],
    }
def calculate_throughput(bytes_received: int, elapsed_seconds: float) -> dict:
    """
    Calculate throughput from total bytes and time taken.
    Returns KB/s and Mbps.
    """
    if elapsed_seconds <= 0:
        return {'kbps': 0.0, 'mbps': 0.0}
    kbps = (bytes_received / 1024) / elapsed_seconds
    mbps = (bytes_received * 8 / 1_000_000) / elapsed_seconds
    return {
        'bytes': bytes_received,
        'elapsed_s': round(elapsed_seconds, 3),
        'kbps': round(kbps, 2),
        'mbps': round(mbps, 4),
    }
def calculate_buffer_delay(start_time: float, buffer_fill_time: float) -> dict:
    """
    Buffer delay = time from connection start to when playback begins.
    """
    if start_time is None or buffer_fill_time is None:
        return {'buffer_delay_s': None}
    return {'buffer_delay_s': round(buffer_fill_time, 3)}
def calculate_packet_loss(chunks_expected: int, chunks_received: int) -> dict:
    """
    Estimate packet loss percentage.
    Over TCP, loss is 0% — but we track dropped/incomplete chunks.
    """
    if chunks_expected <= 0:
        return {'loss_pct': 0.0}
    lost = max(0, chunks_expected - chunks_received)
    loss_pct = (lost / chunks_expected) * 100
    return {
        'expected': chunks_expected,
        'received': chunks_received,
        'lost': lost,
        'loss_pct': round(loss_pct, 2),
    }
# ─────────────────────────────────────────────────────────────
# QoS Report Printer
# ─────────────────────────────────────────────────────────────
def print_qos_report(client_stats: dict, server_end_msg: dict = None):
    """
    Print a formatted QoS report combining client and server stats.

    client_stats keys:
        bytes_received, start_time, buffer_fill_time,
        playback_start_time, chunks_received
    """
    print("\n" + "=" * 52)
    print("    QoS Performance Report")
    print("=" * 52)
    # ── Throughput ──────────────────────────────────────────
    bytes_rx = client_stats.get('bytes_received', 0)
    start = client_stats.get('start_time')
    elapsed = (time.time() - start) if start else 0
    tp = calculate_throughput(bytes_rx, elapsed)
    print(f"\n  Throughput")
    print(f"    Bytes received   : {tp['bytes']:,} bytes")
    print(f"    Transfer time    : {tp['elapsed_s']} s")
    print(f"    Speed            : {tp['kbps']} KB/s  ({tp['mbps']} Mbps)")
    # ── Buffer Delay ────────────────────────────────────────
    buf_fill = client_stats.get('buffer_fill_time')
    bd = calculate_buffer_delay(start, buf_fill)
    print(f"\n  Buffer Delay")
    if bd['buffer_delay_s'] is not None:
        print(f"    Time to fill buffer : {bd['buffer_delay_s']} s")
    else:
        print(f"    Time to fill buffer : N/A")
    # ── Latency (measured separately via ping test) ─────────
    print(f"\n  Latency")
    print(f"    (Run 'python qos.py --ping <host>' for RTT measurement)")
    # ── Packet / Chunk integrity ─────────────────────────────
    chunks_rx = client_stats.get('chunks_received', 0)
    file_size = bytes_rx
    chunk_size = 4096
    chunks_expected = (file_size // chunk_size) + (1 if file_size % chunk_size else 0)
    pl = calculate_packet_loss(chunks_expected, chunks_rx)
    print(f"\n  Packet Integrity (TCP)")
    print(f"    Chunks expected  : {pl['expected']}")
    print(f"    Chunks received  : {pl['received']}")
    print(f"    Estimated loss   : {pl['loss_pct']}%  (TCP guarantees delivery)")
    # ── Server-side stats ───────────────────────────────────
    if server_end_msg and server_end_msg.get('type') == 'stream_end':
        print(f"\n  Server-Side Stats")
        print(f"    Bytes sent       : {server_end_msg.get('bytes_sent', 'N/A'):,}")
        print(f"    Stream duration  : {server_end_msg.get('duration', 'N/A')} s")
    print("\n" + "=" * 52)
# ─────────────────────────────────────────────────────────────
# Standalone latency test (run directly)
# ─────────────────────────────────────────────────────────────
def run_ping_test(host: str, port: int):
    print(f"\n[QoS] Measuring latency to {host}:{port} (5 samples)...")
    result = measure_latency(host, port, samples=5)
    print("\n" + "=" * 40)
    print("  📡  Latency Test Results")
    print("=" * 40)
    if result['avg_ms'] is not None:
        print(f"  Samples   : {result['samples']}")
        print(f"  Min RTT   : {result['min_ms']} ms")
        print(f"  Avg RTT   : {result['avg_ms']} ms")
        print(f"  Max RTT   : {result['max_ms']} ms")
        print(f"  All RTTs  : {result['all_ms']}")
    else:
        print("  Could not reach server.")
    print("=" * 40)
if __name__ == '__main__':
    import sys

    args = sys.argv[1:]
    if '--ping' in args:
        idx = args.index('--ping')
        host = args[idx + 1] if idx + 1 < len(args) else '127.0.0.1'
        port_arg = int(args[idx + 2]) if idx + 2 < len(args) else 5000
        run_ping_test(host, port_arg)
    else:
        print("Usage:")
        print("  python qos.py --ping <host> [port]")
        print("\nExample:")
        print("  python qos.py --ping 127.0.0.1 5000")
