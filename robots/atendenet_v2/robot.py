from playwright.async_api import async_playwright
import re
import asyncio
from pathlib import Path

from services.captcha_api_client import (
    enviar_captcha_para_api,
    consultar_resultado_captcha_api,
)
from utils.logger import get_logger

# Limita consultas simultaneas ao mesmo servidor para evitar bloqueio por anti-bot.
# pinhais.atende.net e araucaria.atende.net sao o mesmo backend IPM.
_semaphore = asyncio.Semaphore(2)

# Sessao salva pelo setup_session_pinhais.py (cookies de usuario autenticado).
# Sem esse arquivo o formulario de consulta exige login e nao carrega.
SESSION_FILE = Path(__file__).parent / "session_state.json"

_UA_CHROME136 = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)

log = get_logger("atendenet")

# Sitekey do badge/invisible captcha usado no formulário de consulta.
SITEKEY_PADRAO_PINHAIS = "6LenD30sAAAAADTdG6GJYoAxOIZy9SEYg1VSY24j"

# Sitekey do captcha visivel do modal "Verificacao de acesso".
# Confirmada via URL do anchor iframe: api2/anchor?k=<este_valor>
# E diferente do badge acima — [data-sitekey] no DOM retorna o badge
# (errado), por isso usamos o URL do iframe filho como fonte primaria.
SITEKEY_MODAL_PINHAIS = "6Le9DX0sAAAAAM10_leN11PLggPbvzjQKcpm3VFW"


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


async def capturar_sitekey(frame_ou_page):
    """
    Procura a sitekey do reCAPTCHA no DOM (via [data-sitekey] ou pela URL
    do iframe do Google). Retorna None se nao encontrar nada.
    """
    return await frame_ou_page.evaluate("""
        () => {
            const el = document.querySelector('[data-sitekey]');
            if (el) return el.getAttribute('data-sitekey');

            const iframe = document.querySelector("iframe[src*='recaptcha']");
            if (iframe) {
                const match = iframe.src.match(/k=([^&]+)/);
                return match ? match[1] : null;
            }

            return null;
        }
    """)


async def injetar_token_recaptcha(frame_ou_page, token):
    """
    Injeta o token em todas as textareas g-recaptcha-response e dispara
    eventos input/change para que frameworks JS detectem a mudanca.
    """
    await frame_ou_page.evaluate(
        """
        (token) => {
            document.querySelectorAll("textarea[name='g-recaptcha-response']").forEach(el => {
                el.style.display = "block";
                el.value = token;
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }
        """,
        token,
    )


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

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)

            ctx_kwargs = {"user_agent": _UA_CHROME136}
            if SESSION_FILE.exists():
                ctx_kwargs["storage_state"] = str(SESSION_FILE)
                log.info("Sessao autenticada carregada (session_state.json)")
            else:
                log.warning(
                    "session_state.json nao encontrado — "
                    "execute robots/atendenet_v2/setup_session_pinhais.py para criar a sessao"
                )

            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()

            await page.goto(url)
            await page.wait_for_timeout(3000)

            # 1a. ALERTA DE CAPTCHA (IP bloqueado por atividade incomum)
            # Aparece quando o servidor detecta multiplas requisicoes automatizadas.
            # Precisa ser dispensado antes de qualquer outro clique.
            try:
                await page.click("button:has-text('Ok')", timeout=3000, force=True)
                log.info("Alerta de captcha dispensado")
                await page.wait_for_timeout(1000)
            except Exception:
                log.debug("Alerta de captcha nao apareceu")

            # 1b. NAVEGADOR INCOMPATIVEL — clicado ANTES dos cookies.
            # O banner de cookies pode desmontar o bloqueador do DOM ao ser aceito,
            # o que faria o botao "Continuar" desaparecer. Por isso clicar aqui primeiro.
            # Clicar "Continuar" faz um POST que autoriza a sessao no servidor,
            # liberando o iframe do formulario. force=True ignora overlays.
            try:
                await page.click(
                    "button:has-text('Continuar o acesso com meu Navegador')",
                    timeout=8000,
                    force=True,
                )
                log.info("Aviso de navegador incompativel aceito")
                await page.wait_for_timeout(5000)
            except Exception:
                log.debug("Aviso de navegador incompativel nao apareceu")

            # 1c. COOKIES
            try:
                await page.click("button:has-text('Aceitar')", timeout=5000, force=True)
                log.info("Banner de cookies aceito")
                await page.wait_for_timeout(1500)
            except Exception:
                log.debug("Banner de cookies nao apareceu ou ja estava fechado")

            # Modal de verificacao de acesso aparece logo ao carregar a pagina,
            # antes do formulario existir no DOM.
            await page.wait_for_timeout(3000)
            await self._resolver_modal_verificacao_acesso(page, url)

            await page.wait_for_timeout(1000)

            # 2. ACESSAR IFRAME
            # O formulario esta num iframe filho do embed frame (nao no embed
            # frame em si). Buscamos o frame com "embed/data" na URL que tenha
            # inputs reais do formulario.
            selector = "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='checkbox']):not([type='radio']):not([id*='goog']):not([name='g-recaptcha-response'])"

            await page.wait_for_selector("iframe", timeout=15000)

            frame = None
            for _ in range(10):
                for f in page.frames:
                    if "embed/data" not in f.url:
                        continue
                    try:
                        cnt = await f.locator(selector).count()
                        if cnt >= 1:
                            frame = f
                            break
                    except Exception:
                        pass
                if frame:
                    break
                log.debug("Aguardando iframe do formulario carregar...")
                await page.wait_for_timeout(2000)

            if not frame:
                # Verifica se iframe existe mas mostra modal de login (sessao expirada)
                for f in page.frames:
                    if "embed/data" in f.url:
                        try:
                            html_f = await f.content()
                            if "acessar_conta" in html_f or "cidadao/acesso" in html_f:
                                raise Exception(
                                    "SESSAO_EXPIRADA: execute "
                                    "robots/atendenet_v2/setup_session_pinhais.py"
                                )
                        except Exception as exc:
                            if "SESSAO_EXPIRADA" in str(exc):
                                raise
                        break
                raise Exception("Iframe com formulario nao encontrado")

            log.info("Iframe do formulario localizado")

            # 3. PREPARAR DADOS
            numero = processo.get("numero_processo")
            codigo = processo.get("codigo") or ""
            ano = processo.get("exercicio") or ""

            numero_base = re.sub(r"[^0-9]", "", str(numero))

            log.info(f"Numero: {numero_base} | Ano: {ano} | Codigo: {codigo}")

            # 4. DETECTAR TIPO DE FORMULARIO E PREENCHER
            # Formulário autenticado: usa filtros de busca com aria-description.
            # Formulário anônimo (legado): usa preenchimento posicional.
            SEL_CAMPO_NUMERO = "input[name='campo01'][aria-description='campo numérico']"
            SEL_CAMPO_ANO = "input[name='campo01'][aria-description='campo ano']"

            campo_numero = frame.locator(SEL_CAMPO_NUMERO).first
            is_form_autenticado = await campo_numero.count() > 0

            if is_form_autenticado:
                log.info("Formulario autenticado detectado (filtros de busca)")

                await campo_numero.fill(numero_base, force=True)
                log.info(f"Filtro Numero preenchido: {numero_base}")

                campo_ano = frame.locator(SEL_CAMPO_ANO).first
                if await campo_ano.count() > 0 and ano:
                    await campo_ano.fill(str(ano), force=True)
                    log.info(f"Filtro Ano preenchido: {ano}")

            else:
                log.info("Formulario anonimo detectado (preenchimento posicional)")
                selector_fill = (
                    "input:visible"
                    ":not([type='hidden']):not([type='submit']):not([type='button'])"
                    ":not([type='checkbox']):not([type='radio'])"
                    ":not([id*='goog']):not([name='g-recaptcha-response'])"
                )
                inputs = frame.locator(selector_fill)
                count = await inputs.count()

                if count < 2:
                    raise Exception(f"Inputs visiveis nao carregaram. Total: {count}")

                numero_input = inputs.nth(0)
                codigo_input = inputs.nth(count - 1)

                await numero_input.fill(numero_base)
                if count > 2:
                    await inputs.nth(1).fill(str(ano))
                await codigo_input.fill(codigo)

            log.info("Formulario preenchido")
            await page.mouse.click(0, 0)
            await page.wait_for_timeout(2000)

            # 5. CAPTCHA (apenas no formulario anonimo)
            if not is_form_autenticado:
                site_key = await capturar_sitekey(frame)
                if not site_key:
                    raise Exception("Sitekey do formulario nao encontrada")
                log.info(f"Sitekey do formulario: {site_key}")
                token = await resolver_captcha(site_key, url)
                await injetar_token_recaptcha(frame, token)
                log.info("Token do formulario injetado")
                await page.wait_for_timeout(2000)
            else:
                site_key = await capturar_sitekey(frame)
                if site_key:
                    log.info(f"Captcha detectado no formulario autenticado: {site_key}")
                    token = await resolver_captcha(site_key, url)
                    await injetar_token_recaptcha(frame, token)
                    await page.wait_for_timeout(2000)
                else:
                    log.info("Sem captcha no formulario autenticado")

            # 6. SUBMIT
            # Autenticado: <input type='button' name='consultar'> (IPM AtendNet filtros).
            # Anonimo: <button name='confirmar'>.
            submit_feito = False
            btn_selectors = (
                [
                    "input[name='consultar']",
                    "input[type='button'][name='consultar']",
                    "button[type='submit']",
                ]
                if is_form_autenticado
                else [
                    "button[name='confirmar']",
                    "input[name='confirmar']",
                    "button[type='submit']",
                    "input[type='submit']",
                ]
            )
            for btn_sel in btn_selectors:
                try:
                    btn = frame.locator(btn_sel).first
                    if await btn.count() > 0:
                        await btn.click(force=True)
                        submit_feito = True
                        log.info(f"Consulta enviada via: {btn_sel}")
                        break
                except Exception:
                    pass

            if not submit_feito:
                raise Exception("Botao de submit nao encontrado no formulario")

            await page.wait_for_timeout(5000)

            # 7. SELECIONAR PROCESSO NA LISTA (formulario autenticado)
            # Após "Consultar", aparece lista de resultados. Clicar no processo correto.
            if is_form_autenticado:
                selecionado = False
                try:
                    result = frame.locator(f"text={numero_base}").first
                    if await result.count() > 0:
                        await result.click(force=True)
                        selecionado = True
                        log.info(f"Processo {numero_base} selecionado na lista")
                        await page.wait_for_timeout(3000)
                except Exception as e:
                    log.debug(f"Selecao por texto falhou: {e}")

                if not selecionado:
                    try:
                        row = frame.locator(f"tr:has-text('{numero_base}')").first
                        if await row.count() > 0:
                            await row.click(force=True)
                            log.info(f"Linha com {numero_base} clicada")
                            await page.wait_for_timeout(3000)
                    except Exception as e:
                        log.debug(f"Selecao por tr falhou: {e}")

            # 8. RESULTADO — extrai da aba "Linha do Tempo"
            # Abordagem: captura o texto completo da aba e divide por
            # "Data do Movimento:" — garante EXATAMENTE 1 registro por card,
            # independente da estrutura HTML interna do IPM.
            await page.wait_for_timeout(6000)

            movimentacoes = []

            try:
                aba_lt = frame.locator("text=Linha do Tempo").first
                if await aba_lt.count() > 0:
                    await aba_lt.click()
                    await page.wait_for_timeout(2000)
                    log.info("Aba Linha do Tempo selecionada")

                    texto_aba = await frame.inner_text("body")

                    # Divide pelo marcador "Data do Movimento:" que aparece
                    # UMA vez por card — produz exatamente 1 secao por movimento
                    marcador = "Data do Movimento:"
                    secoes = texto_aba.split(marcador)

                    for secao in secoes[1:]:          # ignora o que vem antes do primeiro card
                        secao = secao.strip()
                        if not secao:
                            continue
                        # Primeira linha da secao = "DD/MM/YYYY HH:MM:SS"
                        primeira_linha = secao.split("\n")[0].strip()
                        if not re.match(r"\d{2}/\d{2}/\d{4}", primeira_linha):
                            continue
                        # Monta o texto limpo do card (max 600 chars)
                        texto_card = (marcador + " " + secao)[:600].strip()
                        movimentacoes.append(texto_card)

                    log.info(f"Linha do Tempo: {len(movimentacoes)} movimento(s) extraido(s)")
            except Exception as e:
                log.debug(f"Aba Linha do Tempo nao disponivel: {e}")

            # Fallback para tabela do Historico
            if not movimentacoes:
                try:
                    aba_hist = frame.locator("text=Historico").first
                    if await aba_hist.count() > 0:
                        await aba_hist.click()
                        await page.wait_for_timeout(1500)
                        log.info("Aba Historico selecionada (fallback)")
                except Exception:
                    pass

                rows = frame.locator("table tr")
                total = await rows.count()
                for i in range(total):
                    texto = (await rows.nth(i).inner_text()).strip()
                    if texto and re.search(r"\d{2}/\d{2}/\d{4}", texto):
                        movimentacoes.append(texto)
                log.info(f"Historico (fallback): {len(movimentacoes)} linhas com data")

            log.info(f"Total movimentacoes extraidas: {len(movimentacoes)}")

            # 9. STATUS — analisa o conteudo extraido
            texto_total = " ".join(movimentacoes).lower()

            if "encerrado" in texto_total or "deferido" in texto_total:
                status = "Finalizado"
            elif "indeferido" in texto_total:
                status = "Indeferido"
            elif "nao encontrado" in texto_total or "não encontrado" in texto_total:
                await browser.close()
                return {"status": "PROCESSO_NAO_ENCONTRADO"}
            else:
                status = "Em analise"

            log.info(f"Status: {status}")

            await browser.close()

            return {
                "status": "OK",
                "status_processo": status,
                "movimentacoes": movimentacoes,
            }

    async def _resolver_modal_verificacao_acesso(self, page, url):
        """
        Detecta e resolve o modal "Verificacao de acesso".
        Suporta reCAPTCHA v2 (Google) e Cloudflare Turnstile.
        Retorna True se o modal foi detectado e o captcha foi aceito,
        False se o modal nao apareceu.
        """
        try:
            frame_modal = None
            for f in page.frames:
                try:
                    html_frame = await f.content()
                except Exception:
                    continue
                if "verificação de acesso" in html_frame.lower():
                    frame_modal = f
                    break

            if not frame_modal:
                log.debug("Modal 'Verificacao de acesso' nao apareceu — seguindo fluxo normal")
                return False

            log.info(f"Modal de verificacao detectado no frame: {frame_modal.url}")

            # ── Detecta tipo de captcha ──────────────────────────────────────
            # Prioridade: Cloudflare Turnstile (mudanca do site em ~01/07/2026)
            # Fallback: reCAPTCHA v2 (comportamento anterior)

            captcha_method = "userrecaptcha"
            site_key = None

            # 1. Procura frame do Cloudflare Turnstile em todos os frames da pagina
            for f in page.frames:
                if "challenges.cloudflare.com" in f.url and "turnstile" in f.url:
                    m = re.search(r"/([0-9a-zA-Z_-]{20,})/", f.url)
                    if m:
                        site_key = m.group(1)
                        captcha_method = "turnstile"
                        log.info(f"Cloudflare Turnstile detectado — sitekey: {site_key}")
                        break

            # 2. Fallback: reCAPTCHA v2 (anchor iframe do Google)
            if not site_key:
                for child in frame_modal.child_frames:
                    if "api2/anchor" in child.url and "size=invisible" not in child.url:
                        m = re.search(r"[?&]k=([^&]+)", child.url)
                        if m:
                            site_key = m.group(1)
                            log.info(f"reCAPTCHA v2 detectado (child frame) — sitekey: {site_key}")
                            break

            if not site_key:
                for f in page.frames:
                    if "api2/anchor" in f.url and "size=invisible" not in f.url:
                        m = re.search(r"[?&]k=([^&]+)", f.url)
                        if m:
                            site_key = m.group(1)
                            log.info(f"reCAPTCHA v2 detectado (page frames) — sitekey: {site_key}")
                            break

            if not site_key:
                log.warning("Tipo de captcha nao detectado — usando SITEKEY_MODAL_PINHAIS como fallback")
                site_key = SITEKEY_MODAL_PINHAIS

            token = await resolver_captcha(site_key, url, method=captcha_method)

            # ── Injeta token conforme o tipo de captcha ──────────────────────
            if captcha_method == "turnstile":
                await self._injetar_token_turnstile(frame_modal, token)
            else:
                await injetar_token_recaptcha(frame_modal, token)
                log.info("Token reCAPTCHA do modal injetado")

                # Disparo do callback IPM para reCAPTCHA (comportamento anterior)
                try:
                    cb_result = await frame_modal.evaluate(
                        """
                        (token) => {
                            const results = [];
                            try {
                                if (window.grecaptcha && typeof window.grecaptcha.getResponse === 'function') {
                                    window.grecaptcha.getResponse = function() { return token; };
                                    results.push('getResponse_patchado');
                                }
                            } catch(e) { results.push('err_patch:' + e.message); }
                            try {
                                const comp = window.componente;
                                const tela = comp && comp["1211"] && comp["1211"]["102"] &&
                                             comp["1211"]["102"]["1"] &&
                                             comp["1211"]["102"]["1"]["tela_acesso_captcha"] &&
                                             comp["1211"]["102"]["1"]["tela_acesso_captcha"]["tela_acesso_captcha"];
                                const rec  = comp && comp["1211"] && comp["1211"]["102"] &&
                                             comp["1211"]["102"]["1"] &&
                                             comp["1211"]["102"]["1"]["tela_acesso_captcha"] &&
                                             comp["1211"]["102"]["1"]["tela_acesso_captcha"]["recaptcha"];
                                if (tela && rec && typeof window.onValidaCaptchaAcessoSistema === 'function') {
                                    window.onValidaCaptchaAcessoSistema.apply(rec, [tela]);
                                    results.push('onValidaCaptcha_ok');
                                } else {
                                    results.push('fn_nao_encontrada');
                                }
                            } catch(e) { results.push('err_call:' + e.message); }
                            return results.join(' | ');
                        }
                        """,
                        token,
                    )
                    log.debug(f"Callback reCAPTCHA modal: {cb_result}")
                except Exception as e:
                    log.warning(f"Nao foi possivel disparar callback reCAPTCHA do modal: {e}")

            # Aguarda o modal fechar sozinho apos validacao AJAX bem-sucedida.
            modal_fechou = False
            for tentativa in range(15):
                await page.wait_for_timeout(1000)
                try:
                    html_agora = await frame_modal.content()
                    if "verificação de acesso" not in html_agora.lower():
                        modal_fechou = True
                        log.info(f"Modal fechou automaticamente ({tentativa + 1}s)")
                        break
                except Exception:
                    modal_fechou = True
                    log.info(f"Frame do modal desapareceu ({tentativa + 1}s)")
                    break

            if not modal_fechou:
                log.warning("Modal ainda aberto apos 15s — captcha pode ter sido rejeitado pelo servidor")

            await page.wait_for_timeout(1000)
            return True

        except Exception as e:
            log.error(f"Erro ao resolver modal de verificacao: {e}")
            return False

    async def _injetar_token_turnstile(self, frame_modal, token):
        """
        Injeta token do Cloudflare Turnstile e dispara callbacks do IPM.
        O Turnstile usa cf-turnstile-response (diferente do g-recaptcha-response).
        """
        log.info("Injetando token Turnstile no modal...")

        try:
            cb_result = await frame_modal.evaluate(
                """
                (token) => {
                    const results = [];

                    // Injeta no campo oculto do Turnstile
                    document.querySelectorAll('[name="cf-turnstile-response"]').forEach(el => {
                        el.value = token;
                        results.push('cf-turnstile-response injetado');
                    });

                    // Tenta disparar callback declarado via data-callback
                    document.querySelectorAll('[data-callback]').forEach(el => {
                        const cb = el.getAttribute('data-callback');
                        if (cb && typeof window[cb] === 'function') {
                            try { window[cb](token); results.push('data-callback:' + cb); }
                            catch(e) { results.push('err_cb:' + e.message); }
                        }
                    });

                    // Tenta callback IPM especifico para Turnstile
                    try {
                        const comp = window.componente;
                        const tela = comp && comp["1211"] && comp["1211"]["102"] &&
                                     comp["1211"]["102"]["1"] &&
                                     comp["1211"]["102"]["1"]["tela_acesso_captcha"] &&
                                     comp["1211"]["102"]["1"]["tela_acesso_captcha"]["tela_acesso_captcha"];
                        const rec  = comp && comp["1211"] && comp["1211"]["102"] &&
                                     comp["1211"]["102"]["1"] &&
                                     comp["1211"]["102"]["1"]["tela_acesso_captcha"] &&
                                     comp["1211"]["102"]["1"]["tela_acesso_captcha"]["recaptcha"];
                        if (tela && rec && typeof window.onValidaCaptchaAcessoSistema === 'function') {
                            window.onValidaCaptchaAcessoSistema.apply(rec, [tela]);
                            results.push('onValidaCaptcha_ok');
                        } else {
                            results.push('ipm_fn_nao_encontrada');
                        }
                    } catch(e) { results.push('err_ipm:' + e.message); }

                    return results.join(' | ');
                }
                """,
                token,
            )
            log.info(f"Injecao Turnstile: {cb_result}")
        except Exception as e:
            log.warning(f"Erro ao injetar token Turnstile: {e}")


async def consultar_processo_pinhais(processo):
    robo = RobotAtendeNetV2()
    return await robo.consultar_processo(processo)