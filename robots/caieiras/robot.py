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

            log.info(f"Texto pagina (2000 chars): {texto[:2000]}")

            if "nenhum processo foi encontrado" in texto_lower:
                await browser.close()
                log.info("Processo nao encontrado no sistema")
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo nao encontrado no sistema",
                }

            # Extrai status
            status_processo = None
            _MAP_STATUS = [
                (r'indeferido', "Indeferido"),
                (r'deferido', "Deferido"),
                (r'em\s+an[aá]lise', "Em analise"),
                (r'em\s+andamento', "Em andamento"),
                (r'finalizado', "Finalizado"),
                (r'conclu[íi]do', "Finalizado"),
                (r'encerrado', "Encerrado"),
            ]
            for padrao, valor in _MAP_STATUS:
                if re.search(padrao, texto_lower):
                    status_processo = valor
                    break
            if not status_processo:
                status_processo = "Em andamento"

            # Extrai movimentações: linhas que contenham data dd/mm/yyyy
            linhas = texto.split("\n")
            movimentacoes = [
                l.strip() for l in linhas
                if re.search(r"\d{2}/\d{2}/\d{4}", l.strip()) and l.strip()
            ]

            def _data_linha(linha):
                m = re.search(r"\d{2}/\d{2}/\d{4}", linha)
                try:
                    return datetime.strptime(m.group(), "%d/%m/%Y") if m else datetime.min
                except Exception:
                    return datetime.min

            movimentacoes.sort(key=_data_linha, reverse=True)
            log.info(f"Status: {status_processo} | Movimentacoes: {len(movimentacoes)}")

            await browser.close()

            return {
                "status": "OK",
                "mensagem": "Consulta realizada com sucesso",
                "status_processo": status_processo,
                "movimentacoes": movimentacoes,
                "objeto": objeto,
            }

    except Exception as e:
        log.error(f"Erro na consulta: {e}")
        return {"status": "ERRO_CONSULTA", "mensagem": str(e)}