"""
Script de DIAGNÓSTICO v3 — roda em headless=True (igual ao robô real).

Diferença crucial em relação às versões anteriores: a v1 e v2 usavam
headless=False (navegador visível), e nelas o modal "Verificação de
acesso" não tinha sido capturado da forma esperada. O log mais recente
do robô (que roda headless=True) mostra "modal não apareceu" — então
precisamos comparar exatamente o que acontece em modo headless, que pode
se comportar diferente do navegador visível.

Como usar:
    cd SsaMonitorProcessos
    python diagnostico_pinhais_v3.py

Gera em ./evidencias/diagnostico_v3/:
    - 01_apos_cookies.png / .html       -> logo após aceitar cookies
    - 02_apos_espera_3s.png / .html     -> 3s depois (momento em que o
                                            robô real tenta achar o modal)
    - 03_apos_espera_total.png / .html  -> mais alguns segundos depois
    - frames_mapa.txt                   -> lista de frames em cada etapa
"""

import asyncio
import os
from playwright.async_api import async_playwright


PASTA_SAIDA = "evidencias/diagnostico_v3"


async def capturar_estado(page, etapa: str, linhas_mapa: list):
    """Salva screenshot + HTML da página principal + lista de frames."""
    caminho_png = os.path.join(PASTA_SAIDA, f"{etapa}.png")
    caminho_html = os.path.join(PASTA_SAIDA, f"{etapa}.html")

    await page.screenshot(path=caminho_png, full_page=True)

    html = await page.content()
    with open(caminho_html, "w", encoding="utf-8") as fh:
        fh.write(html)

    linhas_mapa.append(f"\n=== {etapa} ===")
    linhas_mapa.append(f"Total de frames: {len(page.frames)}")
    for i, f in enumerate(page.frames):
        linhas_mapa.append(f"  [{i}] {f.url}")

    print(f"📸 Capturado: {etapa} ({len(page.frames)} frames)")


async def main():
    os.makedirs(PASTA_SAIDA, exist_ok=True)

    url = "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"

    linhas_mapa = []

    async with async_playwright() as p:

        # ALTERAÇÃO: headless=True de propósito, igual ao robô real.
        # É isso que precisamos comparar com o comportamento manual.
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"🌐 Acessando (headless=True): {url}")
        await page.goto(url)

        # =====================================================
        # COOKIES (mesma lógica do robô real)
        # =====================================================
        try:
            await page.click("button:has-text('Aceitar')", timeout=5000)
            print("✅ Cookies aceitos")
        except Exception as e:
            print(f"ℹ️ Banner de cookies não apareceu: {e}")

        await capturar_estado(page, "01_apos_cookies", linhas_mapa)

        # =====================================================
        # ESPERA DE 3s (igual ao robô real antes de checar o modal)
        # =====================================================
        await page.wait_for_timeout(3000)
        await capturar_estado(page, "02_apos_espera_3s", linhas_mapa)

        # Verifica se o texto do modal aparece em algum lugar
        texto_pagina = await page.content()
        if "Verificação de acesso" in texto_pagina or "verificação de acesso" in texto_pagina.lower():
            print("🎯 Texto 'Verificação de acesso' ENCONTRADO no HTML da página principal!")
        else:
            print("❌ Texto 'Verificação de acesso' NÃO encontrado no HTML da página principal.")
            print("   Vamos checar dentro de cada frame também...")

            for i, f in enumerate(page.frames):
                try:
                    html_frame = await f.content()
                    if "verificação de acesso" in html_frame.lower():
                        print(f"   🎯 Encontrado dentro do frame [{i}]: {f.url}")
                except Exception as e:
                    print(f"   ⚠️ Não foi possível ler frame [{i}]: {e}")

        # =====================================================
        # ESPERA ADICIONAL (mais 5s, total 8s) — só para ver se
        # demora mais para aparecer em headless
        # =====================================================
        await page.wait_for_timeout(5000)
        await capturar_estado(page, "03_apos_espera_total", linhas_mapa)

        # =====================================================
        # CHECAR SE HÁ ALGUM ERRO DE CONSOLE / REQUEST FALHANDO
        # (captado durante a navegação, não retroativo — mas
        # vamos ao menos registrar o título e a URL atual)
        # =====================================================
        linhas_mapa.append(f"\nTítulo da página: {await page.title()}")
        linhas_mapa.append(f"URL atual: {page.url}")

        with open(os.path.join(PASTA_SAIDA, "frames_mapa.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(linhas_mapa))

        print(f"\n✅ Diagnóstico concluído. Verifique a pasta: {PASTA_SAIDA}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())