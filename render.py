"""
render.py — draw a figure export (bundle.py) without the app, as SVG.

    python render.py figure.plotboard.json      # or - to read the bundle from stdin

prints one JSON object: {"svg", "W", "H", "L", "T", "PW", "PH", "xlim", "ylim", "ylog"}
(a list of them for a list of bundles: one process, the imports paid once).

    python render.py --serve 127.0.0.1:8768     # stay up: POST a bundle (or a list) as JSON, get the same back

The server pays the imports once (a cold call is seconds, mostly imports). It renders one request at a
time (matplotlib is not thread-safe) and has no auth: bind it to an address only trusted callers reach.
W x H is the SVG's viewBox (pt); L, T, PW, PH the plot area (the axes box) in the same
units, xlim / ylim the drawn axis ranges. With them a page can draw over the plot, e.g. a
marker at x = L + PW * (v - xlim[0]) / (xlim[1] - xlim[0]).

Keys the bundle's make_figure_kwargs leave out come from the VOYAGE preset, so a caller
that only knows its data, labels and colours still gets our look. The SVG is transparent
(the page's ground shows through), its text is drawn as paths (no font needed) and it is
the same bytes for the same bundle.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import bundle  # noqa: E402
import figspec  # noqa: E402
import plotter  # noqa: E402

VOYAGE = json.loads((Path(__file__).parent / "default_presets" / "VOYAGE.json").read_text())


def render(b: dict) -> dict:
    df, kwargs = bundle.load(b)
    base = {**figspec.figure_size(VOYAGE),
            **figspec.draw_kwargs(VOYAGE, n_treatments=max(df["treatment"].nunique(), 1))}
    fig = plotter.make_figure(df, **{**base, **kwargs})
    ax = fig.axes[0]
    out = io.StringIO()
    with matplotlib.rc_context({"svg.hashsalt": "plotboard", "svg.fonttype": "path"}):
        fig.savefig(out, format="svg", transparent=True, metadata={"Date": None})
    W, H = fig.get_figwidth() * 72, fig.get_figheight() * 72
    box = ax.get_position()
    return {"svg": out.getvalue(), "W": round(W, 2), "H": round(H, 2),
            "L": round(box.x0 * W, 2), "T": round((1 - box.y1) * H, 2),
            "PW": round(box.width * W, 2), "PH": round(box.height * H, 2),
            "xlim": list(ax.get_xlim()), "ylim": list(ax.get_ylim()),
            "ylog": ax.get_yscale() == "log"}


def _answer(b):
    return [render(x) for x in b] if isinstance(b, list) else render(b)


def serve(addr: str) -> None:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if not 0 < n <= 50_000_000:
                    raise ValueError("need a JSON body of at most 50 MB")
                code, out = 200, _answer(json.loads(self.rfile.read(n)))
            except Exception as err:  # noqa: BLE001  (a bad bundle answers 400, the server stays up)
                code, out = 400, {"error": f"{type(err).__name__}: {err}"}
            body = json.dumps(out).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    host, port = addr.rsplit(":", 1)
    HTTPServer((host, int(port)), Handler).serve_forever()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--serve":
        serve(sys.argv[2])
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    json.dump(_answer(json.loads(text)), sys.stdout)
