"""The phone connects here over Wi-Fi (TCP, one JSON message per line).

Laptop -> phone: {"type": "hello"}, {"type": "sign", ...}, {"type": "sentence", ...}, {"type": "status", ...}
Phone -> laptop: {"type": "replay"} (play the recorded demo signs)
Anyone on the same Wi-Fi can connect: run it on a trusted network or the phone's hotspot.
"""
import json
import socket
import threading


class PhoneLink:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765, on_command=None):
        self.host, self.port, self.on_command = host, port, on_command
        self.phones: list[socket.socket] = []
        self._lock = threading.Lock()
        self._server: socket.socket | None = None
        self._running = False

    def start(self) -> None:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen()
        self.port = self._server.getsockname()[1]
        self._running = True
        threading.Thread(target=self._accept, daemon=True).start()

    def stop(self) -> None:
        self._running = False
        with self._lock:
            for p in self.phones:
                p.close()
            self.phones.clear()
        if self._server:
            self._server.close()

    def send(self, message: dict) -> None:
        line = (json.dumps(message, ensure_ascii=False) + "\n").encode()
        with self._lock:
            for p in list(self.phones):
                try:
                    p.sendall(line)
                except OSError:
                    self.phones.remove(p)
                    p.close()

    def _accept(self) -> None:
        while self._running:
            try:
                conn, addr = self._server.accept()
            except OSError:
                return
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            try:
                conn.sendall(b'{"type": "hello"}\n')
            except OSError:
                conn.close()
                continue
            with self._lock:
                self.phones.append(conn)
            print(f"phone connected from {addr[0]}")
            threading.Thread(target=self._read, args=(conn,), daemon=True).start()

    def _read(self, conn: socket.socket) -> None:
        try:
            for line in conn.makefile("r", encoding="utf-8"):
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict) and self.on_command:
                    self.on_command(message)
        except OSError:
            pass
        with self._lock:
            if conn in self.phones:
                self.phones.remove(conn)
        print("phone disconnected")


def laptop_addresses() -> list[str]:
    """The laptop's Wi-Fi address(es) to type into the phone."""
    found = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet is sent; picks the outgoing interface
        found.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(found)
