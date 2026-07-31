from playwright.async_api import async_playwright
from datetime import datetime
import re

from utils.logger import get_logger

log = get_logger("caieiras")


async def consultar_processo_caieiras(processo):
    url = processo.get("url_orgao") or processo.get("acesso")
    numero_completo = processo.get("numero_processo")
    cnpj = re.sub(r"[^0-9]", "", str(processo.get("login_acesso") or processo.get("cnpj") or ""))

    log.info(f"Iniciando consulta — numero: {numero_completo}")

    try:
        if "/" in numero_completo:
            numero, ano = numero_completo.split("/")
        else:
            numero = numero_completo
            ano = processo.get("exercicio")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url)
            await page.wait_for_timeout(2000)

            await page.fill("#frm_numero", str(numero))
            await page.fill("#frm_ano", str(ano))
            await page.fill("#frm_cpf", str(cnpj))

            await page.click("#bt-selecionar-dividas")
            await page.wait_for_timeout(3000)

            texto = await page.inner_text("body")
            objeto = None
            for marcador in ("Assunto:", "Objeto:", "Descrição:", "Descricao:"):
                if marcador in texto:
                    idx = texto.index(marcador) + len(marcador)
                    objeto = texto[idx:idx + 500].strip().split("\n")[0].strip() or None
                    break
            texto_lower = texto.lower()

            log.debug(f"Texto capturado (primeiros 500 chars): {texto[:500]}")

            if "nenhum processo foi encontrado" in texto_lower:
                await browser.close()
                log.info("Processo nao encontrado no sistema")
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo nao encontrado no sistema",
                }

            status_processo = None
            if "deferido" in texto_lower:
                status_processo = "Deferido"
            elif "indeferido" in texto_lower:
                status_processo = "Indeferido"
            elif "em andamento" in texto_lower:
                status_processo = "Em andamento"

            data_ultimo_movimento = None
            match_data = re.search(r"\d{2}/\d{2}/\d{4}", texto)
            if match_data:
                try:
                    data_convertida = datetime.strptime(match_data.group(), "%d/%m/%Y")
                    data_ultimo_movimento = data_convertida.strftime("%Y-%m-%d")
                except Exception:
                    pass

            log.info(f"Status: {status_processo} | Data: {data_ultimo_movimento}")

            await browser.close()

            return {
                "status": "OK",
                "mensagem": "Consulta realizada com sucesso",
                "status_processo": status_processo,
                "ultima_data_movimento": data_ultimo_movimento,
                "ultima_movimentacao": status_processo,
                "objeto": objeto,
            }

    except Exception as e:
        log.error(f"Erro na consulta: {e}")
        return {"status": "ERRO_CONSULTA", "mensagem": str(e)}