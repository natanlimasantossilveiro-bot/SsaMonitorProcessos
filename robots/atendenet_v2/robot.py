import asyncio
import json
import re
from pathlib import Path

import nodriver as uc

from services.captcha_api_client import (
    enviar_captcha_para_api,
    consultar_resultado_captcha_api,
)
from utils.logger import get_logger

_semaphore = asyncio.Semaphore(2)
SESSION_FILE = Path(__file__).parent / "session_state.json"

log = get_logger("atendenet")

SITEKEY_PADRAO_PINHAIS = "6LenD30sAAAAADTdG6GJYoAxOIZy9SEYg1VSY24j"
SITEKEY_MODAL_PINHAIS = "6Le9DX0sAAAAAM10_leN11PLggPbvzjQKcpm3VFW"

# JS: encontra o documento do formulário dentro dos iframes de mesmo domínio
_JS_EMBED_DOC = """
const __embedDoc = () => {
    for (const iframe of document.querySelectorAll('iframe')) {
        const src = iframe.src || '';
        if (!src.includes('embed/data')) continue;
        try {
            const doc = iframe.contentDocument;
            if (!doc) continue;
            const nested = doc.querySelectorAll('iframe[src*="embed/data"]');
            if (nested.length > 0 && nested[0].contentDocument)
                return [nested[0].contentDocument, nested[0].contentWindow];
            return [doc, iframe.contentWindow];
        } catch(e) { continue; }
    }
    return [null, null];
};
"""

SEL_INPUT = (
    "input:not([type='hidden']):not([type='submit']):not([type='button'])"
    ":not([type='checkbox']):not([type='radio'])"
    ":not([id*='goog']):not([name='g-recaptcha-response'])"
)


async def resolver_captcha(site_key, url, method="userrecaptcha"):
    log.info(f"Enviando captcha para 2captcha (method={method})...")

    resultado_envio = await enviar_captcha_para_api(
        processo={},
        sitekey=site_key,
        url=url,
        method=method,
    )

    if resultado_envio.get("status") != "ENVIADO_API":
        raise Exception(f"Erro ao enviar captcha: {resultado_envio}")

    protocolo = resultado_envio.get("protocolo_api")
    log.info(f"Protocolo 2captcha: {protocolo}")

    resultado = await consultar_resultado_captcha_api(protocolo)

    if resultado.get("status") != "RESOLVIDO":
        raise Exception(f"Falha ao resolver captcha: {resultado}")

    log.info("Captcha resolvido com sucesso")
    return resultado.get("resposta")


class RobotAtendeNetV2:

    async def consultar_processo(self, processo):
        async with _semaphore:
            return await self._consultar_processo_impl(processo)

    async def _consultar_processo_impl(self, processo):

        url = (
            processo.get("acesso")
            or "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"
        )

        municipio = processo.get("municipio") or processo.get("nome_orgao") or "AtendNet"
        log.info(f"Iniciando consulta — municipio: {municipio}")

        # Formulario anonimo nao precisa de autenticacao.
        # A restricao de CNPJ so existe no formulario gerenciamento (autenticado).
        codigo = processo.get("codigo") or ""
        if not codigo:
            log.warning(
                f"Processo {processo.get('numero_processo')} sem codigo_verificador — "
                "consulta anonima impossivel. Atualize o campo 'Codigo' na planilha."
            )
            return {"status": "CODIGO_VERIFICADOR_AUSENTE"}

        browser = await uc.start(
            headless=True,
            sandbox=False,
            browser_args=[
                "--disable-dev-shm-usage",
                "--window-size=1280,800",
            ],
        )

        try:
            # ── Navega diretamente (sem sessao) — formulario anonimo ─────────
            tab = await browser.get(url)
            await tab.sleep(3)

            for texto_btn in ["Ok", "Continuar o acesso com meu Navegador", "Aceitar"]:
                try:
                    btn = await tab.find(texto_btn, best_match=True, timeout=3)
                    if btn:
                        await btn.click()
                        await tab.sleep(1)
                except Exception:
                    pass

            await tab.sleep(3)

            # ── Resolve modal de verificacao de acesso ────────────────────────
            await self._resolver_modal_verificacao_acesso(tab, url)
            await tab.sleep(1)

            # ── Aguarda formulario ────────────────────────────────────────────
            inputs_ok = False
            for _ in range(10):
                try:
                    cnt = await tab.evaluate(
                        f"(() => {{ {_JS_EMBED_DOC} const [doc] = __embedDoc(); "
                        f"return doc ? doc.querySelectorAll({repr(SEL_INPUT)}).length : 0; }})()"
                    )
                    if int(cnt or 0) >= 1:
                        inputs_ok = True
                        break
                except Exception:
                    pass
                log.debug("Aguardando iframe do formulario carregar...")
                await tab.sleep(2)

            if not inputs_ok:
                # Verifica sessao expirada
                check = await tab.evaluate(
                    f"(() => {{ {_JS_EMBED_DOC} const [doc] = __embedDoc();"
                    "const h = doc ? doc.body.innerHTML : '';"
                    "return (h.includes('acessar_conta') || h.includes('cidadao/acesso')) ? 'expirada' : 'sem_form';"
                    "})()"
                )
                if check == "expirada":
                    raise Exception(
                        "SESSAO_EXPIRADA: execute "
                        "robots/atendenet_v2/setup_session_pinhais.py"
                    )
                raise Exception("Iframe com formulario nao encontrado")

            log.info("Iframe do formulario localizado")

            # ── Dados do processo ─────────────────────────────────────────────
            numero = processo.get("numero_processo")
            ano = processo.get("exercicio") or ""
            numero_base = re.sub(r"[^0-9]", "", str(numero))
            log.info(f"Numero: {numero_base} | Ano: {ano} | Codigo: {codigo}")

            # ── Detecta tipo de formulario ────────────────────────────────────
            is_form_autenticado = await tab.evaluate(
                f"(() => {{ {_JS_EMBED_DOC} const [doc] = __embedDoc();"
                "return doc ? !!doc.querySelector(\"input[name='campo01'][aria-description='campo numérico']\") : false;"
                "})()"
            )

            # ── Preenche formulario via JS ────────────────────────────────────
            if is_form_autenticado:
                log.info("Formulario autenticado detectado (filtros de busca)")

                fill_r = await tab.evaluate(f"""
                (() => {{
                    {_JS_EMBED_DOC}
                    const [doc] = __embedDoc();
                    if (!doc) return 'sem_doc';
                    const setVal = (el, v) => {{
                        el.value = v;
                        el.dispatchEvent(new Event('input', {{bubbles: true}}));
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }};
                    const num = doc.querySelector("input[name='campo01'][aria-description='campo numérico']");
                    if (num) setVal(num, '{numero_base}');
                    const ano = doc.querySelector("input[name='campo01'][aria-description='campo ano']");
                    if (ano && '{ano}') setVal(ano, '{ano}');
                    return 'ok';
                }})()
                """)
                log.info(f"Filtros preenchidos: {fill_r}")

            else:
                log.info("Formulario anonimo detectado (preenchimento posicional)")

                fill_r = await tab.evaluate(f"""
                (() => {{
                    {_JS_EMBED_DOC}
                    const [doc] = __embedDoc();
                    if (!doc) return 'sem_doc';
                    const setVal = (el, v) => {{
                        el.value = v;
                        el.dispatchEvent(new Event('input', {{bubbles: true}}));
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }};
                    const inputs = [...doc.querySelectorAll({repr(SEL_INPUT)})];
                    if (inputs.length < 2) return 'poucos:' + inputs.length;
                    setVal(inputs[0], '{numero_base}');
                    if (inputs.length > 2) setVal(inputs[1], '{ano}');
                    setVal(inputs[inputs.length - 1], '{codigo}');
                    return inputs.map(i => i.name + '=' + i.value).join(' | ');
                }})()
                """)
                log.info(f"Campos posicionais: {fill_r}")

            await tab.sleep(2)

            # ── Captcha no formulario (se houver) ────────────────────────────
            site_key_form = await tab.evaluate(f"""
            (() => {{
                {_JS_EMBED_DOC}
                const [doc] = __embedDoc();
                if (!doc) return null;
                const el = doc.querySelector('[data-sitekey]');
                if (el) return el.getAttribute('data-sitekey');
                for (const iframe of doc.querySelectorAll('iframe')) {{
                    const src = iframe.src || '';
                    const m = src.match(/k=([^&]+)/);
                    if (m && src.includes('recaptcha')) return m[1];
                }}
                return null;
            }})()
            """)

            if site_key_form:
                log.info(f"Captcha no formulario: {site_key_form}")
                token = await resolver_captcha(site_key_form, url)
                await self._injetar_token_embed(tab, token)
                await tab.sleep(2)
            else:
                log.info("Sem captcha no formulario")

            # ── Submit ────────────────────────────────────────────────────────
            btn_sels = (
                ["input[name='consultar']", "input[type='button']", "button[type='submit']"]
                if is_form_autenticado
                else ["button[name='confirmar']", "input[name='confirmar']",
                      "button[type='submit']", "input[type='submit']"]
            )
            btn_sels_js = json.dumps(btn_sels)

            submit_r = await tab.evaluate(f"""
            (() => {{
                {_JS_EMBED_DOC}
                const [doc] = __embedDoc();
                if (!doc) return 'sem_doc';
                for (const sel of {btn_sels_js}) {{
                    const btn = doc.querySelector(sel);
                    if (btn) {{ btn.click(); return 'clicado:' + sel; }}
                }}
                return 'btn_nao_encontrado';
            }})()
            """)
            log.info(f"Submit: {submit_r}")

            if "nao_encontrado" in str(submit_r):
                raise Exception("Botao de submit nao encontrado no formulario")

            await tab.sleep(5)

            # ── Seleciona processo na lista (formulario autenticado) ──────────
            if is_form_autenticado:
                sel_r = await tab.evaluate(f"""
                (() => {{
                    {_JS_EMBED_DOC}
                    const [doc] = __embedDoc();
                    if (!doc) return 'sem_doc';
                    // Procura texto exato do numero na tabela
                    const todos = [...doc.querySelectorAll('tr')];
                    for (const tr of todos) {{
                        if (tr.textContent.includes('{numero_base}')) {{
                            tr.click();
                            return 'selecionado_tr';
                        }}
                    }}
                    // Fallback: elemento folha com texto exato
                    const el = [...doc.querySelectorAll('*')].find(
                        e => e.children.length === 0 && e.textContent.trim() === '{numero_base}'
                    );
                    if (el) {{ el.click(); return 'selecionado_texto'; }}
                    return 'nao_encontrado_na_lista';
                }})()
                """)
                log.info(f"Selecao na lista: {sel_r}")
                if "selecionado" in str(sel_r):
                    await tab.sleep(3)

            # ── Extrai objeto do processo (Observação de Abertura) ───────────
            objeto = None
            try:
                texto_info = str(await tab.evaluate(f"""
                (() => {{
                    {_JS_EMBED_DOC}
                    const [doc] = __embedDoc();
                    return doc && doc.body ? doc.body.innerText : '';
                }})()
                """) or "")

                for marcador in ["Observação de Abertura:", "Observacao de Abertura:"]:
                    if marcador in texto_info:
                        idx = texto_info.index(marcador) + len(marcador)
                        objeto = texto_info[idx:idx + 1000].strip()
                        break
            except Exception as e:
                log.debug(f"Nao foi possivel extrair objeto: {e}")

            # ── Extrai movimentacoes ──────────────────────────────────────────
            await tab.sleep(6)
            movimentacoes = []

            # Tenta aba "Linha do Tempo"
            try:
                ldt_r = await tab.evaluate(f"""
                (() => {{
                    {_JS_EMBED_DOC}
                    const [doc] = __embedDoc();
                    if (!doc) return 'sem_doc';
                    const el = [...doc.querySelectorAll('*')].find(
                        e => e.children.length === 0 && e.textContent.trim() === 'Linha do Tempo'
                    );
                    if (el) {{ el.click(); return 'clicado'; }}
                    // Fallback: procura abas com texto similar
                    const aba = [...doc.querySelectorAll('li, a, button, [role="tab"]')].find(
                        e => e.textContent.includes('Linha') && e.textContent.includes('Tempo')
                    );
                    if (aba) {{ aba.click(); return 'clicado_fallback'; }}
                    return 'nao_encontrado';
                }})()
                """)
                await tab.sleep(2)
                log.info(f"Aba Linha do Tempo: {ldt_r}")
            except Exception as e:
                log.debug(f"Aba Linha do Tempo nao clicavel: {e}")

            texto_aba = str(await tab.evaluate(f"""
            (() => {{
                {_JS_EMBED_DOC}
                const [doc] = __embedDoc();
                return doc && doc.body ? doc.body.innerText : '';
            }})()
            """) or "")
            log.debug(f"Texto aba pos-submit (1500): {texto_aba[:1500]}")

            marcador = "Data do Movimento:"
            secoes = texto_aba.split(marcador)
            for secao in secoes[1:]:
                secao = secao.strip()
                if not secao:
                    continue
                primeira_linha = secao.split("\n")[0].strip()
                if not re.match(r"\d{2}/\d{2}/\d{4}", primeira_linha):
                    continue
                movimentacoes.append((marcador + " " + secao)[:600].strip())

            log.info(f"Linha do Tempo: {len(movimentacoes)} movimento(s)")

            # Fallback: tabela Historico
            if not movimentacoes:
                try:
                    await tab.evaluate(f"""
                    (() => {{
                        {_JS_EMBED_DOC}
                        const [doc] = __embedDoc();
                        if (!doc) return;
                        const el = [...doc.querySelectorAll('*')].find(
                            e => e.children.length === 0 && e.textContent.trim() === 'Historico'
                        );
                        if (el) el.click();
                    }})()
                    """)
                    await tab.sleep(1.5)
                except Exception:
                    pass

                texto_hist = str(await tab.evaluate(f"""
                (() => {{
                    {_JS_EMBED_DOC}
                    const [doc] = __embedDoc();
                    if (!doc) return '';
                    return [...doc.querySelectorAll('table tr')]
                        .map(r => r.innerText).join('\\n');
                }})()
                """) or "")

                for linha in texto_hist.split("\n"):
                    linha = linha.strip()
                    if linha and re.search(r"\d{2}/\d{2}/\d{4}", linha):
                        movimentacoes.append(linha)
                log.info(f"Historico (fallback): {len(movimentacoes)} linhas com data")

            log.info(f"Total movimentacoes extraidas: {len(movimentacoes)}")

            # ── Status ────────────────────────────────────────────────────────
            texto_total = " ".join(movimentacoes).lower()

            if "indeferido" in texto_total:
                status = "Indeferido"
            elif "encerrado" in texto_total or "deferido" in texto_total:
                status = "Finalizado"
            elif "nao encontrado" in texto_total or "não encontrado" in texto_total:
                return {"status": "PROCESSO_NAO_ENCONTRADO"}
            else:
                status = "Em analise"

            log.info(f"Status: {status}")

            return {
                "status": "OK",
                "status_processo": status,
                "movimentacoes": movimentacoes,
                "objeto": objeto,
            }

        finally:
            browser.stop()

    async def _resolver_modal_verificacao_acesso(self, tab, url):
        """
        Detecta e resolve o modal 'Verificacao de acesso'.
        Suporta reCAPTCHA v2 (Google) e Cloudflare Turnstile.
        """
        try:
            # Verifica se modal esta presente (mesmo dominio = acessivel via JS)
            modal_presente = await tab.evaluate("""
            (() => {
                for (const iframe of document.querySelectorAll('iframe')) {
                    try {
                        const doc = iframe.contentDocument;
                        if (doc && doc.body.innerHTML.toLowerCase().includes('verificação de acesso'))
                            return true;
                    } catch(e) {}
                }
                return false;
            })()
            """)

            if not modal_presente:
                log.debug("Modal 'Verificacao de acesso' nao apareceu")
                return False

            log.info("Modal de verificacao detectado")

            captcha_method = "userrecaptcha"
            site_key = None

            # Cloudflare Turnstile: iframe cross-origin visiivel no DOM principal
            turnstile_url = await tab.evaluate("""
            (() => {
                // Busca em todos os iframes (inclusive aninhados de mesmo dominio)
                const check = (doc) => {
                    for (const iframe of doc.querySelectorAll('iframe')) {
                        const src = iframe.src || '';
                        if (src.includes('challenges.cloudflare.com') && src.includes('turnstile'))
                            return src;
                    }
                    return null;
                };
                const top_hit = check(document);
                if (top_hit) return top_hit;
                for (const iframe of document.querySelectorAll('iframe')) {
                    try {
                        const doc = iframe.contentDocument;
                        if (!doc) continue;
                        const hit = check(doc);
                        if (hit) return hit;
                    } catch(e) {}
                }
                return null;
            })()
            """)

            if turnstile_url:
                m = re.search(r"/([0-9a-zA-Z_-]{20,})/", turnstile_url)
                if m:
                    site_key = m.group(1)
                    captcha_method = "turnstile"
                    log.info(f"Cloudflare Turnstile detectado — sitekey: {site_key}")

            # reCAPTCHA v2: anchor iframe do Google
            if not site_key:
                recaptcha_url = await tab.evaluate("""
                (() => {
                    const check = (doc) => {
                        for (const iframe of doc.querySelectorAll('iframe')) {
                            const src = iframe.src || '';
                            if (src.includes('api2/anchor') && !src.includes('invisible'))
                                return src;
                        }
                        return null;
                    };
                    const top_hit = check(document);
                    if (top_hit) return top_hit;
                    for (const iframe of document.querySelectorAll('iframe')) {
                        try {
                            const doc = iframe.contentDocument;
                            if (!doc) continue;
                            const hit = check(doc);
                            if (hit) return hit;
                        } catch(e) {}
                    }
                    return null;
                })()
                """)

                if recaptcha_url:
                    m = re.search(r"[?&]k=([^&]+)", recaptcha_url)
                    if m:
                        site_key = m.group(1)
                        log.info(f"reCAPTCHA v2 detectado — sitekey: {site_key}")

            if not site_key:
                log.warning("Tipo de captcha nao detectado — usando sitekey padrao")
                site_key = SITEKEY_MODAL_PINHAIS

            token = await resolver_captcha(site_key, url, method=captcha_method)

            # ── Injeta token no modal ─────────────────────────────────────────
            if captcha_method == "turnstile":
                inject_js = f"""
                (() => {{
                    const results = [];
                    const inject = (doc, win) => {{
                        doc.querySelectorAll('[name="cf-turnstile-response"]').forEach(el => {{
                            el.value = '{token}';
                            results.push('cf-turnstile injetado');
                        }});
                        doc.querySelectorAll('[data-callback]').forEach(el => {{
                            const cb = el.getAttribute('data-callback');
                            if (cb && typeof win[cb] === 'function') {{
                                try {{ win[cb]('{token}'); results.push('data-callback:' + cb); }}
                                catch(e) {{ results.push('err:' + e.message); }}
                            }}
                        }});
                        try {{
                            const comp = win.componente;
                            const tela = comp?.["1211"]?.["102"]?.["1"]?.["tela_acesso_captcha"]?.["tela_acesso_captcha"];
                            const rec  = comp?.["1211"]?.["102"]?.["1"]?.["tela_acesso_captcha"]?.["recaptcha"];
                            if (tela && rec && typeof win.onValidaCaptchaAcessoSistema === 'function') {{
                                win.onValidaCaptchaAcessoSistema.apply(rec, [tela]);
                                results.push('onValidaCaptcha_ok');
                            }} else {{ results.push('fn_nao_encontrada'); }}
                        }} catch(e) {{ results.push('err_ipm:' + e.message); }}
                    }};
                    for (const iframe of document.querySelectorAll('iframe')) {{
                        try {{
                            const doc = iframe.contentDocument;
                            if (doc && doc.body.innerHTML.toLowerCase().includes('verificação de acesso'))
                                inject(doc, iframe.contentWindow);
                        }} catch(e) {{}}
                    }}
                    return results.join(' | ') || 'modal_nao_encontrado';
                }})()
                """
            else:
                inject_js = f"""
                (() => {{
                    const results = [];
                    const inject = (doc, win) => {{
                        doc.querySelectorAll("textarea[name='g-recaptcha-response']").forEach(el => {{
                            el.style.display = 'block';
                            el.value = '{token}';
                            el.dispatchEvent(new Event('input', {{bubbles: true}}));
                            el.dispatchEvent(new Event('change', {{bubbles: true}}));
                            results.push('g-recaptcha injetado');
                        }});
                        if (win.grecaptcha && typeof win.grecaptcha.getResponse === 'function') {{
                            win.grecaptcha.getResponse = function() {{ return '{token}'; }};
                            results.push('getResponse_patchado');
                        }}
                        try {{
                            const comp = win.componente;
                            const tela = comp?.["1211"]?.["102"]?.["1"]?.["tela_acesso_captcha"]?.["tela_acesso_captcha"];
                            const rec  = comp?.["1211"]?.["102"]?.["1"]?.["tela_acesso_captcha"]?.["recaptcha"];
                            if (tela && rec && typeof win.onValidaCaptchaAcessoSistema === 'function') {{
                                win.onValidaCaptchaAcessoSistema.apply(rec, [tela]);
                                results.push('onValidaCaptcha_ok');
                            }} else {{ results.push('fn_nao_encontrada'); }}
                        }} catch(e) {{ results.push('err_ipm:' + e.message); }}
                    }};
                    for (const iframe of document.querySelectorAll('iframe')) {{
                        try {{
                            const doc = iframe.contentDocument;
                            if (doc && doc.body.innerHTML.toLowerCase().includes('verificação de acesso'))
                                inject(doc, iframe.contentWindow);
                        }} catch(e) {{}}
                    }}
                    return results.join(' | ') || 'modal_nao_encontrado';
                }})()
                """

            inject_r = await tab.evaluate(inject_js)
            log.debug(f"Injecao captcha modal: {inject_r}")

            # Aguarda modal fechar
            for tentativa in range(15):
                await tab.sleep(1)
                modal_ainda = await tab.evaluate("""
                (() => {
                    for (const iframe of document.querySelectorAll('iframe')) {
                        try {
                            const doc = iframe.contentDocument;
                            if (doc && doc.body.innerHTML.toLowerCase().includes('verificação de acesso'))
                                return true;
                        } catch(e) {}
                    }
                    return false;
                })()
                """)
                if not modal_ainda:
                    log.info(f"Modal fechou automaticamente ({tentativa + 1}s)")
                    break
            else:
                log.warning("Modal ainda aberto apos 15s — captcha pode ter sido rejeitado")

            await tab.sleep(1)
            return True

        except Exception as e:
            log.error(f"Erro ao resolver modal de verificacao: {e}")
            return False

    async def _injetar_token_embed(self, tab, token):
        """Injeta token de captcha no formulario dentro do embed iframe."""
        await tab.evaluate(f"""
        (() => {{
            {_JS_EMBED_DOC}
            const [doc, win] = __embedDoc();
            if (!doc) return;
            doc.querySelectorAll("textarea[name='g-recaptcha-response']").forEach(el => {{
                el.style.display = 'block';
                el.value = '{token}';
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }});
        }})()
        """)


async def consultar_processo_pinhais(processo):
    robo = RobotAtendeNetV2()
    return await robo.consultar_processo(processo)
