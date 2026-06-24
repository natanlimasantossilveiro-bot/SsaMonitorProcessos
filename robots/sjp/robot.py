from playwright.async_api import async_playwright
import re

from robots.base.robot_base import RobotBase
from database.repositories import registrar_movimentacao


class RobotSJP(RobotBase):

    async def consultar_processo(self, processo):

        print("\n=== ROBÔ SJP ===")
        print(f"Processo: {processo.get('numero_processo')}")

        return await executar_consulta_sjp(processo)


# =====================================================
# ✅ EXECUÇÃO PRINCIPAL
# =====================================================
async def executar_consulta_sjp(processo):

    print("🔍 DEBUG PROCESSO:", processo)

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        url = "https://protocolo.sjp.pr.gov.br/servicos/protocolo-digital/controller/consultar_protocolo.php"

        await page.goto(url)
        print("🔍 Página carregada")

        # =====================================================
        # ✅ PREENCHER NÚMERO (CORRIGIDO)
        # =====================================================
        numero = processo.get("numero_processo")

        numero_limpo = re.sub(r"[^0-9]", "", str(numero))

        print(f"✏️ Preenchendo número: {numero_limpo}")

        input_num = page.locator("#num_protocolo")

        await input_num.click()
        await input_num.fill("")

        for digito in numero_limpo:
            await input_num.type(digito, delay=50)

        await page.keyboard.press("Tab")

        # =====================================================
        # ✅ PREENCHER CNPJ (CORRIGIDO)
        # =====================================================
        cnpj = processo.get("cnpj") or processo.get("CNPJ")

        if cnpj:
            cnpj_limpo = re.sub(r"[^0-9]", "", str(cnpj))

            print(f"✏️ Preenchendo CNPJ: {cnpj_limpo}")

            input_cnpj = page.locator("#num_documento")

            await input_cnpj.click()
            await input_cnpj.fill("")

            for digito in cnpj_limpo:
                await input_cnpj.type(digito, delay=80)

            await page.keyboard.press("Tab")

        else:
            print("⚠️ CNPJ não encontrado")

        # =====================================================
        # ✅ CLICAR BOTÃO
        # =====================================================
        print("🖱️ Clicando botão Buscar...")

        await page.wait_for_selector("button.faleconosco-btn", timeout=10000)
        await page.locator("button.faleconosco-btn").click()

        print("✅ Clique realizado")

        # =====================================================
        # ✅ AGUARDAR RESULTADO REAL
        # =====================================================
        print("⏳ Aguardando retorno da consulta...")

        try:
            await page.wait_for_selector("table", timeout=10000)
        except:
            print("⚠️ Tabela não encontrada - pode não ter resultado")

        # =====================================================
        # ✅ EXTRAIR MOVIMENTAÇÕES
        # =====================================================
        movimentacoes = []

        linhas = await page.locator("table tr").all()

        for linha in linhas:
            texto_linha = await linha.inner_text()

            if not texto_linha.strip():
                continue

            if "Data" in texto_linha and "Descrição" in texto_linha:
                continue

            movimentacoes.append(texto_linha)

        print("\n📊 MOVIMENTAÇÕES EXTRAÍDAS:")
        for mov in movimentacoes:
            print("➡️", mov)

        # =====================================================
        # ✅ SALVAR NO BANCO
        # =====================================================
        print("\n💾 Salvando movimentações no banco...")

        for mov in movimentacoes:
            try:
                sucesso = registrar_movimentacao(
                    processo["id"],
                    None,
                    mov
                )

                if sucesso:
                    print("✅ Nova movimentação salva")
                else:
                    print("⚠️ Movimentação já existia")

            except Exception as e:
                print(f"❌ Erro ao salvar movimentação: {e}")

        # =====================================================
        # ✅ STATUS INTELIGENTE
        # =====================================================

        status = None

        for mov in movimentacoes:

            # prioridade máxima
            if "Finalizado" in mov:
                status = "Finalizado"
                break

            # decisões importantes
            elif "Deferido" in mov:
                status = "Deferido"

            elif "Indeferido" in mov:
                status = "Indeferido"

            # estados intermediários
            elif "Em análise" in mov:
                status = "Em análise"

            elif "Em trâmite" in mov:
                status = "Em andamento"

        # fallback
        if not status:
            status = "Em andamento"

        print(f"\n📌 STATUS: {status}")

        await browser.close()

    return {
        "status": "OK",
        "status_processo": status,
        "movimentacoes": movimentacoes
    }


# =====================================================
# ✅ ENTRYPOINT
# =====================================================
async def consultar_processo_sjp(processo):
    robo = RobotSJP()
    return await robo.consultar_processo(processo)