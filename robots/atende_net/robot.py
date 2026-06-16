from robots.base.robot_base import RobotBase

from robots.atende_net.parser import (
    normalizar_numero_processo_atende_net,
    extrair_dados_resultado_atende_net,
)

from services.captcha_service import solicitar_resolucao_captcha


class RobotAtendeNet(RobotBase):

    async def consultar_processo(self, processo):
        numero_processo = normalizar_numero_processo_atende_net(processo)

        print("\n=== ROBÔ ATENDE.NET ===")
        print(f"Processo: {numero_processo}")
        print(f"Empresa: {processo.get('empresa')}")
        print(f"Município: {processo.get('municipio')}")
        print(f"Acesso: {processo.get('acesso')}")

        resultado_captcha = await solicitar_resolucao_captcha(
            processo=processo,
            caminho_imagem=None,
        )

        if resultado_captcha.get("status") == "PENDENTE_INTEGRACAO_CAPTCHA":
            return {
                "status": "PENDENTE_INTEGRACAO_CAPTCHA",
                "mensagem": resultado_captcha.get("mensagem"),
                "dados": None,
            }

        dados_extraidos = extrair_dados_resultado_atende_net("")

        return {
            "status": "OK",
            "mensagem": "Consulta Atende.Net executada em modo estrutural.",
            "dados": dados_extraidos,
        }


async def consultar_processo_atende_net(processo):
    robo = RobotAtendeNet()
    return await robo.consultar_processo(processo)