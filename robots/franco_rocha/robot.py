from playwright.async_api import async_playwright
from datetime import datetime
import re

from utils.logger import get_logger

log = get_logger("franco_rocha")


async def _extrair_movimentacoes_tabela(page):
    """
    Extrai movimentações lendo células de cada <tr> da tabela de tramitações.
    Captura conteúdo completo dos despachos (multi-linha dentro da célula).
    Retorna a tabela com mais linhas de data encontrada na página.
    """
    melhor = []
    tabelas = await page.query_selector_all("table")
    for tabela in tabelas:
        candidatas = []
        rows = await tabela.query_selector_all("tr")
        for row in rows:
            cells = await row.query_selector_all("td")
            if not cells:
                continue
            date_text = (await cells[0].inner_text()).strip()
            if not re.match(r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}", date_text):
                continue
            partes = [date_text]
            for i in range(1, len(cells)):
                cell_text = (await cells[i].inner_text()).strip()
                if cell_text:
                    partes.append(re.sub(r'\s+', ' ', cell_text)[:400])
            candidatas.append("  ".join(partes))
        if len(candidatas) > len(melhor):
            melhor = candidatas
    return melhor


async def consultar_processo_franco_rocha(processo):
    url = processo.get("url_orgao")
    numero = str(processo.get("numero_processo"))
    usuario = processo.get("login_acesso", "").replace(".", "").replace("-", "")
    senha = processo.get("senha_acesso")

    log.info(f"Iniciando consulta — numero: {numero}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url)
            await page.wait_for_timeout(3000)

            await page.click("#cpf_cnpj")
            await page.fill("#cpf_cnpj", "")
            await page.keyboard.type(usuario, delay=120)
            await page.press("#cpf_cnpj", "Tab")
            await page.wait_for_timeout(1500)

            await page.wait_for_selector("#cpf_cnpj_avancar:not([disabled])")
            await page.click("#cpf_cnpj_avancar")
            await page.wait_for_timeout(3000)

            await page.fill('input[name="passLogin"]', senha)
            await page.click('button:has-text("Entrar")')
            await page.wait_for_timeout(5000)

            log.info("Login realizado")

            texto_lista = await page.inner_text("body")
            numero_formatado = numero.zfill(10)

            if numero_formatado not in texto_lista:
                await browser.close()
                log.info("Processo nao encontrado na lista")
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo nao encontrado na lista",
                }

            # Abre o detalhe do processo clicando no número na lista
            await page.click(f"text={numero_formatado}")
            await page.wait_for_timeout(3000)

            texto = await page.inner_text("body")
            log.info(f"Texto detalhe (2000 chars): {texto[:2000]}")

            texto_lower = texto.lower()

            # Extrai movimentações via células de tabela (captura despachos completos)
            movimentacoes = await _extrair_movimentacoes_tabela(page)

            # Fallback: linha de texto se tabela não retornou nada
            if not movimentacoes:
                for linha in texto.split("\n"):
                    stripped = linha.strip()
                    if re.match(r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}", stripped):
                        movimentacoes.append(stripped)

            def _data_linha(linha):
                m = re.search(r"\d{2}/\d{2}/\d{4}", linha)
                try:
                    return datetime.strptime(m.group(), "%d/%m/%Y") if m else datetime.min
                except Exception:
                    return datetime.min

            movimentacoes.sort(key=_data_linha, reverse=True)

            _MAP_STATUS = [
                (r'indeferido', "Indeferido"),
                (r'deferido', "Deferido"),
                (r'em\s+an[aá]lise', "Em analise"),
                (r'em\s+andamento', "Em andamento"),
                (r'finalizado', "Finalizado"),
                (r'encerrado', "Encerrado"),
                # "CONCLUIDO" neste portal = fase encerrada, não processo encerrado.
                # Não mapeado para "Finalizado" para evitar exclusão do monitoramento.
            ]
            status_processo = None
            if movimentacoes:
                for padrao, valor in _MAP_STATUS:
                    if re.search(padrao, movimentacoes[0].lower()):
                        status_processo = valor
                        break
            if not status_processo:
                for padrao, valor in _MAP_STATUS:
                    if re.search(padrao, texto_lower):
                        status_processo = valor
                        break
            if not status_processo:
                status_processo = "Em andamento"

            log.info(f"Status: {status_processo} | Movimentacoes: {len(movimentacoes)}")

            await browser.close()

            return {
                "status": "OK",
                "mensagem": "Consulta realizada com sucesso",
                "status_processo": status_processo,
                "movimentacoes": movimentacoes,
            }

    except Exception as e:
        log.error(f"Erro na consulta: {e}")
        return {"status": "ERRO_CONSULTA", "mensagem": str(e)}
