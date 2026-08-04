from playwright.async_api import async_playwright
import re

from pyvirtualdisplay import Display
from robots.base.robot_base import RobotBase
from utils.logger import get_logger

log = get_logger("sjp")


class RobotSJP(RobotBase):

    async def consultar_processo(self, processo):
        log.info(f"Iniciando consulta — processo: {processo.get('numero_processo')}")
        return await executar_consulta_sjp(processo)


async def executar_consulta_sjp(processo):

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

            url = "https://protocolo.sjp.pr.gov.br/servicos/protocolo-digital/controller/consultar_protocolo.php"
            await page.goto(url)

            numero = processo.get("numero_processo")
            numero_limpo = re.sub(r"[^0-9]", "", str(numero))

            log.info(f"Preenchendo numero: {numero_limpo}")

            input_num = page.locator("#num_protocolo")
            await input_num.click()
            await input_num.fill("")
            for digito in numero_limpo:
                await input_num.type(digito, delay=50)
            await page.keyboard.press("Tab")

            cnpj = processo.get("cnpj") or processo.get("CNPJ")
            if cnpj:
                cnpj_limpo = re.sub(r"[^0-9]", "", str(cnpj))
                log.info(f"Preenchendo CNPJ: {cnpj_limpo}")
                input_cnpj = page.locator("#num_documento")
                await input_cnpj.click()
                await input_cnpj.fill("")
                for digito in cnpj_limpo:
                    await input_cnpj.type(digito, delay=80)
                await page.keyboard.press("Tab")
            else:
                log.warning("CNPJ nao encontrado no processo")

            await page.wait_for_selector("button.faleconosco-btn", timeout=10000)
            await page.locator("button.faleconosco-btn").click()
            log.info("Consulta enviada — aguardando resultado")

            try:
                await page.wait_for_selector("table", timeout=10000)
            except Exception:
                log.warning("Tabela de resultado nao encontrada")

            texto_pagina = await page.inner_text("body")
            objeto = None
            for marcador in ("Assunto:", "Objeto:", "Descrição:", "Descricao:"):
                if marcador in texto_pagina:
                    idx = texto_pagina.index(marcador) + len(marcador)
                    objeto = texto_pagina[idx:idx + 500].strip().split("\n")[0].strip() or None
                    break

            movimentacoes = []
            linhas = await page.locator("table tr").all()
            for linha in linhas:
                texto_linha = await linha.inner_text()
                if not texto_linha.strip():
                    continue
                if "Data" in texto_linha and "Descricao" in texto_linha:
                    continue
                movimentacoes.append(texto_linha)

            log.info(f"Movimentacoes extraidas: {len(movimentacoes)}")

            status = None
            for mov in movimentacoes:
                if "Finalizado" in mov:
                    status = "Finalizado"
                    break
                elif "Deferido" in mov:
                    status = "Deferido"
                elif "Indeferido" in mov:
                    status = "Indeferido"
                elif "Em analise" in mov or "Em análise" in mov:
                    status = "Em analise"
                elif "Em tramite" in mov or "Em trâmite" in mov:
                    status = "Em andamento"

            if not status:
                status = "Em andamento"

            log.info(f"Status: {status}")
            await browser.close()

            return {
                "status": "OK",
                "status_processo": status,
                "movimentacoes": movimentacoes,
                "objeto": objeto,
            }
    finally:
        display.stop()


async def consultar_processo_sjp(processo):
    robo = RobotSJP()
    return await robo.consultar_processo(processo)