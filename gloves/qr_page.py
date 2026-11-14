"""A browser page with a big QR code: scan it in Sign Talk (Gloves > Scan QR) to connect the phone."""
import html
import tempfile
import urllib.parse
from pathlib import Path


def connect_link(host: str, port: int, name: str) -> str:
    return "signtalk://connect?" + urllib.parse.urlencode({"host": host, "port": port, "name": name})


def _svg(text: str) -> str:
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=14, border=2)
    return img.to_string(encoding="unicode")


def write_page(path, host: str, port: int, name: str) -> Path:
    link = connect_link(host, port, name)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Sign Talk gloves</title>
<style>
 body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
      background:#0E1420;color:#fff;font-family:system-ui,sans-serif;text-align:center}}
 .qr{{background:#fff;padding:18px;border-radius:24px;display:inline-block}}
 .qr svg{{width:min(60vh,80vw);height:auto;display:block}}
 h1{{font-size:34px;margin:0 0 6px}} p{{color:#9AA8BF;font-size:18px;margin:6px}}
 b{{color:#2EC4B6}} code{{color:#FFD166;font-size:20px}}
</style></head><body><div>
<h1>Sign Talk gloves</h1>
<p>On the phone: <b>Sign Talk &rarr; Gloves &rarr; Scan QR</b></p>
<div class="qr">{_svg(link)}</div>
<p>{html.escape(name)} &middot; <code>{html.escape(host)}:{port}</code></p>
<p>Phone and laptop on the same Wi-Fi. Keep the black window open.</p>
</div></body></html>"""
    path = Path(path)
    path.write_text(page, encoding="utf-8")
    return path


def show(host: str, port: int, name: str) -> Path | None:
    """Writes the page to a temp file and opens it in the browser."""
    import webbrowser

    try:
        path = write_page(Path(tempfile.gettempdir()) / "signtalk-gloves-qr.html", host, port, name)
        webbrowser.open(path.as_uri())
        return path
    except Exception as e:  # noqa: BLE001 - the QR is a convenience; the address is printed anyway
        print(f"(couldn't open the QR page: {e})")
        return None
