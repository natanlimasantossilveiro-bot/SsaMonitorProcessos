from playwright.async_api import async_playwright
import re
import asyncio

from services.captcha_api_client import (
    enviar_captcha_para_api,
    consultar_resultado_captcha_api,
)


# ALTERAÇÃO: sitekey conhecida do domínio pinhais.atende.net (vista no
# captcha do formulário). Usada como fallback caso a sitekey não seja
# encontrada automaticamente no DOM do modal de "Verificação de acesso".
# Se o site usar uma sitekey diferente para esse modal específico, o
# fallback automático (busca por [data-sitekey] / iframe[src*=recaptcha])
# tem prioridade e este valor só é usado se a busca automática falhar.
SITEKEY_PADRAO_PINHAIS = "6LenD30sAAAAADTdG6GJYoAxOIZy9SEYg1VSY24j"


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
    Injeta o token do reCAPTCHA em TODAS as textareas com
    name="g-recaptcha-response" presentes no contexto (frame ou page).
    Usa querySelectorAll porque o ID real costuma ter um sufixo numérico
    (ex: g-recaptcha-response-100000) que getElementById("g-recaptcha-response")
    sozinho não encontra.
    """
    await frame_ou_page.evaluate(
        """
        (token) => {
            const areas = document.querySelectorAll("textarea[name='g-recaptcha-response']");
            areas.forEach(el => {
                el.style.display = "block";
                el.value = token;
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

        print("\n=== ROBÔ PINHAIS (ATENDENET V2) ===")

        url = "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"

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
            await page.wait_for_selector("iframe", timeout=15000)

            frame = None
            for f in page.frames:
                if "pinhais.atende.net" in f.url:
                    frame = f
                    break

            if not frame:
                raise Exception("❌ Iframe não encontrado")

            print("✅ Iframe encontrado")

            # ✅ só inputs que NÃO são do Google
            selector = "input[type='text']:not([id*='goog'])"

            # ✅ aguarda QUALQUER input aparecer primeiro (mesmo oculto)
            await frame.wait_for_selector("input", timeout=15000)

            # ✅ espera um tempo extra para renderização JS
            await page.wait_for_timeout(3000)

            # ✅ AGORA pega os inputs reais
            inputs = frame.locator(selector)

            count = await inputs.count()

            if count < 2:
                # fallback — aguarda mais
                await page.wait_for_timeout(3000)
                count = await inputs.count()

            for _ in range(5):

                inputs = frame.locator(selector)
                count = await inputs.count()

                if count >= 2:
                    break

                print("⏳ aguardando inputs reais...")
                await page.wait_for_timeout(2000)

            if count < 2:
                # ALTERAÇÃO: se ainda não carregou, pode ser que um SEGUNDO
                # modal de verificação tenha aparecido nesse meio tempo
                # (o relato indica que ele pode pedir desafio de imagem,
                # o que demora mais). Tentamos resolver de novo antes de
                # desistir, em vez de falhar direto.
                print("⚠️ Inputs não carregaram — verificando se outro modal de captcha apareceu...")
                resolveu_de_novo = await self._resolver_modal_verificacao_acesso(page, url)

                if resolveu_de_novo:
                    await page.wait_for_timeout(3000)
                    inputs = frame.locator(selector)
                    count = await inputs.count()

            if count < 2:
                raise Exception(f"❌ Inputs reais ainda não carregaram. Total: {count}")

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
    # ✅ NOVO: RESOLVER MODAL "VERIFICAÇÃO DE ACESSO"
    # =====================================================
    async def _resolver_modal_verificacao_acesso(self, page, url):
        """
        Detecta e resolve o modal "Verificação de acesso" que bloqueia o
        acesso ao serviço (aparece imediatamente ao carregar a página, em
        testes manuais). Esse modal tem seu PRÓPRIO captcha — separado do
        captcha que aparece depois, ao confirmar o formulário.

        Retorna True se o modal foi detectado e tratado, False se ele não
        apareceu (o que é esperado às vezes, dependendo do site).
        """
        try:
            # Texto visto no modal real: "Verificação de acesso"
            modal = page.locator("text=Verificação de acesso").first

            if await modal.count() == 0:
                print("ℹ️ Modal 'Verificação de acesso' não apareceu — seguindo fluxo normal.")
                return False

            print("🔒 Modal 'Verificação de acesso' detectado. Resolvendo captcha...")

            # ALTERAÇÃO: o modal pode estar na página principal ou em um
            # iframe aninhado dentro dela. Testamos os dois contextos para
            # achar o reCAPTCHA, em vez de assumir um dos dois de antemão.
            contexto_captcha = page
            for f in page.frames:
                try:
                    if await f.locator("iframe[src*='recaptcha'], [data-sitekey]").count() > 0:
                        contexto_captcha = f
                        break
                except Exception:
                    continue

            site_key = await capturar_sitekey(contexto_captcha)

            if not site_key:
                print(f"⚠️ Sitekey do modal não encontrada automaticamente — usando fallback padrão.")
                site_key = SITEKEY_PADRAO_PINHAIS

            print(f"✅ Sitekey do modal: {site_key}")

            token = await resolver_captcha(site_key, url)

            await injetar_token_recaptcha(contexto_captcha, token)

            print("✅ Token do modal injetado")

            await page.wait_for_timeout(1500)

            # Tenta clicar no checkbox "Não sou um robô" também, caso o
            # site exija o clique além do token (alguns fluxos checam os
            # dois: o valor da textarea E o estado "checked" do checkbox).
            try:
                checkbox_frame = None
                for f in page.frames:
                    if "api2/anchor" in f.url:
                        checkbox_frame = f
                        break

                if checkbox_frame:
                    await checkbox_frame.click("#recaptcha-anchor", timeout=3000)
                    print("✅ Checkbox 'Não sou um robô' clicado")
                    await page.wait_for_timeout(1500)
            except Exception as e:
                print(f"ℹ️ Não foi possível clicar no checkbox do modal (pode já estar resolvido via token): {e}")

            # Fecha o modal se ele tiver um botão "Fechar" e ainda estiver visível
            try:
                botao_fechar = page.locator("button:has-text('Fechar')").first
                if await botao_fechar.count() > 0 and await botao_fechar.is_visible():
                    await botao_fechar.click()
                    print("✅ Modal fechado manualmente")
            except Exception as e:
                print(f"ℹ️ Botão 'Fechar' do modal não encontrado/clicável: {e}")

            await page.wait_for_timeout(2000)
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
