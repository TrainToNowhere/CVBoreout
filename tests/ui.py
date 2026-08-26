"""Self-test for the editor front end.

The page is loaded into an offscreen WebKit view - the same engine the desktop
window uses - and driven from the outside, so the checks exercise the real
app.js against the real server instead of a mock of either.

Needs the GTK/WebKit bindings and a display; run it with `make test-ui`.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Must be set before GTK is loaded: the offscreen window has no GL context.
os.environ.setdefault("GDK_BACKEND", "x11")
os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

from cvboreout import model, server                                # noqa: E402

from .harness import check, private_config, summary                # noqa: E402
from .server import _job_board                                     # noqa: E402

SETTLE_MS = 2500        # start-up: editor drawn, first preview requested


class Browser:
    """A WebKit view that can be asked questions from Python."""

    def __init__(self, width=1500, height=1000):
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import GLib, Gtk, WebKit2

        self.GLib, self.WebKit2 = GLib, WebKit2
        self.window = Gtk.OffscreenWindow()
        self.view = WebKit2.WebView()
        self.view.set_size_request(width, height)
        self.window.add(self.view)
        self.window.set_default_size(width, height)
        self.window.show_all()

    def _spin(self, milliseconds):
        loop = self.GLib.MainLoop()
        self.GLib.timeout_add(milliseconds, lambda: (loop.quit(), False)[1])
        loop.run()

    def load(self, url, settle=SETTLE_MS):
        loop = self.GLib.MainLoop()

        def done(_view, event):
            if event == self.WebKit2.LoadEvent.FINISHED:
                loop.quit()

        handler = self.view.connect("load-changed", done)
        self.GLib.timeout_add(30000, lambda: (loop.quit(), False)[1])
        self.view.load_uri(url)
        loop.run()
        self.view.disconnect(handler)
        self._spin(settle)

    def js(self, script: str, settle=0) -> str:
        """Evaluate an expression in the page and bring back its value."""
        loop = self.GLib.MainLoop()
        result = {}

        def done(view, task):
            try:
                result["value"] = view.evaluate_javascript_finish(task).to_string()
            except Exception as error:                              # noqa: BLE001
                result["error"] = str(error)
            loop.quit()

        self.view.evaluate_javascript(script, -1, None, None, None, done)
        self.GLib.timeout_add(30000, lambda: (loop.quit(), False)[1])
        loop.run()
        if "error" in result:
            raise RuntimeError(f"{result['error']}\nscript: {script.strip()[:200]}")
        if settle:
            self._spin(settle)
        return result.get("value", "")

    def value(self, expression: str, settle=0):
        """The same, but for expressions that return something JSON-shaped."""
        return json.loads(self.js(f"JSON.stringify({expression})", settle))


HELPERS = r"""
window.__t = {
  // typing into a field, events and all
  type(selector, text) {
    const node = document.querySelector(selector);
    node.value = text;
    node.dispatchEvent(new Event("input"));
    return node.value;
  },
  // sizes of every single-line field in the editor
  fieldSizes() {
    const seen = {};
    for (const n of document.querySelectorAll(
        "#editor input:not([type]), #editor input[type=number], #editor select")) {
      const box = n.getBoundingClientRect();
      const key = Math.round(box.width) + "x" + Math.round(box.height);
      seen[key] = (seen[key] || 0) + 1;
    }
    return seen;
  },
  badge(id) {
    return document.querySelector(`#editor details.group[data-id=${id}] summary .count`).textContent;
  },
  group(id) {
    const node = document.querySelector(`#editor details.group[data-id=${id}]`);
    node.open = true;
    return node;
  },
  open(id) {                    // same, for when the result travels to Python
    this.group(id);
    return id;
  },
  // a stand-in for the AI endpoint: streams for as long as it is allowed to
  fakeStream() {
    window.__streamed = false;
    const real = window.fetch;
    window.fetch = (url, options = {}) => {
      if (!String(url).includes("/api/ai")) return real(url, options);
      window.__streamed = true;
      const encoder = new TextEncoder();
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(
            'event: start\ndata: {"kind":"text","applicable":true}\n\n'));
          const timer = setInterval(() => controller.enqueue(
            encoder.encode('event: token\ndata: {"t":"wort "}\n\n')), 60);
          options.signal.addEventListener("abort", () => {
            clearInterval(timer);
            controller.error(new DOMException("aborted", "AbortError"));
          });
        },
      });
      return Promise.resolve(new Response(body, { status: 200 }));
    };
    const models = document.querySelector("#ai-model");
    if (!models.value) {
      models.append(new Option("test-model", "test-model"));
      models.value = "test-model";
    }
  },
};
"ready"
"""


def main() -> int:
    failures = 0

    with private_config(), tempfile.TemporaryDirectory() as folder:
        state = server.State(Path(folder) / "resume.json")
        state.data = model.normalize(model.SAMPLE)
        running, address = server.serve(state, port=0)
        try:
            page = Browser()
            page.load(address)
            page.js(HELPERS)

            print("Fixed field sizes")
            sizes = page.value("__t.fieldSizes()")
            fixed = sizes.get("200x32", 0)
            odd = {key: count for key, count in sizes.items()
                   if key not in ("200x32", "88x32", "106x32", "104x32")}
            failures += not check(fixed > 80, f"{fixed} single-line fields at exactly 200x32")
            failures += not check(not odd, f"no field off the grid ({odd or 'none'})")
            failures += not check(
                page.value('(() => { const r = document.querySelector("#editor .row.date")'
                           '.getBoundingClientRect(); return Math.round(r.width); })()') == 200,
                "month and year together fill one field")
            for width in (330, 420, 505, 700):
                overflow = page.value(
                    f'(() => {{ document.documentElement.style.setProperty("--editor-width", "{width}px");'
                    ' const e = document.querySelector("#editor");'
                    " return e.scrollWidth - e.clientWidth; })()")
                failures += not check(overflow == 0, f"no sideways overflow at {width}px")
            page.js('document.documentElement.style.removeProperty("--editor-width")')

            print("\nPersonal details")
            heads = page.value('[...__t.group("person").querySelectorAll(".subhead")]'
                               ".map(n => n.textContent)")
            failures += not check(heads == ["NAME", "ADRESSE", "WEITERE DATEN"]
                                  or [h.lower() for h in heads] == ["name", "adresse", "weitere daten"],
                                  f"fields grouped under {heads}")
            page.js('__t.type("#editor input[placeholder=optional]", "deutsch")')
            failures += not check(page.value("DATA.person.nationality") == "deutsch",
                                  "typing reaches the document")
            street = page.value(
                '(() => { const f = [...__t.group("person").querySelectorAll(".field")]'
                '.find(f => f.querySelector("span.label").textContent.startsWith("Straße"));'
                ' f.querySelector("input").value = "Bahnhofstr. 4";'
                ' f.querySelector("input").dispatchEvent(new Event("input"));'
                " return DATA.person.street; })()")
            failures += not check(street == "Bahnhofstr. 4", "street field bound to the document")

            print("\nLive counters")
            before = page.value("__t.badge('interests')")
            page.js('__t.group("interests").querySelector(".taglist .add").click()')
            after = page.value("__t.badge('interests')")
            failures += not check(int(after) == int(before) + 1,
                                  f"adding an interest updates the badge ({before} to {after})")
            page.js('__t.group("interests").querySelector(".taglist .row .btn.tiny").click()')
            failures += not check(page.value("__t.badge('interests')") == before,
                                  "deleting one updates it again")
            page.js('__t.group("experience").querySelector(".card .card-head button:last-child").click()')
            failures += not check(page.value("__t.badge('experience')")
                                  == str(page.value("DATA.experience.length")),
                                  "deleting an entry updates its badge")

            print("\nReordering with the arrow buttons")
            page.js('__t.open("experience")')
            tags_before = page.value("DATA.experience[0].tech")
            page.js('__t.group("experience").querySelectorAll(".card .taglist .row")[1]'
                    '.querySelector(".arrows button").click()')
            tags_after = page.value("DATA.experience[0].tech")
            failures += not check(tags_after[:2] == [tags_before[1], tags_before[0]],
                                  "a technology moves up")
            failures += not check(
                page.value('[...document.querySelectorAll("#editor details.group[data-id=experience]'
                           ' .card .taglist .row input")].map(i => i.value)')[:2] == tags_after[:2],
                "the rows follow the data")

            skills_before = page.value("DATA.skills[0].items.map(i => i.name)")
            page.js('__t.group("skills").querySelector(".card .row")'
                    '.querySelectorAll(".arrows button")[1].click()')
            skills_after = page.value("DATA.skills[0].items.map(i => i.name)")
            failures += not check(skills_after[:2] == [skills_before[1], skills_before[0]],
                                  "a skill moves down")
            page.js('__t.group("skills").querySelector(".card .row")'
                    '.querySelectorAll(".arrows button")[0].click()')
            failures += not check(page.value("DATA.skills[0].items.map(i => i.name)") == skills_after,
                                  "moving the first entry up does nothing")
            rows = page.value('__t.group("skills").querySelectorAll(".card .row").length')
            page.js(f'__t.group("skills").querySelectorAll(".card .row")[{rows - 1}]'
                    '.querySelectorAll(".arrows button")[1].click()')
            failures += not check(page.value("DATA.skills[0].items.map(i => i.name)") == skills_after,
                                  "moving the last entry down does nothing")

            print("\nAI modes")
            page.js('document.querySelector("#ai").hidden = false')
            options = page.value('[...document.querySelector("#ai-action").options].map(o => o.value)')
            failures += not check(options == ["summary", "bullets", "skills", "review", "match",
                                              "letter", "proofread", "free"],
                                  "every mode sits in the dropdown")
            page.js("__t.fakeStream()")
            for mode, station, free in [("bullets", False, True), ("free", True, False),
                                        ("review", True, True)]:
                page.js(f'(() => {{ const s = document.querySelector("#ai-action");'
                        f' s.value = "{mode}"; s.dispatchEvent(new Event("change")); }})()')
                hidden = page.value('[document.querySelector("#station-field").hidden,'
                                    ' document.querySelector("#free-field").hidden]')
                failures += not check(hidden == [station, free], f"{mode}: extra fields as expected")
            failures += not check(page.value("window.__streamed") is False,
                                  "switching modes starts nothing")
            page.js('chooseAction("letter")')
            failures += not check(page.value('document.querySelector("#ai-action").value') == "letter",
                                  "the editor buttons move the dropdown along")

            print("\nPlay and stop")
            failures += not check(page.value('!!document.querySelector("#ai-stop")') is False,
                                  "no separate stop button left")
            page.js('document.querySelector("#ai-run").click()', settle=400)
            state_running = page.value(
                '(() => { const b = document.querySelector("#ai-run"); return [b.textContent,'
                ' b.classList.contains("running"), aiAbort !== null,'
                ' document.querySelector("#ai-text").value.length > 0]; })()')
            failures += not check(state_running == ["■", True, True, True],
                                  "play starts the run and turns into stop")
            page.js('document.querySelector("#ai-run").click()', settle=400)
            state_stopped = page.value(
                '(() => { const b = document.querySelector("#ai-run"); return [b.textContent,'
                ' b.classList.contains("running"), aiAbort === null,'
                ' document.querySelector("#ai-text").value.length > 0,'
                ' document.querySelector("#toast").hidden]; })()')
            failures += not check(state_stopped == ["▶", False, True, True, True],
                                  "the same button stops, keeps the text and shows no error")

            print("\nJob posting by URL")
            with _job_board() as url:
                page.js(f'__t.type("#ai-posting-url", "{url}");'
                        ' document.querySelector("#ai-posting-load").click()', settle=1500)
                text = page.value('document.querySelector("#ai-posting").value')
                failures += not check("Testingenieur (m/w/d)" in text, "the posting lands in the box")
                failures += not check("var t = 1" not in text, "without its scripts")
                failures += not check(
                    page.value('[document.querySelector("#ai-posting-load").disabled,'
                               ' document.querySelector("#ai-posting-load").textContent]')
                    == [False, "laden"], "the button returns to its resting state")
            page.js('__t.type("#ai-posting-url", "http://127.0.0.1:9");'
                    ' document.querySelector("#ai-posting-load").click()', settle=1500)
            failures += not check(page.value('document.querySelector("#toast").hidden') is False,
                                  "an unreachable address is reported")
            failures += not check("Testingenieur" in page.value(
                'document.querySelector("#ai-posting").value'), "and the old text is kept")

            print("\nLanguage switch")
            page.js('(switchLanguage("en"), "switching")', settle=1200)
            failures += not check(page.value('document.querySelector("#ai-action").value') == "letter",
                                  "the chosen mode survives")
            failures += not check(
                page.value('[...document.querySelector("#ai-action").options].map(o => o.text)')[0]
                == "Write profile", "the modes are translated")
            failures += not check(page.value('document.querySelector("#ai-run").title') == "Run",
                                  "the play button is translated")
            labels = page.value('[...__t.group("person").querySelectorAll(".subhead")]'
                                ".map(n => n.textContent.toLowerCase())")
            failures += not check(labels == ["name", "address", "further details"],
                                  f"the field groups are translated ({labels})")
        finally:
            running.shutdown()
            running.server_close()

    return summary(failures)


if __name__ == "__main__":
    sys.exit(main())
