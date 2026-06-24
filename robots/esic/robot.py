from playwright.async_api import async_playwright
import re


class RobotEsicSJP:

    async def consultar_processo(self, processo):

        print("\n=== ROBÔ ESIC SJP ===")

        url = "https://esic.sjp.pr.gov.br/servicos/esic/controller/consulta/con_solicitacao.php"

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            await page.goto(url)

            # =====================================================
            # ✅ 1. PREPARAR DADOS
            # =====================================================
            numero = processo.get("numero_processo") or ""

            numero_limpo = re.sub(r"[^\d]", "", str(numero))

            print(f"Número: {numero_limpo}")

            # =====================================================
            # ✅ 2. ESPERAR INPUT
            # =====================================================
            await page.wait_for_selector("#solic_protocolo")

            # =====================================================
            # ✅ 3. PREENCHER CAMPO
            # =====================================================
            input_processo = page.locator("#solic_protocolo")

            await input_processo.click()
            await input_processo.fill(numero_limpo)

            print("✅ Campo preenchido")

            # =====================================================
            # ✅ 4. CLICAR BOTÃO BUSCAR
            # =====================================================
            await page.click("button.faleconosco-btn")

            print("✅ Consulta realizada")

            # =====================================================
            # ✅ 5. AGUARDAR RESULTADO
            # =====================================================
            await page.wait_for_timeout(5000)

            # =====================================================
            # ✅ 6. EXTRAÇÃO SIMPLES
            # =====================================================
            texto = await page.inner_text("body")

            linhas = [
                linha.strip()
                for linha in texto.split("\n")
                if linha.strip()
            ]

            print(f"🔎 Linhas capturadas: {len(linhas)}")

            # =====================================================
            # ✅ 7. STATUS
            # =====================================================
            texto_total = " ".join(linhas).lower()

            if "concluído" in texto_total:
                status = "Finalizado"
            elif "em andamento" in texto_total:
                status = "Em andamento"
            elif "finalizado" in texto_total:
                status = "Finalizado"
            else:
                status = "Em análise"

            print(f"📊 Status identificado: {status}")

            # =====================================================
            # ✅ 8. FINALIZAR
            # =====================================================
            await browser.close()

            return {
                "status": "OK",
                "status_processo": status,
                "movimentacoes": linhas[:30],
            }


# =====================================================
# ✅ ENTRYPOINT
# =====================================================
async def consultar_processo_esic(processo):
    robo = RobotEsicSJP()
    return await robo.consultar_processo(processo)
