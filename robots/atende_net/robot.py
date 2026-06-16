import os
from datetime import datetime

from playwright.async_api import async_playwright

from robots.base.robot_base import RobotBase

from robots.atende_net.parser import (
    montar_dados_consulta_atende_net,
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

        caminho_solicitacao_existente = processo.get("caminho_solicitacao_captcha")

        if caminho_solicitacao_existente:
            resultado_captcha = buscar_resposta_captcha_resolvido(
                caminho_solicitacao_existente
            )

            if resultado_captcha.get("status") == "RESOLVIDO":
                print("\n=== CAPTCHA RESOLVIDO ===")
                print(f"Resposta: {resultado_captcha.get('resposta')}")

                return await executar_consulta_com_captcha_resolvido(
                    dados_consulta=dados_consulta,
                    processo=processo,
                    resposta_captcha=resultado_captcha.get("resposta"),
                    caminho_processado=resultado_captcha.get("caminho_processado"),
                )

            print("\n=== CAPTCHA AINDA PENDENTE ===")
            print(resultado_captcha.get("mensagem"))

            return {
                "status": "PENDENTE_INTEGRACAO_CAPTCHA",
                "mensagem": resultado_captcha.get("mensagem"),
                "dados": {
                    "numero": dados_consulta["numero"],
                    "ano": dados_consulta["ano"],
                    "codigo_verificador": dados_consulta["codigo_verificador"],
                    "caminho_solicitacao": caminho_solicitacao_existente,
                    "caminho_resolvido": resultado_captcha.get("caminho_resolvido"),
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
            "caminho_solicitacao": resultado_captcha.get("caminho_solicitacao"),
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
    print(f"Captcha: {resposta_captcha}")

    return {
        "status": "CAPTCHA_RESOLVIDO_FLUXO_PENDENTE",
        "mensagem": (
            "Captcha resolvido encontrado. Próxima etapa será preencher "
            "captcha, número, ano e código verificador no Atende.Net."
        ),
        "dados": {
            "numero": dados_consulta["numero"],
            "ano": dados_consulta["ano"],
            "codigo_verificador": dados_consulta["codigo_verificador"],
            "resposta_captcha": resposta_captcha,
            "caminho_processado": caminho_processado,
            "processo_id": processo.get("id"),
        },
    }


def gerar_caminho_evidencia_captcha(processo):
    processo_id = processo.get("id", "sem_id")
    numero = str(processo.get("numero_processo", "sem_numero")).replace("/", "_")
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"evidencias/atende_net_captcha_{processo_id}_{numero}_{agora}.png"


async def consultar_processo_atende_net(processo):
    robo = RobotAtendeNet()
    return await robo.consultar_processo(processo)