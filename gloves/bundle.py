"""signtalk-gloves bundle: one zip to share privately (backend + trained model + start scripts).
It contains glove recordings (inside the model, for the replay demo) and no API keys."""
import shutil
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULES = ["serve", "phone_link", "decoder", "sentence", "csv_signs", "signs", "studio", "qr_page", "bundle"]
FILES = ["pyproject.toml", "start.bat", "start.sh", "QUICKSTART.txt"]


def make(model_path: Path, out: Path) -> Path:
    import joblib

    if not Path(model_path).is_file():
        raise SystemExit(f"No trained model at {model_path}: run `signtalk-gloves train --data <csv folder>` first")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "SignTalk-Gloves"
        root.mkdir()
        for m in MODULES:
            shutil.copy2(HERE / f"{m}.py", root / f"{m}.py")
        for f in FILES:
            shutil.copy2(HERE / f, root / f)
        joblib.dump(joblib.load(model_path), root / "gloves-model.joblib", compress=3)
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(root.rglob("*")):
                info = zipfile.ZipInfo.from_file(f, f"SignTalk-Gloves/{f.relative_to(root).as_posix()}")
                if f.name == "start.sh":
                    info.external_attr = 0o100755 << 16  # stays runnable after unzipping
                with open(f, "rb") as fh:
                    z.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB). Share it privately: it holds glove recordings.")
    print("The recipient unzips it and follows QUICKSTART.txt (Windows: double-click start.bat).")
    return out
