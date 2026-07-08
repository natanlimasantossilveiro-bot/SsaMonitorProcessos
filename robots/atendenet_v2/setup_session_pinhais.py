"""
Setup de sessao: abre browser visivel para login manual no pinhais.atende.net.
Salva sessao em session_state.json e captura parametros da API em api_info.json.

Execute sempre que a sessao expirar:
    python robots/atendenet_v2/setup_session_pinhais.py
"""
import asyncio
import json
import re
from pathlib import Path

import nodriver as uc
import nodriver.cdp.network as network

LOGIN_URL = "https://pinhais.atende.net/cidadao/acesso/tipo/1/redirect/YXV0b2F0ZW5kaW1lbnRv"
CONSULTA_URL = "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"
SESSION_FILE = Path(__file__).parent / "session_state.json"
API_INFO_FILE = Path(__file__).parent / "api_info.json"

NUMERO_TESTE = "12431"
ANO_TESTE = "2026"

SEL_INPUT = (
    "input:not([type='hidden']):not([type='submit']):not([type='button'])"
    ":not([type='checkbox']):not([type='radio'])"
    ":not([id*='goog']):not([name='g-recaptcha-response'])"
)

# JS helpers para interagir com iframes de mesmo domínio via contentDocument
_JS_CONTAR_INPUTS = f"""
(() => {{
    for (const iframe of document.querySelectorAll('iframe')) {{
        const src = iframe.src || '';
        if (!src.includes('embed/data')) continue;
        try {{
            const doc = iframe.contentDocument;
            if (!doc) continue;
            const nested = doc.querySelectorAll('iframe[src*="embed/data"]');
            const alvo = nested.length > 0 && nested[0].contentDocument
                ? nested[0].contentDocument : doc;
            return alvo.querySelectorAll({repr(SEL_INPUT)}).length;
        }} catch(e) {{ continue; }}
    }}
    return 0;
}})()
"""

_JS_TEXTO_FRAME = """
(() => {
    for (const iframe of document.querySelectorAll('iframe')) {
        const src = iframe.src || '';
        if (!src.includes('embed/data')) continue;
        try {
            const doc = iframe.contentDocument;
            if (!doc) continue;
            const nested = doc.querySelectorAll('iframe[src*="embed/data"]');
            const alvo = nested.length > 0 && nested[0].contentDocument
                ? nested[0].contentDocument : doc;
            return alvo.body ? alvo.body.innerText : '';
        } catch(e) { continue; }
    }
    return '';
})()
"""


async def main():
    print("=" * 60)
    print("SETUP DE SESSAO — pinhais.atende.net  [nodriver]")
    print("=" * 60)
    print()
    print("1. Browser vai abrir na pagina de login.")
    print("2. Faca o login com seu CNPJ e senha.")
    print("3. Apos o login, aguarde — o script salva a sessao.")
    print()

    xhr_log = []
    embed_urls = []

    browser = await uc.start(
        headless=False,
        browser_args=["--start-maximized"],
    )
    tab = await browser.get(LOGIN_URL)

    # ── Monitora requisicoes de rede ─────────────────────────────────────────
    async def on_request(evt: network.RequestWillBeSent):
        url = evt.request.url
        if any(x in url for x in ["embed/data", "atende.php"]):
            rid = str(evt.request_id)
            pd = evt.request.post_data or ""
            xhr_log.append({
                "_rid": rid,
                "method": evt.request.method,
                "url": url,
                "post_data": pd[:600],
            })
            if "embed/data/" in url:
                embed_urls.append(url)

    async def on_response(evt: network.ResponseReceived):
        url = evt.response.url
        if "atende.php" not in url:
            return
        rid = str(evt.request_id)
        for entry in reversed(xhr_log):
            if entry.get("_rid") == rid and "response_body" not in entry:
                try:
                    body, _ = await tab.send(
                        network.get_response_body(request_id=evt.request_id)
                    )
                except Exception:
                    body = ""
                entry["response_status"] = evt.response.status
                entry["response_body"] = body[:4000]
                break

    tab.add_handler(network.RequestWillBeSent, on_request)
    tab.add_handler(network.ResponseReceived, on_response)
    await tab.send(network.enable())

    await tab.sleep(3)

    try:
        btn = await tab.find("Aceitar", best_match=True, timeout=5)
        if btn:
            await btn.click()
            print("Cookies aceitos.")
    except Exception:
        pass

    # ── Aguarda login ─────────────────────────────────────────────────────────
    print("Aguardando login (ate 3 minutos)...")
    logado = False
    for _ in range(90):
        try:
            url_atual = await tab.evaluate("window.location.href")
            if "autoatendimento" in (url_atual or ""):
                logado = True
                break
        except Exception:
            pass
        await tab.sleep(2)

    if not logado:
        print("Timeout aguardando login. Encerrando.")
        browser.stop()
        return

    print("Login detectado!")
    await tab.sleep(2)

    # ── Salva cookies ─────────────────────────────────────────────────────────
    cookies_raw = await browser.cookies.get_all()
    cookies_list = []
    for c in cookies_raw:
        try:
            cookies_list.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain or "pinhais.atende.net",
                "path": c.path or "/",
                "expires": c.expires or -1,
                "httpOnly": c.http_only or False,
                "secure": c.secure or False,
                "sameSite": str(c.same_site or "Lax"),
            })
        except Exception:
            pass

    state = {"cookies": cookies_list}
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    print(f"Sessao salva: {SESSION_FILE}  ({len(cookies_list)} cookies)")

    # ── Navega para consulta ──────────────────────────────────────────────────
    print("\nAcessando pagina de consulta...")
    xhr_log.clear()
    embed_urls.clear()

    await tab.get(CONSULTA_URL)
    await tab.sleep(3)

    for texto_btn in ["Continuar o acesso com meu Navegador", "Aceitar"]:
        try:
            btn = await tab.find(texto_btn, best_match=True, timeout=3)
            if btn:
                await btn.click()
                await tab.sleep(2)
        except Exception:
            pass

    await tab.sleep(3)

    # ── Aguarda formulario (com deteccao de captcha) ──────────────────────────
    inputs_count = 0
    aviso_captcha = False

    for iteracao in range(90):  # ate 3 min
        try:
            inputs_count = int(await tab.evaluate(_JS_CONTAR_INPUTS) or 0)
        except Exception:
            inputs_count = 0

        if inputs_count >= 1:
            break

        if iteracao == 4 and not aviso_captcha:
            try:
                texto_frame = str(await tab.evaluate(_JS_TEXTO_FRAME) or "").lower()
                if "verificação" in texto_frame or "captcha" in texto_frame:
                    print("\n*** CAPTCHA detectado! ***")
                    print("    Resolva o modal 'Verificacao de acesso' no browser aberto.")
                    print("    O script aguarda ate 3 minutos...\n")
                    aviso_captcha = True
                elif "atividade incomum" in texto_frame:
                    print("\n*** IP bloqueado ('atividade incomum'). ***")
                    print("    Aguarde e tente novamente mais tarde.")
                    break
            except Exception:
                pass

        await tab.sleep(2)

    if inputs_count >= 2:
        print(f"Formulario carregou ({inputs_count} inputs).")
    else:
        print(f"Aviso: formulario nao carregou (inputs={inputs_count}).")

    # ── Fase 2: preenche e captura XHR do Consultar ───────────────────────────
    texto_resultado = ""
    consultar_xhr = []

    if inputs_count >= 2:
        print(f"\n--- Fase 2: Preenchendo {NUMERO_TESTE}/{ANO_TESTE} ---")
        xhr_log.clear()

        try:
            # Lista inputs para debug
            debug_inputs = await tab.evaluate(f"""
            (() => {{
                for (const iframe of document.querySelectorAll('iframe')) {{
                    const src = iframe.src || '';
                    if (!src.includes('embed/data')) continue;
                    try {{
                        const doc = iframe.contentDocument;
                        if (!doc) continue;
                        const nested = doc.querySelectorAll('iframe[src*="embed/data"]');
                        const alvo = nested.length > 0 && nested[0].contentDocument
                            ? nested[0].contentDocument : doc;
                        const inputs = alvo.querySelectorAll({repr(SEL_INPUT)});
                        return Array.from(inputs).map(i =>
                            i.name + ':' + (i.getAttribute('aria-description') || '?')
                        ).join(' | ');
                    }} catch(e) {{ continue; }}
                }}
                return 'sem_frame';
            }})()
            """)
            print(f"Inputs: {debug_inputs}")

            # Preenche numero e ano via JS
            fill_result = await tab.evaluate(f"""
            (() => {{
                const setVal = (el, v) => {{
                    el.value = v;
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }};
                for (const iframe of document.querySelectorAll('iframe')) {{
                    const src = iframe.src || '';
                    if (!src.includes('embed/data')) continue;
                    try {{
                        const doc = iframe.contentDocument;
                        if (!doc) continue;
                        const nested = doc.querySelectorAll('iframe[src*="embed/data"]');
                        const alvo = nested.length > 0 && nested[0].contentDocument
                            ? nested[0].contentDocument : doc;
                        const num = alvo.querySelector(
                            "input[name='campo01'][aria-description='campo numérico']"
                        ) || alvo.querySelectorAll({repr(SEL_INPUT)})[0];
                        if (num) setVal(num, '{NUMERO_TESTE}');
                        const ano = alvo.querySelector(
                            "input[name='campo01'][aria-description='campo ano']"
                        );
                        if (ano) setVal(ano, '{ANO_TESTE}');
                        return 'ok';
                    }} catch(e) {{ return 'erro:' + e.message; }}
                }}
                return 'sem_frame';
            }})()
            """)
            print(f"Preenchimento: {fill_result}")
            await tab.sleep(1)

            # Clica Consultar via JS
            click_result = await tab.evaluate("""
            (() => {
                for (const iframe of document.querySelectorAll('iframe')) {
                    const src = iframe.src || '';
                    if (!src.includes('embed/data')) continue;
                    try {
                        const doc = iframe.contentDocument;
                        if (!doc) continue;
                        const nested = doc.querySelectorAll('iframe[src*="embed/data"]');
                        const alvo = nested.length > 0 && nested[0].contentDocument
                            ? nested[0].contentDocument : doc;
                        const btn = alvo.querySelector("input[name='consultar']")
                                 || alvo.querySelector("input[type='button']")
                                 || alvo.querySelector("button[type='submit']");
                        if (btn) { btn.click(); return 'clicado:' + btn.name; }
                        return 'btn_nao_encontrado';
                    } catch(e) { return 'erro:' + e.message; }
                }
                return 'sem_frame';
            })()
            """)
            print(f"Consultar: {click_result}")
            print("Aguardando resposta (20s)...")
            await tab.sleep(20)

            # Texto do resultado
            texto_resultado = str(await tab.evaluate(_JS_TEXTO_FRAME) or "")
            print(f"Texto resultado (500): {texto_resultado[:500]}")
            print(f"'{NUMERO_TESTE}' no resultado: {'SIM' if NUMERO_TESTE in texto_resultado else 'NAO'}")

            consultar_xhr = [x for x in xhr_log if "atende.php" in x.get("url", "")]
            print(f"\nXHR pos-Consultar: {len(consultar_xhr)}")
            for xr in consultar_xhr:
                rm = re.search(r"rot=(\d+)", xr.get("url", ""))
                am = re.search(r"aca=(\d+)", xr.get("url", ""))
                pm = re.search(r"processo=([^&]+)", xr.get("url", ""))
                rot = rm.group(1) if rm else "?"
                aca = am.group(1) if am else "?"
                proc = pm.group(1) if pm else ""
                preview = (xr.get("response_body") or "")[:150]
                st = xr.get("response_status", "?")
                print(f"  rot={rot} aca={aca} {proc} [{st}] => {preview!r}")

        except Exception as e:
            print(f"Erro Fase 2: {e}")

    # ── Decodifica token do embed ─────────────────────────────────────────────
    all_embed = list(dict.fromkeys(embed_urls))
    print(f"\nEmbed URLs capturadas ({len(all_embed)}):")
    for eu in all_embed[:5]:
        print(f"  {eu}")

    api_info = {
        "embed_urls": all_embed[:10],
        "xhr_calls": [
            {k: v for k, v in x.items() if k != "_rid"}
            for x in xhr_log[:30]
        ],
        "consultar_xhr": [
            {k: v for k, v in x.items() if k != "_rid"}
            for x in consultar_xhr
        ],
        "consultar_texto_resultado": texto_resultado[:3000],
    }

    for eu in all_embed[:3]:
        m = re.search(r"embed/data/([A-Za-z0-9+/=_%-]+)", eu)
        if not m:
            continue
        import base64, urllib.parse
        try:
            raw = urllib.parse.unquote(m.group(1))
            padded = raw + "=" * (-len(raw) % 4)
            decoded = base64.b64decode(padded).decode("utf-8", errors="replace")
            decoded_clean = decoded[:decoded.rfind("}") + 1]
            params = json.loads(decoded_clean)
            api_info["token_params"] = params
            print(f"\nToken decodificado: {decoded_clean}")
            break
        except Exception:
            pass

    with open(API_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(api_info, f, indent=2, ensure_ascii=False)
    print(f"\nAPI info salva: {API_INFO_FILE}")

    browser.stop()
    print("\nSetup concluido.")


asyncio.run(main())
