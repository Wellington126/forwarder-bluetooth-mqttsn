#!/usr/bin/env python3
"""Forwarder Bluetooth (RFCOMM) -> Gateway MQTT-SN (UDP)."""
import socket, threading, argparse

def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except OSError:
            return None
        if not chunk:
            return None
        buf += chunk
    return buf

def read_packet(bt):
    """Lê exatamente um pacote MQTT-SN usando o campo de tamanho."""
    first = recv_exact(bt, 1)
    if first is None:
        return None
    if first[0] == 0x01:                       # tamanho estendido (3 bytes)
        ext = recv_exact(bt, 2)
        if ext is None:
            return None
        length = int.from_bytes(ext, "big")
        rest = recv_exact(bt, length - 3)
        return None if rest is None else first + ext + rest
    rest = recv_exact(bt, first[0] - 1)
    return None if rest is None else first + rest

def handle_client(bt, addr, gw):
    print(f"[+] Cliente Bluetooth conectado: {addr}", flush=True)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # 1 socket UDP por cliente
    udp.settimeout(0.5)
    alive = True

    def gateway_para_bluetooth():
        while alive:
            try:
                data, _ = udp.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            print(f"[GW->BT] {data.hex()}", flush=True)
            try:
                bt.send(data)
            except OSError:
                break

    threading.Thread(target=gateway_para_bluetooth, daemon=True).start()
    try:
        while True:
            pkt = read_packet(bt)
            if pkt is None:
                break
            print(f"[BT->GW] {pkt.hex()}", flush=True)
            udp.sendto(pkt, gw)
    finally:
        alive = False
        udp.close()
        bt.close()
        print(f"[-] Cliente desconectado: {addr}", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw-host", default="127.0.0.1")
    ap.add_argument("--gw-port", type=int, default=10000)
    ap.add_argument("--channel", type=int, default=1)
    a = ap.parse_args()

    srv = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    srv.bind((socket.BDADDR_ANY, a.channel))
    srv.listen(1)
    print(f"Forwarder no canal RFCOMM {a.channel} -> gateway {a.gw_host}:{a.gw_port}", flush=True)
    while True:
        bt, addr = srv.accept()
        threading.Thread(target=handle_client, args=(bt, addr, (a.gw_host, a.gw_port)), daemon=True).start()

if __name__ == "__main__":
    main()
