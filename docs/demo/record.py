"""Scripted demo of the DORM playground, recorded with Playwright."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
URL  = "http://127.0.0.1:8001/__dorm__/"
W, H = 1280, 760

CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.id = '__cursor';
  Object.assign(c.style, {
    position: 'fixed', left: '0px', top: '0px', width: '18px', height: '18px',
    marginLeft: '-9px', marginTop: '-9px', borderRadius: '50%', zIndex: 2147483647,
    background: 'rgba(0,0,0,0.35)', border: '2px solid #fff',
    boxShadow: '0 0 0 1px rgba(0,0,0,0.5)', pointerEvents: 'none',
    transition: 'transform .12s ease',
  });
  document.body.appendChild(c);
  document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  document.addEventListener('mousedown', () => { c.style.transform = 'scale(.7)'; }, true);
  document.addEventListener('mouseup',   () => { c.style.transform = 'scale(1)'; }, true);
});
"""


def main(out_dir: Path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(out_dir),
            record_video_size={"width": W, "height": H},
            accept_downloads=True,
        )
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept("Prolific authors"))

        pause = page.wait_for_timeout

        def move(target, dx=0, dy=0, steps=28):
            box = (page.locator(target) if isinstance(target, str) else target).bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2 + dx, box["y"] + box["height"] / 2 + dy, steps=steps)

        def click(target, **kw):
            move(target, **kw)
            pause(180)
            page.mouse.down(); pause(70); page.mouse.up()

        def cell(n):
            return page.locator(".dorm-cell").nth(n)

        def type_in(n, text, delay=42):
            click(cell(n).locator(".CodeMirror"), dx=-200)
            pause(250)
            page.keyboard.type(text, delay=delay)

        def run(expect):
            pause(350)
            page.keyboard.press("Control+Enter")
            page.wait_for_selector(expect)
            pause(900)

        page.goto(URL)
        page.mouse.move(640, 300)
        pause(1200)

        # 1–3: notebook flow — variables carry across cells
        type_in(0, 'authors = Author.objects.annotate(n_books=Count("books"))')
        run(".dorm-cell:nth-of-type(2)")
        type_in(1, 'authors.order_by("-n_books").values("name", "n_books")')
        run("#dorm-result .dorm-table")
        pause(1200)

        type_in(2, 'Book.objects.select_related("author").order_by("-published_year")')
        run("#dorm-result .dorm-table[data-truncated=true]")
        move("#dorm-result", dy=40)
        page.mouse.wheel(0, 500); pause(700); page.mouse.wheel(0, -500)
        pause(800)

        # verbose names toggle
        click("#dorm-verbose-cb"); pause(1100)
        click("#dorm-verbose-cb"); pause(800)

        # truncated export → choice → full result (.zip)
        click(".dorm-export-btn >> nth=0")
        page.wait_for_selector("#dorm-export-modal:not([hidden])")
        pause(1200)
        move("[data-choice=visible]"); pause(900)
        with page.expect_download():
            click("[data-choice=full]")
        pause(1800)

        # hover actions → save cell 2
        move(cell(1), dx=120); pause(900)
        click(cell(1).locator("[data-action=save]"))
        pause(1700)

        # history modal: recents → saved → insert into the focused cell
        click(".dorm-header-btn")
        page.wait_for_selector(".dorm-hist-item")
        pause(1300)
        move(".dorm-hist-item >> nth=1"); pause(700)
        click(".dorm-tab[data-tab=saved]"); pause(1000)
        item = page.locator(".dorm-tab-panel[data-tab=saved] .dorm-hist-item").first
        move(item); pause(500)
        click(item.locator("[data-hist-action=insert]"))
        pause(900)
        run("#dorm-result .dorm-table")
        pause(600)

        # Alt+Up / Alt+Down through recents in the new draft cell
        for key in ["Alt+ArrowUp", "Alt+ArrowUp", "Alt+ArrowDown", "Alt+ArrowDown"]:
            page.keyboard.press(key); pause(1000)

        # layout toggle
        click(".dorm-layout-opt[data-dir=col]"); pause(1500)
        click(".dorm-layout-opt[data-dir=row]"); pause(1500)

        video = page.video
        ctx.close()
        browser.close()
        print(video.path())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
