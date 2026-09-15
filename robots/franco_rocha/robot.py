from playwright.async_api import async_playwright
from datetime import datetime
import re

from utils.logger import get_logger

log = get_logger("franco_rocha")


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

            # Extrai movimentações: linhas que começam com dd/mm/yyyy HH:MM
            linhas = texto.split("\n")
            movimentacoes = []
            for linha in linhas:
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

            # Status: tenta a movimentação mais recente primeiro, fallback no texto todo
            _MAP_STATUS = [
                (r'indeferido', "Indeferido"),
                (r'deferido', "Deferido"),
                (r'em\s+an[aá]lise', "Em analise"),
                (r'em\s+andamento', "Em andamento"),
                (r'finalizado', "Finalizado"),
                (r'conclu[íi]do', "Finalizado"),
                (r'encerrado', "Encerrado"),
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
