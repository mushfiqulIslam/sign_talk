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
        self._last_gloves: bytes | None = None  # glove status, repeated to phones that connect later

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
        if message.get("type") == "gloves":
            self._last_gloves = line
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
                if self._last_gloves:
                    conn.sendall(self._last_gloves)
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


def rank_addresses(addresses: list[str], route_guess: str | None = None) -> list[str]:
    """Usable addresses for the phone, best first: real Wi-Fi/LAN (10.x, 192.168.x, others), then
    172.16-31.x (usually a virtual adapter: WSL, Hyper-V, Docker). Never loopback or link-local."""
    def usable(ip: str) -> bool:
        return not (ip.startswith(("127.", "169.254.", "0.")) or ip == "")

    def virtual(ip: str) -> bool:
        parts = ip.split(".")
        return parts[0] == "172" and len(parts) > 1 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31

    unique = list(dict.fromkeys(ip for ip in addresses if usable(ip)))
    return sorted(unique, key=lambda ip: (virtual(ip), ip != route_guess, unique.index(ip)))


def laptop_addresses() -> list[str]:
    """The laptop's address(es) to give the phone, best first."""
    found, route_guess = [], None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet is sent; picks the interface used for the internet
        route_guess = s.getsockname()[0]
        found.append(route_guess)
        s.close()
    except OSError:
        pass
    try:
        found += [info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    except OSError:
        pass
    return rank_addresses(found, route_guess)


DISCOVERY_PORT = 8767  # the phone listens here for laptops announcing themselves


class Beacon:
    """Tells phones on the same Wi-Fi "Sign Talk gloves here", once a second (UDP broadcast).
    The phone takes the laptop's address from the packet, so nobody types an IP.
    Some networks block broadcasts; typing the address in the app still works then."""

    def __init__(self, name: str, port: int, target=("255.255.255.255", DISCOVERY_PORT), every_s: float = 1.0):
        self.message = json.dumps({"type": "signtalk-gloves", "name": name, "port": port}).encode()
        self.target, self.every_s = target, every_s
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        warned = False
        while not self._stop.is_set():
            try:
                s.sendto(self.message, self.target)
            except OSError as e:
                if not warned:
                    print(f"(can't announce on the Wi-Fi: {e}; type the address in the app instead)")
                    warned = True
            self._stop.wait(self.every_s)
        s.close()
