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

            texto = await page.inner_text("body")
            log.debug(f"Texto capturado (primeiros 300 chars): {texto[:300]}")

            numero_formatado = numero.zfill(10)

            if numero_formatado not in texto:
                await browser.close()
                log.info("Processo nao encontrado na lista")
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo nao encontrado na lista",
                    "texto_completo": texto,
                }

            linhas = texto.split("\n")
            linha_processo = None
            for linha in linhas:
                if numero_formatado in linha:
                    linha_processo = linha.strip()
                    break

            linha_lower = (linha_processo or "").lower()

            if "finalizado" in linha_lower:
                status_processo = "Finalizado"
            elif "analise" in linha_lower or "análise" in linha_lower:
                status_processo = "Em analise"
            elif "andamento" in linha_lower:
                status_processo = "Em andamento"
            else:
                status_processo = "Em andamento"

            data_ultimo_movimento = None
            if linha_processo:
                datas = re.findall(r"\d{2}/\d{2}/\d{4}", linha_processo)
                if datas:
                    try:
                        data_convertida = datetime.strptime(datas[-1], "%d/%m/%Y")
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
                "ultima_movimentacao": linha_processo,
                "texto_completo": texto,
            }

    except Exception as e:
        log.error(f"Erro na consulta: {e}")
        return {"status": "ERRO_CONSULTA", "mensagem": str(e)}