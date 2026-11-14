import json
import socket
import time

from phone_link import PhoneLink


def connect(port):
    s = socket.create_connection(("127.0.0.1", port), timeout=3)
    f = s.makefile("rw", encoding="utf-8")
    return s, f


def test_phone_gets_hello_and_broadcasts():
    link = PhoneLink(port=0)
    link.start()
    try:
        s, f = connect(link.port)
        assert json.loads(f.readline())["type"] == "hello"
        for _ in range(50):
            if link.phones:
                break
            time.sleep(0.02)
        link.send({"type": "sign", "sign": "me"})
        assert json.loads(f.readline()) == {"type": "sign", "sign": "me"}
        s.close()
    finally:
        link.stop()


def test_phone_command_reaches_the_backend():
    got = []
    link = PhoneLink(port=0, on_command=got.append)
    link.start()
    try:
        s, f = connect(link.port)
        f.readline()
        f.write(json.dumps({"type": "replay"}) + "\n")
        f.flush()
        for _ in range(50):
            if got:
                break
            time.sleep(0.02)
        assert got == [{"type": "replay"}]
        s.close()
    finally:
        link.stop()


def test_garbage_from_a_phone_is_ignored():
    got = []
    link = PhoneLink(port=0, on_command=got.append)
    link.start()
    try:
        s, f = connect(link.port)
        f.readline()
        f.write("not json\n")
        f.flush()
        time.sleep(0.1)
        assert got == []
        s.close()
    finally:
        link.stop()


def test_beacon_announces_name_and_port():
    import socket as so

    from phone_link import Beacon

    rx = so.socket(so.AF_INET, so.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0))
    rx.settimeout(3)
    beacon = Beacon(name="Team table", port=8765, target=("127.0.0.1", rx.getsockname()[1]), every_s=0.05)
    beacon.start()
    try:
        data, _ = rx.recvfrom(2048)
        assert json.loads(data) == {"type": "signtalk-gloves", "name": "Team table", "port": 8765}
    finally:
        beacon.stop()
        rx.close()


def test_addresses_skip_loopback_and_prefer_real_lan():
    from phone_link import rank_addresses

    got = rank_addresses(["127.0.0.1", "172.25.96.1", "169.254.3.4", "10.0.34.57", "192.168.1.20"], route_guess="172.25.96.1")
    assert got[:2] == ["10.0.34.57", "192.168.1.20"]  # real Wi-Fi/LAN first
    assert "127.0.0.1" not in got and "169.254.3.4" not in got
    assert got[-1] == "172.25.96.1"  # 172.16-31: usually WSL / Hyper-V / Docker, kept last


def test_route_guess_wins_among_equals():
    from phone_link import rank_addresses

    assert rank_addresses(["192.168.1.20", "10.0.34.57"], route_guess="10.0.34.57")[0] == "10.0.34.57"
