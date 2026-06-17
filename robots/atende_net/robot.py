import os
from datetime import datetime

from playwright.async_api import async_playwright

from robots.base.robot_base import RobotBase

from robots.atende_net.parser import (
    montar_dados_consulta_atende_net,
)

from robots.atende_net.selectors import (
    CAMPO_NUMERO,
    CAMPO_ANO,
    CAMPO_CODIGO_VERIFICADOR,
    BOTAO_CONFIRMAR,
)

from services.captcha_service import (
    solicitar_resolucao_captcha,
    buscar_resposta_captcha_resolvido,
)


class RobotAtendeNet(RobotBase):

    async def consultar_processo(self, processo):
        dados_consulta = montar_dados_consulta_atende_net(processo)

        print("\n=== ROBÔ ATENDE.NET ===")
        print(f"Processo: {dados_consulta['numero']}")
        print(f"Ano: {dados_consulta['ano']}")
        print(f"Código verificador: {dados_consulta['codigo_verificador']}")
        print(f"Empresa: {processo.get('empresa')}")
        print(f"Município: {processo.get('municipio')}")
        print(f"Acesso: {dados_consulta['url']}")

        caminho_solicitacao_existente = processo.get(
            "caminho_solicitacao_captcha"
        )

        if caminho_solicitacao_existente:
            resultado_captcha = await buscar_resposta_captcha_resolvido(
                caminho_solicitacao_existente
            )

            if resultado_captcha.get("status") == "RESOLVIDO":
                print("\n=== CAPTCHA RESOLVIDO ===")
                print("Token reCAPTCHA recebido com sucesso.")

                return await executar_consulta_com_captcha_resolvido(
                    dados_consulta=dados_consulta,
                    processo=processo,
                    resposta_captcha=resultado_captcha.get("resposta"),
                    caminho_processado=resultado_captcha.get(
                        "caminho_processado"
                    ),
                )

            print("\n=== CAPTCHA AINDA PENDENTE ===")
            print(resultado_captcha.get("mensagem"))

            return {
                "status": "PENDENTE_INTEGRACAO_CAPTCHA",
                "mensagem": resultado_captcha.get("mensagem"),
                "dados": {
                    "numero": dados_consulta["numero"],
                    "ano": dados_consulta["ano"],
                    "codigo_verificador": dados_consulta[
                        "codigo_verificador"
                    ],
                    "caminho_solicitacao": caminho_solicitacao_existente,
                    "caminho_resolvido": resultado_captcha.get(
                        "caminho_resolvido"
                    ),
                },
            }

        resultado_captcha = await criar_nova_solicitacao_captcha(
            processo=processo,
            dados_consulta=dados_consulta,
        )

        return resultado_captcha


async def criar_nova_solicitacao_captcha(processo, dados_consulta):
    os.makedirs("evidencias", exist_ok=True)

    caminho_evidencia = gerar_caminho_evidencia_captcha(processo)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False
        )

        page = await browser.new_page()

        await page.goto(
            dados_consulta["url"],
            wait_until="networkidle"
        )

        await aceitar_cookies_se_existir(page)

        await page.screenshot(
            path=caminho_evidencia,
            full_page=True,
        )

        print("\n=== CAPTCHA / VERIFICAÇÃO DE ACESSO ===")
        print(f"Evidência salva em: {caminho_evidencia}")

        await page.wait_for_timeout(5000)

        await browser.close()

    resultado_captcha = await solicitar_resolucao_captcha(
        processo=processo,
        caminho_imagem=caminho_evidencia,
    )

    return {
        "status": "PENDENTE_INTEGRACAO_CAPTCHA",
        "mensagem": resultado_captcha.get("mensagem"),
        "dados": {
            "numero": dados_consulta["numero"],
            "ano": dados_consulta["ano"],
            "codigo_verificador": dados_consulta["codigo_verificador"],
            "evidencia_captcha": caminho_evidencia,
            "caminho_solicitacao": resultado_captcha.get(
                "caminho_solicitacao"
            ),
        },
    }


async def executar_consulta_com_captcha_resolvido(
    dados_consulta,
    processo,
    resposta_captcha,
    caminho_processado=None,
):
    print("\n=== CONSULTA ATENDE.NET COM CAPTCHA RESOLVIDO ===")
    print(f"Processo: {dados_consulta['numero']}")
    print(f"Ano: {dados_consulta['ano']}")
    print(f"Código verificador: {dados_consulta['codigo_verificador']}")

    caminho_evidencia_resultado = gerar_caminho_evidencia_resultado(processo)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False
        )

        page = await browser.new_page()

        await page.goto(
            dados_consulta["url"],
            wait_until="networkidle"
        )

        await aceitar_cookies_se_existir(page)

        print("\nAplicando token do reCAPTCHA na página...")

        await aplicar_token_recaptcha(
            page=page,
            token=resposta_captcha,
        )

        await page.wait_for_timeout(2000)

        try:
            await page.click(BOTAO_CONFIRMAR, timeout=10000)
            print("Confirmação do reCAPTCHA enviada.")
        except Exception:
            print("Botão confirmar do reCAPTCHA não encontrado. Continuando...")

        await page.wait_for_selector(
            CAMPO_NUMERO,
            timeout=60000,
        )

        print("\nPreenchendo dados do processo...")

        await page.fill(
            CAMPO_NUMERO,
            str(dados_consulta["numero"]),
        )

        await page.fill(
            CAMPO_ANO,
            str(dados_consulta["ano"]),
        )

        await page.fill(
            CAMPO_CODIGO_VERIFICADOR,
            str(dados_consulta["codigo_verificador"]),
        )

        await page.click(BOTAO_CONFIRMAR)

        await page.wait_for_timeout(5000)

        await page.screenshot(
            path=caminho_evidencia_resultado,
            full_page=True,
        )

        print(
            f"Evidência do resultado salva em: "
            f"{caminho_evidencia_resultado}"
        )

        await browser.close()

    return {
        "status": "ATENDE_NET_CONSULTA_EXECUTADA",
        "mensagem": (
            "Consulta Atende.Net executada. "
            "Próxima etapa será interpretar a tela de resultado."
        ),
        "dados": {
            "numero": dados_consulta["numero"],
            "ano": dados_consulta["ano"],
            "codigo_verificador": dados_consulta["codigo_verificador"],
            "resposta_captcha": "TOKEN_RECAPTCHA_RECEBIDO",
            "caminho_processado": caminho_processado,
            "evidencia_resultado": caminho_evidencia_resultado,
            "processo_id": processo.get("id"),
        },
    }


async def aplicar_token_recaptcha(page, token):
    await page.evaluate(
        """
        (token) => {
            let textarea = document.querySelector(
                'textarea[name="g-recaptcha-response"]'
            );

            if (!textarea) {
                textarea = document.createElement('textarea');
                textarea.name = 'g-recaptcha-response';
                textarea.id = 'g-recaptcha-response';
                textarea.style.display = 'block';
                document.body.appendChild(textarea);
            }

            textarea.value = token;
            textarea.innerHTML = token;

            textarea.dispatchEvent(
                new Event('input', { bubbles: true })
            );

            textarea.dispatchEvent(
                new Event('change', { bubbles: true })
            );
        }
        """,
        token,
    )


async def aceitar_cookies_se_existir(page):
    try:
        botao_aceitar = page.locator(
            "button:has-text('Aceitar')"
        ).first

        await botao_aceitar.wait_for(timeout=5000)
        await botao_aceitar.click()

        print("Cookies aceitos.")

        await page.wait_for_timeout(2000)

    except Exception:
        print("Banner de cookies não encontrado. Continuando.")


def gerar_caminho_evidencia_captcha(processo):
    processo_id = processo.get("id", "sem_id")
    numero = str(
        processo.get("numero_processo", "sem_numero")
    ).replace("/", "_")
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"evidencias/atende_net_captcha_{processo_id}_{numero}_{agora}.png"


def gerar_caminho_evidencia_resultado(processo):
    processo_id = processo.get("id", "sem_id")
    numero = str(
        processo.get("numero_processo", "sem_numero")
    ).replace("/", "_")
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"evidencias/atende_net_resultado_{processo_id}_{numero}_{agora}.png"


async def consultar_processo_atende_net(processo):
    robo = RobotAtendeNet()
    return await robo.consultar_processo(processo)