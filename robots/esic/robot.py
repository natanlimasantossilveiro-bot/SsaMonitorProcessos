from playwright.async_api import async_playwright
import re

from pyvirtualdisplay import Display
from robots.base.robot_base import RobotBase
from utils.logger import get_logger

log = get_logger("esic")


class RobotEsicSJP(RobotBase):

    async def consultar_processo(self, processo):
        log.info(f"Iniciando consulta — processo: {processo.get('numero_processo')}")

        url = "https://esic.sjp.pr.gov.br/servicos/esic/controller/consulta/con_solicitacao.php"

        display = Display(visible=False, size=(1280, 800))
        display.start()
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=False,
                    executable_path="/usr/bin/google-chrome",
                    ignore_default_args=["--enable-automation", "--disable-infobars"],
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                await page.goto(url)

                numero = processo.get("numero_processo") or ""
                numero_limpo = re.sub(r"[^\d]", "", str(numero))

                log.info(f"Numero: {numero_limpo}")

                await page.wait_for_selector("#solic_protocolo")

                input_processo = page.locator("#solic_protocolo")
                await input_processo.click()
                await input_processo.fill(numero_limpo)

                log.info("Campo preenchido")

                await page.click("button.faleconosco-btn")
                log.info("Consulta enviada")

                await page.wait_for_timeout(5000)

                texto = await page.inner_text("body")
                objeto = None
                for marcador in ("Assunto:", "Objeto:", "Descrição:", "Descricao:"):
                    if marcador in texto:
                        idx = texto.index(marcador) + len(marcador)
                        objeto = texto[idx:idx + 500].strip().split("\n")[0].strip() or None
                        break

                texto_total = texto.lower()

                if "concluido" in texto_total or "concluído" in texto_total:
                    status = "Finalizado"
                elif "finalizado" in texto_total:
                    status = "Finalizado"
                elif "em andamento" in texto_total:
                    status = "Em andamento"
                else:
                    status = "Em analise"

                # Extrai data da última resposta a partir do campo "Situação Atual"
                ultima_data = None
                ultima_mov_desc = None
                m = re.search(r"Situa[çc][aã]o\s+Atual:.*?(\d{2}/\d{2}/\d{4})\s+às\s+(\d{2}:\d{2})", texto)
                if m:
                    ultima_data = m.group(1)
                    hora = m.group(2)
                    ultima_mov_desc = f"{status} - {ultima_data} às {hora}"
                    log.info(f"Ultima data extraída: {ultima_data} às {hora}")

                log.info(f"Status: {status}")

                await browser.close()

                # Não retornar as linhas brutas da página como movimentações — o portal
                # e-SIC não tem estrutura de tramites; retornar lista vazia evita que
                # metadados do cabeçalho (Protocolo:, Situação Atual:, Data:) sejam
                # inseridos no banco como movimentações falsas.
                return {
                    "status": "OK",
                    "status_processo": status,
                    "movimentacoes": [],
                    "ultima_data_movimento": ultima_data,
                    "ultima_movimentacao": ultima_mov_desc,
                    "objeto": objeto,
                }
        finally:
            display.stop()


async def consultar_processo_esic(processo):
    robo = RobotEsicSJP()
    return await robo.consultar_processo(processo)