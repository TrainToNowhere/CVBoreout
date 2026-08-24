"""Entry point: desktop window, web mode and command line export."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from . import model, pdf, server

DEFAULT_FILE = Path("data/resume.json")
WINDOW_WIDTH, WINDOW_HEIGHT = 1360, 860


def _run_window(state: server.State, address: str) -> int:
    try:
        import webview  # noqa: PLC0415
    except ImportError:
        print("pywebview is not installed – falling back to web mode.", file=sys.stderr)
        return _run_web(address)

    window = webview.create_window(
        "CVBoreout",
        address,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(1080, 680),
        background_color="#0e1219",
        text_select=True,
    )

    def dialog(suggestion: Path):
        """Save dialog; falls back to the suggested path on any problem."""
        try:
            result = window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=str(suggestion.parent),
                save_filename=suggestion.name,
                file_types=("PDF file (*.pdf)",),
            )
        except Exception:  # noqa: BLE001 – dialogs are platform dependent
            return str(suggestion)
        if result is None:
            return None
        if isinstance(result, str):
            return result
        return result[0] if result else None

    state.file_dialog = dialog
    # private_mode=False keeps localStorage available inside the WebView and
    # lets preferences survive a restart.
    storage = Path.home() / ".local" / "share" / "cvboreout"
    storage.mkdir(parents=True, exist_ok=True)
    try:
        webview.start(private_mode=False, storage_path=str(storage))
    except TypeError:  # older pywebview versions lack these arguments
        webview.start()
    return 0


def _run_web(address: str) -> int:
    print(f"CVBoreout is running: {address}\nPress Ctrl+C to stop.")
    try:
        import time

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


def _adopt_legacy_file(target: Path) -> None:
    """Carry a resume written by the first release over to the new file name."""
    legacy = target.parent / "lebenslauf.json"
    if target.exists() or not legacy.exists():
        return
    try:
        data = model.normalize(json.loads(legacy.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return
    model.save(target, data)
    print(f"Adopted {legacy} -> {target}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="cvboreout", description="Resume builder for STEM professionals")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help="JSON file holding the resume")
    parser.add_argument("--web", action="store_true", help="serve only, open in the default browser")
    parser.add_argument("--port", type=int, default=0, help="fixed port (default: pick a free one)")
    parser.add_argument("--export", type=Path, metavar="TARGET.pdf", help="write a PDF and exit")
    parser.add_argument("--html", type=Path, metavar="TARGET.html", help="write the HTML and exit")
    parser.add_argument("--doc", choices=("resume", "letter", "both"), default="resume",
                        help="which document to export (default: resume)")
    parser.add_argument("--sample", action="store_true", help="start from the sample resume")
    args = parser.parse_args(argv)

    _adopt_legacy_file(args.file)

    if args.sample and not args.file.exists():
        model.save(args.file, model.normalize(copy.deepcopy(model.SAMPLE)))

    if args.export or args.html:
        data = model.load(args.file)
        if args.html:
            from . import render  # noqa: PLC0415

            args.html.parent.mkdir(parents=True, exist_ok=True)
            markup = (render.render_letter(data) if args.doc == "letter"
                      else render.render_html(data))
            args.html.write_text(markup, encoding="utf-8")
            print(f"HTML written: {args.html}")
        if args.export:
            print(f"PDF written: {pdf.write_pdf(data, args.export, args.doc)}")
        return 0

    state = server.State(args.file)
    _, address = server.serve(state, args.port)

    if args.web:
        import webbrowser  # noqa: PLC0415

        webbrowser.open(address)
        return _run_web(address)
    return _run_window(state, address)


if __name__ == "__main__":
    raise SystemExit(main())
