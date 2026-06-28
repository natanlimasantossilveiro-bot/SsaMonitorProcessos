from playwright.async_api import async_playwright
from datetime import datetime
import re


async def consultar_processo_caieiras(processo):
    url = processo.get("url_orgao") or processo.get("acesso")

    numero_completo = processo.get("numero_processo")
    cnpj = processo.get("login_acesso") or processo.get("cnpj")

    print("\n=== ROBÔ CAIEIRAS ===")
    print(f"Número: {numero_completo}")
    print(f"CNPJ/CPF: {cnpj}")

    try:
        # ✅ separa número e ano
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

            # ✅ CAMPOS
            await page.fill("#frm_numero", str(numero))
            await page.fill("#frm_ano", str(ano))
            await page.fill("#frm_cpf", str(cnpj))

            # ✅ BOTÃO
            await page.click("#bt-selecionar-dividas")

            await page.wait_for_timeout(3000)

            # ✅ CAPTURA TEXTO
            texto = await page.inner_text("body")

            print("\n📄 TEXTO CAPTURADO:")
            print(texto[:500])

            # 🔥 NORMALIZA TEXTO
            texto_lower = texto.lower()

            # ✅ CASO: PROCESSO NÃO ENCONTRADO
            if "nenhum processo foi encontrado" in texto_lower:
                await browser.close()
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo não encontrado no sistema",
                }

            # ✅ IDENTIFICAR STATUS
            status_processo = None

            if "deferido" in texto_lower:
                status_processo = "Deferido"
            elif "indeferido" in texto_lower:
                status_processo = "Indeferido"
            elif "em andamento" in texto_lower:
                status_processo = "Em andamento"

            # ✅ IDENTIFICAR DATA
            data_ultimo_movimento = None

            match_data = re.search(r"\d{2}/\d{2}/\d{4}", texto)
            if match_data:
                data_str = match_data.group()
                data_convertida = datetime.strptime(data_str, "%d/%m/%Y")
                data_ultimo_movimento = data_convertida.strftime("%Y-%m-%d")

            await browser.close()

            return {
                "status": "OK",
                "mensagem": "Consulta realizada com sucesso",
                "status_processo": status_processo,
                "ultima_data_movimento": data_ultimo_movimento,
                "ultima_movimentacao": status_processo,
            }

    except Exception as e:
        return {
            "status": "ERRO_CONSULTA",
            "mensagem": str(e),
        }