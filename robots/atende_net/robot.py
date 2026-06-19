import os
from datetime import datetime

from playwright.async_api import async_playwright

from robots.base.robot_base import RobotBase

from robots.atende_net.parser import (
    montar_dados_consulta_atende_net,
    extrair_dados_resultado_atende_net,
)

from database.repositories import (
    atualizar_dados_processo,
    registrar_movimentacao,
    registrar_alteracoes
)

from services.comparador_service import comparar_processo
from services.captcha_service import resolver_recaptcha_direto


class RobotAtendeNet(RobotBase):

    async def consultar_processo(self, processo):
        dados_consulta = montar_dados_consulta_atende_net(processo)

        print("\n=== ROBÔ ATENDE.NET ===")
        print(f"Processo: {dados_consulta['numero']}")

        return await executar_consulta_atende_net(
            dados_consulta,
            processo
        )


async def executar_consulta_atende_net(dados_consulta, processo):

    caminho_evidencia = gerar_caminho_evidencia_resultado(processo)

    async with async_playwright() as p:

        browser = await p.chromium.launch_persistent_context(
            user_data_dir="chrome_profile",
            headless=False
        )

        page = await browser.new_page()

        await page.goto(dados_consulta["url"], wait_until="networkidle")

        await aceitar_cookies_se_existir(page)

        await page.wait_for_timeout(3000)

        print("\n=== CAPTCHA ===")

        try:
            sitekey = "6LenD30sAAAAADTdG6GJYoAxOIZy9SEYg1VSY24j"

            token = await resolver_recaptcha_direto(sitekey, page.url)

            # ✅ injeta token corretamente
            await page.evaluate(
                """
                (token) => {
                    let textarea = document.getElementById("g-recaptcha-response");

                    if (!textarea) {
                        textarea = document.createElement("textarea");
                        textarea.id = "g-recaptcha-response";
                        textarea.name = "g-recaptcha-response";
                        textarea.style.display = "none";
                        document.body.appendChild(textarea);
                    }

                    textarea.value = token;

                    if (!window.grecaptcha) {
                        console.log("grecaptcha não encontrado");
                        return;
                    }

                    if (window.grecaptcha.getResponse && window.grecaptcha.getResponse().length === 0) {
                        console.log("forçando resposta");
                    }
                }
                """,
                token
            )

            # 🔥 CHAMA CALLBACK DO RECAPTCHA
            await page.evaluate(
                """
                (token) => {
                    if (window.grecaptcha) {
                        try {
                            const clients = window.___grecaptcha_cfg.clients;

                            for (const key in clients) {
                                const client = clients[key];

                                for (const subKey in client) {
                                    const sub = client[subKey];

                                    if (sub && sub.callback) {
                                        sub.callback(token);
                                        console.log("callback chamado");
                                        return;
                                    }
                                }
                            }

                        } catch (e) {
                            console.log("erro ao chamar callback", e);
                        }
                    }
                }
                """,
                token
            )

            print("✅ Captcha resolvido e callback executado")

            await page.wait_for_timeout(5000)

        except Exception as e:
            print(f"⚠️ Falha no 2Captcha: {e}")
            input("Resolva manualmente...")

        print("\n=== PREENCHENDO FORMULÁRIO ===")

        await preencher_formulario_iframe(
            page,
            dados_consulta["numero"],
            dados_consulta["ano"],
            dados_consulta["codigo_verificador"],
        )

        await clicar_confirmar_iframe(page)

        await page.wait_for_timeout(5000)

        await page.screenshot(path=caminho_evidencia, full_page=True)

        dados_tela = await extrair_dados_tela_resultado(page)
        dados_resultado = extrair_dados_resultado_atende_net(dados_tela)

        atualizar_dados_processo(
            processo_id=processo.get("id"),
            status_atual=str(dados_resultado.get("situacao") or "")
        )

        await browser.close()

    return {"status": "OK"}


# ================= UTIL =================

async def obter_frame_consulta(page):
    await page.wait_for_selector("iframe", timeout=30000)
    iframe = await page.query_selector("iframe")
    return await iframe.content_frame()


async def preencher_formulario_iframe(page, numero, ano, codigo):
    frame = await obter_frame_consulta(page)

    await frame.wait_for_selector("input", timeout=20000)

    await frame.fill("input[name='numero']", str(numero))
    await frame.fill("input[name='ano']", str(ano))
    await frame.fill("input[name='codigo_verificador']", str(codigo))


async def clicar_confirmar_iframe(page):
    frame = await obter_frame_consulta(page)

    try:
        await frame.get_by_role("button", name="Confirmar").click()
    except:
        await frame.locator("input[value='Confirmar']").click()


async def extrair_dados_tela_resultado(page):
    frame = await obter_frame_consulta(page)

    return await frame.evaluate("() => ({ texto: document.body.innerText })")


async def aceitar_cookies_se_existir(page):
    try:
        botao = page.locator("button:has-text('Aceitar')").first
        await botao.click()
    except:
        pass


def gerar_caminho_evidencia_resultado(processo):
    os.makedirs("evidencias", exist_ok=True)
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"evidencias/{processo.get('id')}_{agora}.png"


async def consultar_processo_atende_net(processo):
    robo = RobotAtendeNet()
    return await robo.consultar_processo(processo)