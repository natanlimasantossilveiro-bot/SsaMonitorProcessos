"""
Setup de sessao: abre um browser visivel para voce fazer login manualmente
no pinhais.atende.net e salva a sessao em session_state.json.

Execute este script sempre que a sessao expirar:
    python robots/atendenet_v2/setup_session_pinhais.py

Alem de salvar a sessao, o script:
1. Captura o embed URL e os parametros da API IPM
2. Preenche o formulario com processo 12431/2026 e clica Consultar
3. Captura o XHR exato do Consultar (rot/aca/body/resposta) em api_info.json
"""
import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

LOGIN_URL = "https://pinhais.atende.net/cidadao/acesso/tipo/1/redirect/YXV0b2F0ZW5kaW1lbnRv"
CONSULTA_URL = "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"
SESSION_FILE = Path(__file__).parent / "session_state.json"
API_INFO_FILE = Path(__file__).parent / "api_info.json"

SELECTOR_INPUT = (
    "input:not([type='hidden']):not([type='submit']):not([type='button'])"
    ":not([type='checkbox']):not([type='radio'])"
    ":not([id*='goog']):not([name='g-recaptcha-response'])"
)

# Processo de teste para capturar o XHR do Consultar
NUMERO_TESTE = "12431"
ANO_TESTE = "2026"


async def main():
    print("=" * 60)
    print("SETUP DE SESSAO — pinhais.atende.net")
    print("=" * 60)
    print()
    print("1. Um browser vai abrir na pagina de login.")
    print("2. Faca o login com seu CNPJ e senha.")
    print("3. Apos o login, aguarde — o script salva a sessao.")
    print()

    xhr_log = []
    embed_urls = []

    def on_request(req):
        try:
            if req.resource_type in ("xhr", "fetch"):
                url = req.url
                if any(x in url for x in ["embed/data", "servicos/", "/autoatendimento"]):
                    try:
                        pd = req.post_data or ""
                    except Exception:
                        pd = ""
                    xhr_log.append({"method": req.method, "url": url, "post_data": pd[:600]})
                # Captura embed URL
                if "embed/data/" in url:
                    embed_urls.append(url)
        except Exception:
            pass

    async def on_response(resp):
        try:
            url = resp.url
            if "atende.php" not in url:
                return
            try:
                body = await resp.text()
            except Exception:
                body = "<erro ao ler body>"
            # Associa resposta ao ultimo request com mesma URL
            for xr in reversed(xhr_log):
                if xr["url"] == url and "response_body" not in xr:
                    xr["response_status"] = resp.status
                    xr["response_body"] = body[:4000]
                    break
        except Exception:
            pass

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
        context.on("request", on_request)
        context.on("response", on_response)

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

        # Navega para a pagina de consulta para capturar embed URL e API calls
        print("\nAcessando pagina de consulta para capturar parametros da API...")
        xhr_log.clear()
        embed_urls.clear()
        await page.goto(CONSULTA_URL)
        await page.wait_for_timeout(3000)

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

        # Captura embed URL dos iframes da pagina
        for f in page.frames:
            if "embed/data" in f.url:
                embed_urls.append(f.url)

        # Aguarda o formulario carregar
        inputs_encontrados = 0
        frame_encontrado = None
        for _ in range(15):
            for f in page.frames:
                if "embed/data" in f.url:
                    try:
                        cnt = await f.locator(SELECTOR_INPUT).count()
                        if cnt >= 1:
                            inputs_encontrados = cnt
                            frame_encontrado = f
                            break
                    except Exception:
                        pass
            if frame_encontrado:
                break
            await page.wait_for_timeout(2000)

        if inputs_encontrados >= 2:
            print(f"SUCESSO! Formulario carregou ({inputs_encontrados} inputs).")
        else:
            print(f"Aviso: formulario nao carregou (inputs={inputs_encontrados}).")
            print("A sessao foi salva, mas verifique se o login esta ativo.")

        # ─── FASE 2: Captura o XHR exato do Consultar ────────────────────────
        if frame_encontrado and inputs_encontrados >= 2:
            print(f"\n--- Fase 2: Preenchendo numero={NUMERO_TESTE} ano={ANO_TESTE} e capturando Consultar ---")
            xhr_log.clear()
            try:
                # Lista todos os inputs para debug
                all_inputs = frame_encontrado.locator(SELECTOR_INPUT)
                n_inp = await all_inputs.count()
                print(f"Inputs visiveis no frame ({n_inp}):")
                for i in range(n_inp):
                    inp = all_inputs.nth(i)
                    name = await inp.get_attribute("name") or "?"
                    aria = await inp.get_attribute("aria-description") or ""
                    val = await inp.input_value()
                    print(f"  [{i}] name={name!r} aria={aria!r} value={val!r}")

                # Preenche numero do processo
                SEL_NUM = "input[name='campo01'][aria-description='campo numérico']"
                SEL_ANO = "input[name='campo01'][aria-description='campo ano']"
                campo_num = frame_encontrado.locator(SEL_NUM).first
                campo_ano = frame_encontrado.locator(SEL_ANO).first

                if await campo_num.count() > 0:
                    await campo_num.fill(NUMERO_TESTE, force=True)
                    print(f"Campo numero preenchido: {NUMERO_TESTE}")
                else:
                    # Fallback: primeiro input numerico
                    await all_inputs.first.fill(NUMERO_TESTE, force=True)
                    print(f"Campo numero (fallback primeiro input): {NUMERO_TESTE}")

                if await campo_ano.count() > 0:
                    await campo_ano.fill(ANO_TESTE, force=True)
                    print(f"Campo ano preenchido: {ANO_TESTE}")

                await page.wait_for_timeout(1000)

                # Clica Consultar
                btn = frame_encontrado.locator("input[name='consultar']").first
                if await btn.count() == 0:
                    btn = frame_encontrado.locator("button:has-text('Consultar'), input[value='Consultar']").first
                await btn.click(force=True)
                print("Consultar clicado! Aguardando resposta (20s)...")
                await page.wait_for_timeout(20000)

                # Le o texto do resultado
                texto = await frame_encontrado.inner_text("body")
                print(f"\nTexto apos Consultar (500 chars): {texto[:500]}")
                print(f"'{NUMERO_TESTE}' no resultado: {'SIM' if NUMERO_TESTE in texto else 'NAO'}")

                # Quantidade de resultados
                import re as _re
                total_m = _re.search(r"Total[:\s]+(\d+)|(\d+)\s+registro", texto, _re.IGNORECASE)
                if total_m:
                    print(f"Total encontrado no texto: {total_m.group(0)}")

            except Exception as e:
                print(f"Erro na Fase 2: {e}")
                texto = ""
        else:
            print("\nFase 2 ignorada (formulario nao carregou).")
            texto = ""

        # Captura embed URL (mais recente)
        all_embed = list(dict.fromkeys(embed_urls))  # deduplicado, ordem preservada
        print(f"\nEmbed URLs capturadas ({len(all_embed)}):")
        for eu in all_embed[:5]:
            print(f"  {eu}")

        # Decodifica token do embed para extrair rotina/acao
        api_info = {"embed_urls": all_embed, "xhr_calls": xhr_log[:30]}
        for eu in all_embed[:3]:
            token_match = re.search(r"embed/data/([A-Za-z0-9+/=_%-]+)", eu)
            if token_match:
                import base64, urllib.parse
                token_raw = token_match.group(1)
                token_raw_dec = urllib.parse.unquote(token_raw)
                # Adiciona padding se necessario
                padded = token_raw_dec + "=" * (-len(token_raw_dec) % 4)
                try:
                    decoded = base64.b64decode(padded).decode("utf-8", errors="replace")
                    print(f"\nToken decodificado: {decoded}")
                    try:
                        params = json.loads(decoded)
                        api_info["token_params"] = params
                        print(f"Rotina: {params.get('rotina')}")
                        print(f"Acao: {params.get('acao')}")
                        print(f"ID: {params.get('id')}")
                        print(f"Proxy: {params.get('proxy')}")
                        if params.get("proxy"):
                            print(f"Codigo: {params.get('codigo')}")
                            print(f"Tipo: {params.get('tipo')}")
                    except json.JSONDecodeError:
                        print(f"  (nao e JSON valido)")
                except Exception as e:
                    print(f"  Erro decode: {e}")

        # Adiciona XHR do Consultar e texto do resultado
        if frame_encontrado and inputs_encontrados >= 2:
            api_info["consultar_xhr"] = [xr for xr in xhr_log if "atende.php" in xr.get("url", "")]
            api_info["consultar_texto_resultado"] = texto[:3000] if texto else ""
            print(f"\nXHR pos-Consultar capturados: {len(api_info['consultar_xhr'])}")
            for xr in api_info["consultar_xhr"]:
                rot = ""
                aca = ""
                proc = ""
                import re as _re2
                rm = _re2.search(r"rot=(\d+)", xr.get("url", ""))
                am = _re2.search(r"aca=(\d+)", xr.get("url", ""))
                pm = _re2.search(r"processo=([^&]+)", xr.get("url", ""))
                if rm: rot = rm.group(1)
                if am: aca = am.group(1)
                if pm: proc = pm.group(1)
                resp_status = xr.get("response_status", "?")
                resp_preview = (xr.get("response_body") or "")[:200]
                print(f"  rot={rot} aca={aca} processo={proc} [{resp_status}] => {resp_preview!r}")

        # Salva informacoes da API
        with open(API_INFO_FILE, "w", encoding="utf-8") as f:
            json.dump(api_info, f, indent=2, ensure_ascii=False)
        print(f"\nInfo da API salva em: {API_INFO_FILE}")

        if xhr_log:
            print(f"\nXHR calls capturadas ({len(xhr_log)}):")
            for xr in xhr_log[:10]:
                print(f"  {xr['method']} {xr['url'][:100]}")
                if xr['post_data']:
                    print(f"    POST: {xr['post_data'][:200]}")

        await browser.close()

    print("\nSetup concluido.")


asyncio.run(main())
