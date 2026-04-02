"""
QoS Evaluation Module — SSL/TLS Secured
Member 3: Latency, throughput, buffer delay, packet integrity

Latency is measured over SSL handshake (real-world secure RTT)
"""

import time
import socket
import ssl
import os


# ─────────────────────────────────────────────────────────────
# Latency — measured over SSL (includes handshake time)
# ─────────────────────────────────────────────────────────────

def measure_latency(host: str, port: int, certfile: str = 'cert.pem',
                    samples: int = 5) -> dict:
    """
    Measure SSL round-trip latency by timing full TCP+SSL connect.
    Includes TLS handshake time — realistic secure RTT.
    """
    latencies = []

    for i in range(samples):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations(certfile)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_REQUIRED

            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.settimeout(3)
            secure_sock = context.wrap_socket(raw_sock, server_hostname=host)

            t_start = time.time()
            secure_sock.connect((host, port))
            t_end = time.time()

            secure_sock.close()
            rtt_ms = (t_end - t_start) * 1000
            latencies.append(rtt_ms)
            time.sleep(0.1)

        except Exception as e:
            print(f"[QoS] Sample {i+1} failed: {e}")

    if not latencies:
        return {'min_ms': None, 'max_ms': None, 'avg_ms': None, 'samples': 0}

    return {
        'min_ms':  round(min(latencies), 3),
        'max_ms':  round(max(latencies), 3),
        'avg_ms':  round(sum(latencies) / len(latencies), 3),
        'samples': len(latencies),
        'all_ms':  [round(l, 3) for l in latencies],
    }


# ─────────────────────────────────────────────────────────────
# Throughput
# ─────────────────────────────────────────────────────────────

def calculate_throughput(bytes_received: int, elapsed_seconds: float) -> dict:
    """Calculate KB/s and Mbps from bytes received and time taken."""
    if elapsed_seconds <= 0:
        return {'bytes': bytes_received, 'elapsed_s': 0,
                'kbps': 0.0, 'mbps': 0.0}
    return {
        'bytes':     bytes_received,
        'elapsed_s': round(elapsed_seconds, 3),
        'kbps':      round((bytes_received / 1024) / elapsed_seconds, 2),
        'mbps':      round((bytes_received * 8 / 1_000_000) / elapsed_seconds, 4),
    }


# ─────────────────────────────────────────────────────────────
# Buffer Delay
# ─────────────────────────────────────────────────────────────

def calculate_buffer_delay(start_time: float, buffer_fill_time: float) -> dict:
    """Time from transfer start to when playback begins."""
    if start_time is None or buffer_fill_time is None:
        return {'buffer_delay_s': None}
    return {'buffer_delay_s': round(buffer_fill_time, 3)}


# ─────────────────────────────────────────────────────────────
# Packet Loss
# ─────────────────────────────────────────────────────────────

def calculate_packet_loss(chunks_expected: int, chunks_received: int) -> dict:
    """Estimate packet loss (should be 0% over TCP/SSL)."""
    if chunks_expected <= 0:
        return {'loss_pct': 0.0, 'expected': 0, 'received': 0, 'lost': 0}
    lost = max(0, chunks_expected - chunks_received)
    return {
        'expected': chunks_expected,
        'received': chunks_received,
        'lost':     lost,
        'loss_pct': round((lost / chunks_expected) * 100, 2),
    }


# ─────────────────────────────────────────────────────────────
# QoS Report
# ─────────────────────────────────────────────────────────────

def print_qos_report(client_stats: dict, server_end_msg: dict = None):
    """Print full QoS report after each stream."""
    print("\n" + "=" * 52)
    print("  📊  QoS Performance Report  (SSL/TLS)")
    print("=" * 52)

    bytes_rx = client_stats.get('bytes_received', 0)
    start    = client_stats.get('start_time')
    elapsed  = (time.time() - start) if start else 0

    # Throughput
    tp = calculate_throughput(bytes_rx, elapsed)
    print(f"\n  Throughput")
    print(f"    Bytes received : {tp['bytes']:,} bytes")
    print(f"    Transfer time  : {tp['elapsed_s']} s")
    print(f"    Speed          : {tp['kbps']} KB/s  ({tp['mbps']} Mbps)")

    # Buffer Delay
    buf_fill = client_stats.get('buffer_fill_time')
    bd = calculate_buffer_delay(start, buf_fill)
    print(f"\n  Buffer Delay")
    if bd['buffer_delay_s'] is not None:
        print(f"    Time to buffer : {bd['buffer_delay_s']} s")
    else:
        print(f"    Time to buffer : N/A")

    # Latency note
    print(f"\n  Latency (SSL RTT)")
    print(f"    Run: python qos.py --ping 127.0.0.1 5000")

    # Packet integrity
    chunks_rx  = client_stats.get('chunks_received', 0)
    chunks_exp = (bytes_rx // 4096) + (1 if bytes_rx % 4096 else 0)
    pl = calculate_packet_loss(chunks_exp, chunks_rx)
    print(f"\n  Packet Integrity (TCP/SSL)")
    print(f"    Chunks expected : {pl['expected']}")
    print(f"    Chunks received : {pl['received']}")
    print(f"    Loss            : {pl['loss_pct']}%")

    # Server stats
    if server_end_msg and server_end_msg.get('type') == 'stream_end':
        print(f"\n  Server-Side Stats")
        print(f"    Bytes sent     : {server_end_msg.get('bytes_sent', 'N/A'):,}")
        print(f"    Stream time    : {server_end_msg.get('duration', 'N/A')} s")

    # Security info
    print(f"\n  Security")
    print(f"    Protocol       : SSL/TLS (TLS 1.2 minimum)")
    print(f"    Encryption     : All data encrypted end-to-end")
    print(f"    Certificate    : cert.pem (self-signed)")

    print("\n" + "=" * 52)


# ─────────────────────────────────────────────────────────────
# Standalone SSL latency test
# ─────────────────────────────────────────────────────────────

def run_ping_test(host: str, port: int):
    certfile = 'cert.pem'
    if not os.path.exists(certfile):
        print(f"[QoS] ERROR: {certfile} not found.")
        return

    print(f"\n[QoS] Measuring SSL latency to {host}:{port} (5 samples)...")
    result = measure_latency(host, port, certfile=certfile, samples=5)

    print("\n" + "=" * 44)
    print("  📡  SSL Latency Test Results")
    print("=" * 44)
    if result['avg_ms'] is not None:
        print(f"  Samples  : {result['samples']}")
        print(f"  Min RTT  : {result['min_ms']} ms")
        print(f"  Avg RTT  : {result['avg_ms']} ms")
        print(f"  Max RTT  : {result['max_ms']} ms")
        print(f"  All RTTs : {result['all_ms']}")
        print(f"  Note     : Includes TLS handshake overhead")
    else:
        print("  Could not reach server.")
    print("=" * 44)


if __name__ == '__main__':
    import sys
    args = sys.argv[1:]
    if '--ping' in args:
        idx  = args.index('--ping')
        host = args[idx + 1] if idx + 1 < len(args) else '127.0.0.1'
        port = int(args[idx + 2]) if idx + 2 < len(args) else 5000
        run_ping_test(host, port)
    else:
        print("Usage: python qos.py --ping <host> [port]")
        print("Example: python qos.py --ping 127.0.0.1 5000")
