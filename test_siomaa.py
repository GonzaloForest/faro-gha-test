"""Prueba minima: login SIOMAA + descarga de patentamientos de todo el mercado (sin DB)."""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

OUT = Path("out")
OUT.mkdir(exist_ok=True)
URL = "https://www.siomaa.com/V2/Vehiculo/Index/"
USER = os.environ["SIOMAA_USER"]
PWD = os.environ["SIOMAA_PASSWORD"]
print(f"Largo usuario={len(USER)} largo password={len(PWD)} (0 = secret vacio o no cargado)")


def shot(page, name):
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    except Exception:
        pass


def fill_first(page, sels, value):
    for s in sels:
        if page.locator(s).count() > 0:
            page.fill(s, value)
            return True
    return False


def main() -> int:
    hasta = date.today() - timedelta(days=1)
    desde = hasta - timedelta(days=6)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        page.set_default_timeout(20000)

        for intento in range(1, 4):
            try:
                page.goto(URL, wait_until="commit", timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                break
            except Exception as e:
                print(f"intento {intento} fallo: {str(e)[:120]}")
                if intento == 3:
                    return 1
        page.wait_for_timeout(3000)
        print("URL inicial:", page.url)
        shot(page, "1_inicio")

        if "/login" in page.url.lower():
            u = page.locator("input[placeholder*='suario']").first
            pw = page.locator("input[type='password']").first
            u.click()
            u.press_sequentially(USER, delay=30)
            pw.click()
            pw.press_sequentially(PWD, delay=30)
            print("valores escritos: usuario", len(u.input_value()), "password", len(pw.input_value()))
            shot(page, "1b_campos_llenos")
            page.locator("button:has-text('Entrar')").first.click()
            try:
                page.wait_for_url(lambda url: "/login" not in url.lower(), timeout=25000)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            shot(page, "2_post_login")
            if "/login" in page.url.lower():
                txt = page.inner_text("body")
                print("FALLO: sigue en login. Texto de la pagina:")
                print(txt[:800])
                return 1
        print("LOGIN OK:", page.url)

        page.goto(URL, wait_until="domcontentloaded")
        page.get_by_text("Patentamientos", exact=True).first.click()
        page.wait_for_timeout(3000)
        for fid, val in [("Filter_FechaDesde", desde.strftime("%d/%m/%Y")), ("Filter_FechaHasta", hasta.strftime("%d/%m/%Y"))]:
            page.evaluate(
                "([i,v])=>{const e=document.getElementById(i);e.value=v;e.dispatchEvent(new Event('change',{bubbles:true}));}",
                [fid, val],
            )
        shot(page, "3_filtros")
        page.locator("button:has-text('Diario')").first.click()
        page.wait_for_timeout(5000)
        with page.expect_download(timeout=60000) as dl:
            page.locator("a:has-text('Excel')").first.click()
        f = OUT / "patentamientos.xls"
        dl.value.save_as(str(f))
        browser.close()

    df = pd.read_html(str(f))[0]
    print("DESCARGA OK. Shape:", df.shape)
    print(df.iloc[:15, :4].to_string())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("ERROR:", repr(e))
        sys.exit(1)
