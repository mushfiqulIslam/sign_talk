"""Crawl the public Signbank dictionary (VKK corpus dataset) -> $FINSL_DATA/signbank.json. Polite: 1 request/s, cached."""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from finsl.signbank import known, make_bank, parse_dictionary_page

DEFAULT_DATA = Path(__file__).resolve().parent.parent.parent / "finsl-data"
URL = "https://signbank.csc.fi/dictionary/?dataset=1&page={page}"


def fetch(page: int, cache: Path) -> str | None:
    """None means the page doesn't exist (past the last page)."""
    f = cache / f"page{page}.html"
    if f.exists():
        return f.read_text(encoding="utf-8")
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL.format(page=page), headers={"User-Agent": "Mozilla/5.0 (finsl-hackathon)"})
            html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8")
            f.write_text(html, encoding="utf-8")
            time.sleep(1)
            return html
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            print(f"  page {page} attempt {attempt + 1}: {e}")
            time.sleep(3)
        except Exception as e:  # noqa: BLE001 - retry any network failure
            print(f"  page {page} attempt {attempt + 1}: {e}")
            time.sleep(3)
    raise RuntimeError(f"page {page} failed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("FINSL_DATA", DEFAULT_DATA)))
    data = ap.parse_args().data
    cache = data / "cache" / "signbank"
    cache.mkdir(parents=True, exist_ok=True)
    entries, seen = [], set()
    page = 1
    while True:
        html = fetch(page, cache)
        if html is None:
            break
        parsed = parse_dictionary_page(html)
        new = [e for e in parsed if e.gloss_id not in seen]
        if not new:
            break
        seen.update(e.gloss_id for e in new)
        entries += new
        page += 1
    bank = make_bank(entries)
    (data / "signbank.json").write_text(json.dumps(bank, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(entries)} Signbank entries from {page - 1} pages -> {len(bank)} names")
    signs = [s for split in ("train", "val", "test")
             for line in (data / "dataset" / f"{split}.jsonl").open(encoding="utf-8")
             for s in json.loads(line)["signs"]]
    print(f"corpus signs known to Signbank: {sum(known(s, bank) for s in signs) / len(signs):.0%} of {len(signs)}")


if __name__ == "__main__":
    main()
