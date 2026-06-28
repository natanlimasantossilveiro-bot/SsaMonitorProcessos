from playwright.async_api import async_playwright
from datetime import datetime
import re


async def consultar_processo_ponta_grossa(processo):
    url = processo.get("url_orgao")

    numero = str(processo.get("numero_processo"))

    print("\n=== ROBÔ PONTA GROSSA ===")
    print(f"Número: {numero}")
    print(f"URL: {url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # ==================================================
            # ✅ ABRIR DIRETO A PÁGINA DO PROCESSO
            # ==================================================
            await page.goto(url)

            # ✅ espera carregamento SPA
            await page.wait_for_load_state("networkidle")

            print("✅ Página carregada")

            # ==================================================
            # ✅ CAPTURA TEXTO COMPLETO
            # ==================================================
            texto = await page.inner_text("body")
            texto_lower = texto.lower()

            print("\n📄 TEXTO CAPTURADO:")
            print(texto[:500])

            # ==================================================
            # ✅ VALIDAÇÃO
            # ==================================================
            if "erro" in texto_lower and "processo" in texto_lower:
                await browser.close()
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo não encontrado",
                    "texto_completo": texto
                }

            # ==================================================
            # ✅ STATUS
            # ==================================================
            if "finalizado" in texto_lower:
                status_processo = "Finalizado"
            elif "deferido" in texto_lower:
                status_processo = "Deferido"
            elif "indeferido" in texto_lower:
                status_processo = "Indeferido"
            elif "em andamento" in texto_lower:
                status_processo = "Em andamento"
            elif "em análise" in texto_lower or "analise" in texto_lower:
                status_processo = "Em análise"
            else:
                status_processo = "Em andamento"

            # ==================================================
            # ✅ CAPTURA TODAS MOVIMENTAÇÕES
            # ==================================================
            linhas = texto.split("\n")
            movimentacoes = []

            for linha in linhas:
                linha_limpa = linha.strip()

                # pega qualquer linha com data
                if re.search(r"\d{2}/\d{2}/\d{4}", linha_limpa):
                    movimentacoes.append(linha_limpa)

            # ==================================================
            # ✅ PEGA A ÚLTIMA (MAIS RECENTE)
            # ==================================================
            ultima_movimentacao = None
            data_ultimo_movimento = None

            if movimentacoes:
                ultima_movimentacao = movimentacoes[-1]  # 🔥 última linha

                # extrai data da última movimentação
                match = re.search(r"\d{2}/\d{2}/\d{4}", ultima_movimentacao)

                if match:
                    data_str = match.group()

                    try:
                        data_convertida = datetime.strptime(data_str, "%d/%m/%Y")
                        data_ultimo_movimento = data_convertida.strftime("%Y-%m-%d")
                    except Exception:
                        pass

            await browser.close()

            # ==================================================
            # ✅ RETORNO FINAL
            # ==================================================
            return {
                "status": "OK",
                "mensagem": "Consulta realizada com sucesso",
                "status_processo": status_processo,
                "ultima_data_movimento": data_ultimo_movimento,
                "ultima_movimentacao": ultima_movimentacao,
                "texto_completo": texto
            }

    except Exception as e:
        return {
            "status": "ERRO_CONSULTA",
            "mensagem": str(e),
        }