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
                browser = await p.chromium.launch(headless=False)
                page = await browser.new_page()

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
                linhas = [l.strip() for l in texto.split("\n") if l.strip()]

                log.info(f"Linhas capturadas: {len(linhas)}")

                texto_total = " ".join(linhas).lower()

                if "concluido" in texto_total or "concluído" in texto_total:
                    status = "Finalizado"
                elif "finalizado" in texto_total:
                    status = "Finalizado"
                elif "em andamento" in texto_total:
                    status = "Em andamento"
                else:
                    status = "Em analise"

                log.info(f"Status: {status}")

                await browser.close()

                return {
                    "status": "OK",
                    "status_processo": status,
                    "movimentacoes": linhas[:30],
                    "objeto": objeto,
                }
        finally:
            display.stop()


async def consultar_processo_esic(processo):
    robo = RobotEsicSJP()
    return await robo.consultar_processo(processo)