"""
Testa se o formulario publico (sem autenticacao) ainda existe.

Acessa a URL de consulta SEM carregar cookies de sessao e captura
qual formulario aparece — se for o anonimo (com codigo de verificacao),
podemos usar esse caminho para monitorar processos de terceiros.

Execute:
    python robots/atendenet_v2/testar_form_anonimo.py
"""
import asyncio
import json
import re
from pathlib import Path

import nodriver as uc
import nodriver.cdp.network as network

CONSULTA_URL = "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"
# URL de login para comparacao
LOGIN_URL = "https://pinhais.atende.net/cidadao/acesso"
# Processo de teste que deveria existir na base do Pinhais
NUMERO_TESTE = "12431"
ANO_TESTE = "2026"
CODIGO_TESTE = "1"  # codigo de verificacao (geralmente 4 digitos — ajuste se necessario)

SEL_INPUT = (
    "input:not([type='hidden']):not([type='submit']):not([type='button'])"
    ":not([type='checkbox']):not([type='radio'])"
    ":not([id*='goog']):not([name='g-recaptcha-response'])"
)

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
    print("TESTE: formulario anonimo pinhais.atende.net")
    print("=" * 60)
    print("Acesso SEM cookies de sessao — como um cidadao nao logado.")
    print()

    xhr_log = []

    browser = await uc.start(
        headless=False,
        browser_args=["--start-maximized"],
    )

    async def on_request(evt: network.RequestWillBeSent):
        url = evt.request.url
        if "atende.php" in url or "embed/data" in url:
            rid = str(evt.request_id)
            pd = evt.request.post_data or ""
            xhr_log.append({
                "_rid": rid,
                "method": evt.request.method,
                "url": url,
                "post_data": pd[:2000],  # captura mais dados
            })

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
                entry["response_body"] = body[:6000]
                break

    tab = await browser.get(CONSULTA_URL)
    tab.add_handler(network.RequestWillBeSent, on_request)
    tab.add_handler(network.ResponseReceived, on_response)
    await tab.send(network.enable(max_post_data_size=65536))

    print(f"URL carregada. Aguardando 10s...\n")
    await tab.sleep(10)

    # Aceita avisos se houver
    for texto_btn in ["Ok", "Continuar o acesso com meu Navegador", "Aceitar"]:
        try:
            btn = await tab.find(texto_btn, best_match=True, timeout=3)
            if btn:
                await btn.click()
                await tab.sleep(2)
        except Exception:
            pass

    # Checa se redirecionou para login
    url_atual = await tab.evaluate("window.location.href") or ""
    print(f"URL atual: {url_atual}")

    if "cidadao/acesso" in url_atual or "login" in url_atual:
        print("\n>>> REDIRECIONOU PARA LOGIN — site exige autenticacao para esta URL.")
        print("    O formulario anonimo NAO esta mais disponivel nessa URL.")
        browser.stop()
        return

    # Aguarda iframe carregar (com captcha se houver)
    inputs_count = 0
    form_text = ""

    for iteracao in range(30):  # 60s
        try:
            inputs_count = int(await tab.evaluate(f"""
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
            """) or 0)
        except Exception:
            inputs_count = 0

        if inputs_count >= 1:
            break

        if iteracao == 5:
            try:
                form_text = str(await tab.evaluate(_JS_TEXTO_FRAME) or "").lower()
                if "verificação" in form_text or "captcha" in form_text:
                    print("CAPTCHA detectado! Resolva manualmente no browser...")
                elif "atividade incomum" in form_text:
                    print("IP bloqueado ('atividade incomum').")
                elif "acesso" in form_text and "login" in form_text:
                    print("Formulario pede login.")
            except Exception:
                pass

        await tab.sleep(2)

    print(f"\nInputs encontrados no iframe: {inputs_count}")

    form_text = str(await tab.evaluate(_JS_TEXTO_FRAME) or "")
    print(f"\n--- Texto do iframe (800 chars) ---")
    print(form_text[:800])

    # Detecta o tipo de formulario
    tem_confirmar = "confirmar" in form_text.lower()
    tem_consultar = "consultar" in form_text.lower()
    tem_codigo = "código" in form_text.lower() and "verificação" not in form_text.lower()
    tem_gerenciamento = "mostrar processos" in form_text.lower() or "responsável" in form_text.lower()
    redirecionou_login = "acesso" in form_text.lower() and inputs_count == 0

    print("\n--- Diagnostico ---")
    if redirecionou_login:
        print("RESULTADO: Formulario exige login (redirecionou para autenticacao no iframe)")
    elif tem_gerenciamento:
        print("RESULTADO: Formulario autenticado/gerenciamento (igual ao que ja temos — CNPJ restrito)")
    elif tem_confirmar and inputs_count >= 2:
        print("RESULTADO: Formulario ANONIMO encontrado! (botao 'confirmar', sem restricao CNPJ)")
        print("  -> Podemos usar esse caminho para monitorar processos de terceiros.")
    elif tem_consultar and inputs_count >= 1:
        print("RESULTADO: Formulario de busca encontrado com botao 'consultar'")
    else:
        print("RESULTADO: Nao foi possivel determinar o tipo de formulario")

    print()

    # Se encontrou form anonimo, testa a busca
    if tem_confirmar and inputs_count >= 2:
        print(f"--- Testando busca anonima: {NUMERO_TESTE}/{ANO_TESTE} ---")
        xhr_log.clear()

        fill_r = await tab.evaluate(f"""
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
                    const inputs = [...alvo.querySelectorAll({repr(SEL_INPUT)})];
                    if (inputs.length < 2) return 'poucos:' + inputs.length;
                    setVal(inputs[0], '{NUMERO_TESTE}');
                    if (inputs.length > 2) setVal(inputs[1], '{ANO_TESTE}');
                    if (inputs.length > 1) setVal(inputs[inputs.length - 1], '{CODIGO_TESTE}');
                    return inputs.map(i => i.name + '=' + i.value).join(' | ');
                }} catch(e) {{ return 'erro:' + e.message; }}
            }}
            return 'sem_frame';
        }})()
        """)
        print(f"Preenchimento: {fill_r}")
        await tab.sleep(1)

        click_r = await tab.evaluate("""
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
                    const btn = alvo.querySelector("button[name='confirmar']")
                             || alvo.querySelector("input[name='confirmar']")
                             || alvo.querySelector("button[type='submit']");
                    if (btn) { btn.click(); return 'clicado:' + btn.name; }
                    return 'btn_nao_encontrado';
                } catch(e) { return 'erro:' + e.message; }
            }
            return 'sem_frame';
        })()
        """)
        print(f"Submit: {click_r}")
        await tab.sleep(15)

        texto_result = str(await tab.evaluate(_JS_TEXTO_FRAME) or "")
        print(f"\nResultado (500): {texto_result[:500]}")

        if xhr_log:
            print(f"\nXHR capturados ({len(xhr_log)}):")
            for xr in xhr_log:
                if "atende.php" in xr.get("url", ""):
                    rm = re.search(r"rot=(\d+)", xr["url"])
                    am = re.search(r"aca=(\d+)", xr["url"])
                    print(f"  rot={rm.group(1) if rm else '?'} aca={am.group(1) if am else '?'}")
                    pd_decoded = xr.get("post_data", "")
                    if pd_decoded:
                        from urllib.parse import parse_qs, unquote
                        parts = parse_qs(pd_decoded, keep_blank_values=True)
                        for k, v in parts.items():
                            print(f"    {k}: {v[0][:400]}")
                    body = xr.get("response_body", "")
                    if body:
                        print(f"  Resposta: {body[:300]!r}")

    # Exibe todos os XHR capturados
    all_atende = [x for x in xhr_log if "atende.php" in x.get("url", "")]
    if all_atende:
        print(f"\n--- Todos XHR atende.php ({len(all_atende)}) ---")
        for xr in all_atende:
            rm = re.search(r"rot=(\d+)", xr["url"])
            am = re.search(r"aca=(\d+)", xr["url"])
            pm = re.search(r"processo=([^&]+)", xr["url"])
            body = (xr.get("response_body") or "")[:200]
            print(f"  rot={rm.group(1) if rm else '?'} aca={am.group(1) if am else '?'} {pm.group(1) if pm else ''}")
            if body:
                print(f"  => {body!r}")

    browser.stop()
    print("\nTeste concluido.")


asyncio.run(main())
