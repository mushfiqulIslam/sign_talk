from serve import GloveMonitor


class FakeLink:
    def __init__(self):
        self.sent = []

    def send(self, m):
        self.sent.append(m)


def test_receiving_reports_rate_and_last_guess():
    link = FakeLink()
    m = GloveMonitor(link, source="udp port 9100", start=0.0)
    for i in range(120):
        m.frame(i / 60)
    m.guess("study", 0.82)
    line = m.report(2.0)
    assert "receiving 60 frames/s" in line and "STUDY (0.82)" in line
    assert link.sent[-1] == {"type": "gloves", "receiving": True, "text": "Gloves: receiving data (60 frames/s)"}


def test_silence_is_reported_with_where_to_send():
    link = FakeLink()
    m = GloveMonitor(link, source="Rokoko Studio, UDP port 14043", start=0.0)
    line = m.report(5.0)
    assert "NO DATA for 5 s" in line and "UDP port 14043" in line
    assert link.sent[-1]["receiving"] is False


def test_data_then_silence():
    link = FakeLink()
    m = GloveMonitor(link, source="udp port 9100", start=0.0)
    m.frame(1.0)
    m.report(2.0)
    assert link.sent[-1]["receiving"] is True
    assert "NO DATA for 4 s" in m.report(5.0)
