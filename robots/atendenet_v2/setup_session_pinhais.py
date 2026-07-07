"""
Setup de sessao: abre um browser visivel para voce fazer login manualmente
no pinhais.atende.net e salva a sessao em session_state.json.

Execute este script sempre que a sessao expirar:
    python robots/atendenet_v2/setup_session_pinhais.py
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

LOGIN_URL = "https://pinhais.atende.net/cidadao/acesso/tipo/1/redirect/YXV0b2F0ZW5kaW1lbnRv"
CONSULTA_URL = "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"
SESSION_FILE = Path(__file__).parent / "session_state.json"

SELECTOR_INPUT = (
    "input:not([type='hidden']):not([type='submit']):not([type='button'])"
    ":not([type='checkbox']):not([type='radio'])"
    ":not([id*='goog']):not([name='g-recaptcha-response'])"
)


async def main():
    print("=" * 60)
    print("SETUP DE SESSAO — pinhais.atende.net")
    print("=" * 60)
    print()
    print("1. Um browser vai abrir na pagina de login.")
    print("2. Faca o login com seu CNPJ e senha.")
    print("3. Apos o login, aguarde — o script salva a sessao.")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        print("Abrindo browser...")
        await page.goto(LOGIN_URL)

        try:
            await page.click("button:has-text('Aceitar')", timeout=5000)
            print("Cookies aceitos.")
        except Exception:
            pass

        print()
        print("Aguardando login (ate 3 minutos)...")

        try:
            await page.wait_for_url("**/autoatendimento**", timeout=180_000)
            print("Login detectado!")
        except Exception:
            if "autoatendimento" not in page.url:
                print("Timeout aguardando login. Encerrando.")
                await browser.close()
                return

        await page.wait_for_timeout(2000)
        state = await context.storage_state()
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        print(f"Sessao salva em: {SESSION_FILE}")

        # Testa se a consulta carrega com a sessao salva
        print("\nTestando consulta de processo com a sessao...")
        await page.goto(CONSULTA_URL)
        await page.wait_for_timeout(5000)

        try:
            await page.click(
                "button:has-text('Continuar o acesso com meu Navegador')",
                timeout=5000,
                force=True,
            )
            print("Aviso de navegador: aceito")
            await page.wait_for_timeout(3000)
        except Exception:
            pass

        try:
            await page.click("button:has-text('Aceitar')", timeout=3000, force=True)
        except Exception:
            pass

        await page.wait_for_timeout(5000)

        inputs_encontrados = 0
        for f in page.frames:
            if "embed/data" in f.url:
                try:
                    inputs_encontrados = await f.locator(SELECTOR_INPUT).count()
                except Exception:
                    pass
                break

        if inputs_encontrados >= 2:
            print(f"SUCESSO! Formulario carregou ({inputs_encontrados} inputs).")
            print("O robot esta pronto para monitorar Pinhais e Araucaria.")
        else:
            print(f"Aviso: formulario nao carregou (inputs={inputs_encontrados}).")
            print("A sessao foi salva, mas verifique se o login esta ativo.")

        await browser.close()

    print("\nSetup concluido.")


asyncio.run(main())
