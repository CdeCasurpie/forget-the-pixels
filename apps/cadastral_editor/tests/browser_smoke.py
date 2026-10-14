"""Optional real-browser smoke test; run only against a fresh --demo workspace.

Requires playwright and its Chromium installation. Usage: python .../browser_smoke.py
"""
import argparse
from playwright.sync_api import sync_playwright
from pyproj import Transformer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8766')
    args = parser.parse_args()
    with sync_playwright() as runner:
        browser = runner.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(args.url)
        page.wait_for_function("document.getElementById('status').textContent.startsWith('Listo')")
        assert page.request.get(args.url+'/api/config').json()['demo'], 'Demo server required'
        page.fill('#search', 'demo-a')
        page.click('#find')
        page.wait_for_function("document.getElementById('details').textContent.includes('demo-a ·')")
        page.fill('#block', 'e2e-block')
        page.click('#assign')
        page.wait_for_selector('#preview', state='visible')
        page.click('#commit')
        page.wait_for_function("document.getElementById('status').textContent.startsWith('Guardado')")
        assert page.locator('#fronts input').count() == 4
        page.fill('#dy', '2')
        page.click('#move')
        page.wait_for_selector('#preview', state='visible')
        page.click('#cancel')
        assert page.request.get(args.url+'/api/lots/demo-a').json()['geometry']['coordinates'][0][0][1] == 8656480
        page.click('#cut')
        to_map = Transformer.from_crs(32718, 4326, always_xy=True)
        for xy in [(279956, 8656475), (279956, 8656505)]:
            lonlat = to_map.transform(*xy)
            point = page.evaluate('p => screen(p)', lonlat)
            bounds = page.locator('#canvas').bounding_box()
            page.mouse.click(bounds['x']+point[0], bounds['y']+point[1])
        page.click('#previewCut')
        page.wait_for_selector('#preview', state='visible')
        page.click('#commit')
        page.wait_for_function("document.getElementById('count').textContent==='2'")
        page.click('#merge')
        page.wait_for_selector('#preview', state='visible')
        page.click('#commit')
        page.wait_for_function("document.getElementById('count').textContent==='1'")
        page.reload()
        page.wait_for_function("document.getElementById('status').textContent.startsWith('Listo')")
        page.click('#undo')
        page.wait_for_selector('#preview', state='visible')
        page.click('#commit')
        page.wait_for_function("document.getElementById('count').textContent==='2'")
        page.click('#historyButton')
        page.wait_for_selector('#history p')
        assert not errors, errors
        browser.close()
        print('Browser OK: assign, cancel movement, draw cut, merge, reload, undo, history')


if __name__ == '__main__':
    main()
