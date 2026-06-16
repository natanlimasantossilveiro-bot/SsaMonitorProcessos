import os
from datetime import datetime

from playwright.async_api import async_playwright

from robots.base.robot_base import RobotBase

from robots.atende_net.parser import (
    montar_dados_consulta_atende_net,
)

from services.captcha_service import solicitar_resolucao_captcha


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


def gerar_caminho_evidencia_captcha(processo):
    processo_id = processo.get("id", "sem_id")
    numero = str(processo.get("numero_processo", "sem_numero")).replace("/", "_")
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"evidencias/atende_net_captcha_{processo_id}_{numero}_{agora}.png"


async def consultar_processo_atende_net(processo):
    robo = RobotAtendeNet()
    return await robo.consultar_processo(processo)