from playwright.async_api import async_playwright
from datetime import datetime
import re

from utils.logger import get_logger

log = get_logger("ponta_grossa")


async def consultar_processo_ponta_grossa(processo):
    url = processo.get("url_orgao")
    numero = str(processo.get("numero_processo"))

    log.info(f"Iniciando consulta — numero: {numero} | url: {url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url)
            await page.wait_for_load_state("networkidle")

            log.info("Pagina carregada")

            texto = await page.inner_text("body")
            objeto = None
            for marcador in ("Assunto:", "Objeto:", "Descrição:", "Descricao:"):
                if marcador in texto:
                    idx = texto.index(marcador) + len(marcador)
                    objeto = texto[idx:idx + 500].strip().split("\n")[0].strip() or None
                    break
            texto_lower = texto.lower()

            log.debug(f"Texto capturado (primeiros 300 chars): {texto[:300]}")

            if "erro" in texto_lower and "processo" in texto_lower:
                await browser.close()
                log.info("Processo nao encontrado")
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo nao encontrado",
                    "texto_completo": texto,
                }

            if "finalizado" in texto_lower:
                status_processo = "Finalizado"
            elif "deferido" in texto_lower:
                status_processo = "Deferido"
            elif "indeferido" in texto_lower:
                status_processo = "Indeferido"
            elif "em andamento" in texto_lower:
                status_processo = "Em andamento"
            elif "em analise" in texto_lower or "em análise" in texto_lower:
                status_processo = "Em analise"
            else:
                status_processo = "Em andamento"

            linhas = texto.split("\n")
            movimentacoes = [
                linha.strip()
                for linha in linhas
                if re.search(r"\d{2}/\d{2}/\d{4}", linha.strip())
            ]

            ultima_movimentacao = None
            data_ultimo_movimento = None

            if movimentacoes:
                ultima_movimentacao = movimentacoes[-1]
                match = re.search(r"\d{2}/\d{2}/\d{4}", ultima_movimentacao)
                if match:
                    try:
                        data_convertida = datetime.strptime(match.group(), "%d/%m/%Y")
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
                "ultima_movimentacao": ultima_movimentacao,
                "texto_completo": texto,
                "objeto": objeto,
            }

    except Exception as e:
        log.error(f"Erro na consulta: {e}")
        return {"status": "ERRO_CONSULTA", "mensagem": str(e)}