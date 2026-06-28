from playwright.async_api import async_playwright
from datetime import datetime
import re


async def consultar_processo_franco_rocha(processo):
    url = processo.get("url_orgao")
    numero = str(processo.get("numero_processo"))
    usuario = processo.get("login_acesso").replace(".", "").replace("-", "")
    senha = processo.get("senha_acesso")

    print("\n=== ROBÔ FRANCO DA ROCHA ===")
    print(f"Número: {numero}")
    print(f"Usuário: {usuario}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # ==================================================
            # ✅ LOGIN
            # ==================================================

            await page.goto(url)
            await page.wait_for_timeout(3000)

            # CPF
            await page.click("#cpf_cnpj")
            await page.fill("#cpf_cnpj", "")
            await page.keyboard.type(usuario, delay=120)

            await page.press("#cpf_cnpj", "Tab")
            await page.wait_for_timeout(1500)

            await page.wait_for_selector("#cpf_cnpj_avancar:not([disabled])")
            await page.click("#cpf_cnpj_avancar")

            await page.wait_for_timeout(3000)

            # SENHA
            await page.fill('input[name="passLogin"]', senha)
            await page.click('button:has-text("Entrar")')

            await page.wait_for_timeout(5000)

            print("✅ Login realizado")

            # ==================================================
            # ✅ CAPTURA TEXTO
            # ==================================================

            texto = await page.inner_text("body")

            print("\n📄 TEXTO CAPTURADO:")
            print(texto[:500])

            # ==================================================
            # ✅ FORMATA NÚMERO CORRETAMENTE
            # ==================================================

            numero_formatado = numero.zfill(10)

            if numero_formatado not in texto:
                await browser.close()
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo não encontrado na lista",
                    "texto_completo": texto  # 🔥 ESSENCIAL PRO BATCH
                }

            # ==================================================
            # ✅ LOCALIZA LINHA DO PROCESSO
            # ==================================================

            linhas = texto.split("\n")

            linha_processo = None
            for linha in linhas:
                if numero_formatado in linha:
                    linha_processo = linha.strip()
                    break

            # ==================================================
            # ✅ STATUS (POR LINHA - CORRETO)
            # ==================================================

            linha_lower = (linha_processo or "").lower()

            if "finalizado" in linha_lower:
                status_processo = "Finalizado"
            elif "análise" in linha_lower or "analise" in linha_lower:
                status_processo = "Em análise"
            elif "andamento" in linha_lower:
                status_processo = "Em andamento"
            else:
                status_processo = "Em andamento"

            # ==================================================
            # ✅ DATA DA LINHA
            # ==================================================

            data_ultimo_movimento = None

            if linha_processo:
                datas = re.findall(r"\d{2}/\d{2}/\d{4}", linha_processo)

                if datas:
                    try:
                        data_convertida = datetime.strptime(datas[-1], "%d/%m/%Y")
                        data_ultimo_movimento = data_convertida.strftime("%Y-%m-%d")
                    except Exception:
                        data_ultimo_movimento = None

            await browser.close()

            # ==================================================
            # ✅ RETORNO COMPLETO (AGORA CORRETO)
            # ==================================================

            return {
                "status": "OK",
                "mensagem": "Consulta realizada com sucesso",
                "status_processo": status_processo,
                "ultima_data_movimento": data_ultimo_movimento,
                "ultima_movimentacao": linha_processo,
                "texto_completo": texto  # 🔥 ESSENCIAL PRO BATCH
            }

    except Exception as e:
        return {
            "status": "ERRO_CONSULTA",
            "mensagem": str(e),
        }