from playwright.async_api import async_playwright
import re
import asyncio

from services.captcha_api_client import (
    enviar_captcha_para_api,
    consultar_resultado_captcha_api,
)


# Sitekey do badge/invisible captcha usado no formulário de consulta.
SITEKEY_PADRAO_PINHAIS = "6LenD30sAAAAADTdG6GJYoAxOIZy9SEYg1VSY24j"

# Sitekey do captcha VISÍVEL do modal "Verificação de acesso".
# Confirmada via URL do anchor iframe: api2/anchor?k=<este_valor>
# É DIFERENTE do badge acima — [data-sitekey] no DOM retorna o badge
# (errado), por isso usamos o URL do iframe filho como fonte primária.
SITEKEY_MODAL_PINHAIS = "6Le9DX0sAAAAAM10_leN11PLggPbvzjQKcpm3VFW"


# =====================================================
# ✅ RESOLVER CAPTCHA (2CAPTCHA)
# =====================================================
async def resolver_captcha(site_key, url):
    print("🧠 Enviando captcha para 2captcha...")

    resultado_envio = await enviar_captcha_para_api(
        processo={},
        sitekey=site_key,
        url=url,
    )

    if resultado_envio.get("status") != "ENVIADO_API":
        raise Exception(f"❌ Erro ao enviar captcha: {resultado_envio}")

    protocolo = resultado_envio.get("protocolo_api")
    print(f"📌 Protocolo: {protocolo}")

    resultado = await consultar_resultado_captcha_api(protocolo)

    if resultado.get("status") != "RESOLVIDO":
        raise Exception(f"❌ Falha ao resolver captcha: {resultado}")

    print("✅ Captcha resolvido!")
    return resultado.get("resposta")


async def capturar_sitekey(frame_ou_page):
    """
    Procura a sitekey do reCAPTCHA no DOM (via [data-sitekey] ou pela URL
    do iframe do Google). Retorna None se não encontrar nada — quem chama
    decide se aplica um fallback.
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
    eventos input/change para que frameworks JS detectem a mudança.
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


# =====================================================
# ✅ ROBÔ PRINCIPAL
# =====================================================
class RobotAtendeNetV2:

    async def consultar_processo(self, processo):

        # Usa a URL cadastrada no processo; fallback para Pinhais se não houver
        url = (
            processo.get("acesso")
            or "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"
        )

        municipio = processo.get("municipio") or processo.get("nome_orgao") or "AtendNet"
        print(f"\n=== ROBÔ ATENDENET V2 — {municipio.upper()} ===")

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url)

            # =====================================================
            # ✅ 1. COOKIES
            # =====================================================
            try:
                await page.click("button:has-text('Aceitar')", timeout=5000)
                print("✅ Cookies aceitos")
            except Exception as e:
                print(f"ℹ️ Banner de cookies não apareceu ou já estava fechado: {e}")

            # ALTERAÇÃO: o modal "Verificação de acesso" aparece logo ao
            # carregar a página (confirmado em testes manuais), antes do
            # formulário sequer existir no DOM. Damos um tempo curto para
            # ele aparecer e tentamos resolvê-lo aqui. Se ele não aparecer
            # (site pode não exibir sempre, dependendo de IP/comportamento),
            # seguimos o fluxo normalmente.
            await page.wait_for_timeout(3000)
            await self._resolver_modal_verificacao_acesso(page, url)

            await page.wait_for_timeout(1000)

            # =====================================================
            # ✅ 2. ACESSAR IFRAME
            # =====================================================
            # Estrutura real da página Pinhais após o modal fechar:
            #   main page
            #   └── embed frame (frame_modal): mini-portal IPM com header/footer
            #       └── embed iframe aninhado: formulário de consulta ← queremos este
            #
            # O embed frame externo agora tem o shell do serviço (header, breadcrumbs
            # e um <iframe src="embed/data/...">). O formulário com os inputs de
            # processo está dentro desse iframe filho.
            # Buscamos o frame com "embed/data" na URL que tenha inputs reais.

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
                print("⏳ aguardando iframe do formulário carregar...")
                await page.wait_for_timeout(2000)

            if not frame:
                raise Exception("❌ Iframe com formulário não encontrado")

            print("✅ Iframe encontrado")

            inputs = frame.locator(selector)
            count = await inputs.count()

            if count < 2:
                raise Exception(f"❌ Inputs do formulário não carregaram. Total: {count}")

            inputs = frame.locator(selector)

            # =====================================================
            # ✅ 3. PREPARAR DADOS
            # =====================================================
            numero = processo.get("numero_processo")
            codigo = processo.get("codigo") or ""
            ano = processo.get("exercicio") or ""

            numero_base = re.sub(r"[^0-9]", "", str(numero))

            print(f"Número: {numero_base}")
            print(f"Ano: {ano}")
            print(f"Código: {codigo}")

            # =====================================================
            # ✅ 4. PREENCHER FORMULÁRIO
            # =====================================================
            inputs = frame.locator(selector)

            count = await inputs.count()

            if count < 2:
                raise Exception(f"❌ Inputs não encontrados. Total: {count}")

            numero_input = inputs.nth(0)
            codigo_input = inputs.nth(count - 1)

            await numero_input.fill(numero_base)

            if count > 2:
                await inputs.nth(1).fill(str(ano))

            await codigo_input.fill(codigo)

            print("✅ Formulário preenchido")

            # ✅ dispara evento usuário
            await numero_input.click()
            await page.mouse.click(0, 0)

            await page.wait_for_timeout(5000)

            # =====================================================
            # ✅ 5. CAPTURAR SITEKEY (captcha do formulário)
            # =====================================================
            site_key = await capturar_sitekey(frame)

            if not site_key:
                raise Exception("❌ Sitekey não encontrada")

            print(f"✅ Sitekey: {site_key}")

            # =====================================================
            # ✅ 6. CAPTCHA (do formulário)
            # =====================================================
            token = await resolver_captcha(site_key, url)

            await injetar_token_recaptcha(frame, token)

            print("✅ Captcha inserido")

            await page.wait_for_timeout(2000)

            # =====================================================
            # ✅ 7. SUBMIT
            # =====================================================
            await frame.locator("button[name='confirmar']").click(force=True)

            print("✅ Consulta enviada")

            # =====================================================
            # ✅ 8. RESULTADO
            # =====================================================
            await page.wait_for_timeout(6000)

            try:
                aba_historico = frame.locator("text=Histórico").first
                if await aba_historico.count() > 0:
                    await aba_historico.click()
                    await page.wait_for_timeout(1500)
                    print("✅ Aba 'Histórico' selecionada")
            except Exception as e:
                print(f"ℹ️ Aba 'Histórico' não encontrada, seguindo com a tabela padrão: {e}")

            movimentacoes = []

            rows = frame.locator("table tr")
            total = await rows.count()

            for i in range(total):
                texto = (await rows.nth(i).inner_text()).strip()
                if texto and "Data" not in texto:
                    movimentacoes.append(texto)

            print(f"✅ Movimentações: {len(movimentacoes)}")

            # =====================================================
            # ✅ 9. STATUS
            # =====================================================
            texto_total = " ".join(movimentacoes).lower()

            if "deferido" in texto_total:
                status = "Finalizado"
            elif "indeferido" in texto_total:
                status = "Indeferido"
            elif "não encontrado" in texto_total:
                await browser.close()
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO"
                }
            else:
                status = "Em análise"

            print(f"📊 Status: {status}")

            await browser.close()

            return {
                "status": "OK",
                "status_processo": status,
                "movimentacoes": movimentacoes,
            }

    # =====================================================
    # ✅ RESOLVER MODAL "VERIFICAÇÃO DE ACESSO"
    # =====================================================
    async def _resolver_modal_verificacao_acesso(self, page, url):
        """
        Detecta e resolve o modal "Verificação de acesso".
        Retorna True se o modal foi detectado e o captcha foi aceito,
        False se o modal não apareceu.
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
                print("ℹ️ Modal 'Verificação de acesso' não apareceu — seguindo fluxo normal.")
                return False

            print(f"🔒 Modal detectado no frame: {frame_modal.url}")

            # CORREÇÃO: filtrar por size!=invisible para pegar o captcha
            # visível do modal, ignorando o badge invisível (mesmo frame,
            # dois anchor iframes distintos com sitekeys diferentes).
            site_key = None
            for child in frame_modal.child_frames:
                if "api2/anchor" in child.url and "size=invisible" not in child.url:
                    m = re.search(r"[?&]k=([^&]+)", child.url)
                    if m:
                        site_key = m.group(1)
                        print(f"✅ Sitekey do modal (anchor normal): {site_key}")
                        break

            if not site_key:
                for f in page.frames:
                    if "api2/anchor" in f.url and "size=invisible" not in f.url:
                        m = re.search(r"[?&]k=([^&]+)", f.url)
                        if m:
                            site_key = m.group(1)
                            print(f"✅ Sitekey do modal (page frames, normal): {site_key}")
                            break

            if not site_key:
                print(f"⚠️ Anchor normal não detectado — usando SITEKEY_MODAL_PINHAIS.")
                site_key = SITEKEY_MODAL_PINHAIS

            token = await resolver_captcha(site_key, url)

            await injetar_token_recaptcha(frame_modal, token)
            print("✅ Token do modal injetado")

            # Disparo controlado — apenas UMA chamada para evitar race condition.
            # Chamadas duplicadas enviam o mesmo token duas vezes: o 2º e 3º
            # chegam com token já usado → servidor retorna 500 → IPM re-renderiza
            # o modal por erro, mesmo que o 1º tenha retornado 200.
            #
            # Estratégia:
            # 1. Patchar grecaptcha.getResponse → retorna nosso token
            # 2. Checar __user_access_config (precisa estar setado para o
            #    serviço carregar após o modal fechar)
            # 3. Chamar onValidaCaptchaAcessoSistema UMA VEZ (sem cfg-L2)
            try:
                cb_result = await frame_modal.evaluate(
                    """
                    (token) => {
                        const results = [];

                        // 1. Patchar grecaptcha.getResponse
                        try {
                            if (window.grecaptcha && typeof window.grecaptcha.getResponse === 'function') {
                                window.grecaptcha.getResponse = function() { return token; };
                                results.push('getResponse_patchado');
                            }
                            if (window.grecaptcha && window.grecaptcha.enterprise &&
                                typeof window.grecaptcha.enterprise.getResponse === 'function') {
                                window.grecaptcha.enterprise.getResponse = function() { return token; };
                                results.push('enterprise_patchado');
                            }
                        } catch(e) { results.push('err_patch:' + e.message); }

                        // 2. Diagnóstico: __user_access_config
                        try {
                            const cfg = window.__user_access_config;
                            results.push('uac:' + (cfg ? JSON.stringify({
                                rotina: cfg.rotina, acao: cfg.acao,
                                processo: cfg.processo
                            }) : 'undefined'));
                        } catch(e) { results.push('err_uac:' + e.message); }

                        // 3. Uma única chamada a onValidaCaptchaAcessoSistema
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
                                results.push('fn_nao_encontrada:tela=' + !!tela + ',rec=' + !!rec);
                            }
                        } catch(e) { results.push('err_call:' + e.message); }

                        return results.join(' | ');
                    }
                    """,
                    token,
                )
                print(f"🔧 Callback: {cb_result}")
            except Exception as e:
                print(f"ℹ️ Não foi possível disparar callback: {e}")

            # Aguarda o modal fechar sozinho (sinal de que o AJAX foi aceito).
            # Não clicamos em "Fechar" — esse botão descarta o modal sem
            # acionar onSubmitCompleteAcessoCaptcha, então o serviço nunca carrega.
            modal_fechou = False
            for tentativa in range(12):
                await page.wait_for_timeout(1000)
                try:
                    html_agora = await frame_modal.content()
                    if "verificação de acesso" not in html_agora.lower():
                        modal_fechou = True
                        print(f"✅ Modal fechou automaticamente ({tentativa + 1}s)")
                        break
                except Exception:
                    modal_fechou = True
                    print(f"✅ Frame do modal desapareceu ({tentativa + 1}s)")
                    break

            if not modal_fechou:
                print("⚠️ Modal ainda aberto após 12s — captcha pode ter sido rejeitado pelo servidor.")

            await page.wait_for_timeout(1000)
            return True

        except Exception as e:
            print(f"⚠️ Erro ao tentar resolver o modal de verificação de acesso: {e}")
            return False


# =====================================================
# ✅ ENTRYPOINT
# =====================================================
async def consultar_processo_pinhais(processo):
    robo = RobotAtendeNetV2()
    return await robo.consultar_processo(processo)