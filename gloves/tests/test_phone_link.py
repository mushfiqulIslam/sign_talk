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
