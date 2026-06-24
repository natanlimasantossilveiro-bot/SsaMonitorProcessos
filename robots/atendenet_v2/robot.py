from playwright.async_api import async_playwright
import re


class RobotAtendeNetV2:

    async def consultar_processo(self, processo):

        print("\n=== ROBÔ ATENDENET V2 ===")

        url = "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            await page.goto(url)

            # =====================================================
            # ✅ 1. ACEITAR COOKIES
            # =====================================================
            try:
                await page.click("button:has-text('Aceitar')", timeout=5000)
                print("✅ Cookies aceitos")
            except:
                print("ℹ️ Banner de cookies não apareceu")

            # =====================================================
            # ✅ 2. CAPTCHA
            # =====================================================
            print("🔒 CAPTCHA detectado")
            print("⚠️ Resolva manualmente e depois continue...")

            await page.pause()

            print("✅ CAPTCHA resolvido")

            # =====================================================
            # ✅ 3. AGUARDAR DOM
            # =====================================================
            print("🔎 Preenchendo campos...")
            await page.wait_for_timeout(3000)

            # =====================================================
            # ✅ 4. PREPARAR DADOS
            # =====================================================
            numero = processo.get("numero_processo")
            codigo = processo.get("codigo") or ""
            ano = processo.get("exercicio") or ""

            numero_base = re.sub(r"[^0-9]", "", str(numero))

            print(f"Número: {numero_base}")
            print(f"Ano: {ano}")
            print(f"Código: {codigo}")

            # =====================================================
            # ✅ 5. PREENCHER (SEM DEPENDER DE NAME)
            # =====================================================
            await page.evaluate(
                """(dados) => {

                    const inputs = Array.from(document.querySelectorAll("input[type='text']"));

                    if (inputs.length < 2) {
                        throw new Error("Inputs insuficientes");
                    }

                    // ORDEM REAL DO FORMULÁRIO
                    const numeroInput = inputs[0];
                    const anoInput = inputs.length > 2 ? inputs[1] : null;
                    const codigoInput = inputs[inputs.length - 1];

                    numeroInput.value = dados.numero;

                    if (dados.ano && anoInput) {
                        anoInput.value = dados.ano;
                    }

                    codigoInput.value = dados.codigo;

                    inputs.forEach(input => {
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    });

                }""",
                {
                    "numero": numero_base,
                    "ano": str(ano),
                    "codigo": codigo,
                }
            )

            print("✅ Formulário preenchido")

            # =====================================================
            # ✅ 6. CLICAR BOTÃO CORRETO (SELETOR OFICIAL)
            # =====================================================
            botao = page.locator("button[name='confirmar']")
            await botao.wait_for(state="visible", timeout=10000)
            await botao.click(force=True)

            print("✅ Consulta realizada")

            # =====================================================
            # ✅ 7. AGUARDAR RESULTADO REAL
            # =====================================================
            await page.wait_for_timeout(5000)

            # =====================================================
            # ✅ 8. EXTRAÇÃO
            # =====================================================
            movimentacoes = []

            rows = page.locator("table tr")
            count = await rows.count()

            print(f"🔎 Linhas encontradas na tabela: {count}")

            for i in range(count):
                linha = rows.nth(i)
                texto = await linha.inner_text()
                texto_limpo = texto.strip()

                if texto_limpo and "Data" not in texto_limpo:
                    movimentacoes.append(texto_limpo)

            print(f"✅ Movimentações capturadas: {len(movimentacoes)}")

            # =====================================================
            # ✅ 9. STATUS
            # =====================================================
            texto_total = " ".join(movimentacoes).lower()

            if "deferido" in texto_total:
                status_processo = "Finalizado"
            elif "indeferido" in texto_total:
                status_processo = "Indeferido"
            else:
                status_processo = "Em análise"

            print(f"📊 Status identificado: {status_processo}")

            # =====================================================
            # ✅ 10. FINALIZAR
            # =====================================================
            await browser.close()

            return {
                "status": "OK",
                "status_processo": status_processo,
                "movimentacoes": movimentacoes,
            }


# =====================================================
# ✅ ENTRYPOINT
# =====================================================
async def consultar_processo_atende_net(processo):
    robo = RobotAtendeNetV2()
    return await robo.consultar_processo(processo)