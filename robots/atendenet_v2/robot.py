from playwright.async_api import async_playwright
import re
import requests
import time
import asyncio


API_KEY_2CAPTCHA = "SUA_API_KEY_AQUI"


# =====================================================
# ✅ RESOLVER CAPTCHA (2CAPTCHA)
# =====================================================
def resolver_captcha(site_key, url):
    print("🧠 Enviando captcha para 2captcha...")

    resposta = requests.get(
        f"http://2captcha.com/in.php?key={API_KEY_2CAPTCHA}&method=userrecaptcha&googlekey={site_key}&pageurl={url}&json=1"
    ).json()

    if resposta.get("status") != 1:
        raise Exception("❌ Erro ao enviar captcha")

    captcha_id = resposta.get("request")

    for _ in range(24):
        time.sleep(5)

        resultado = requests.get(
            f"http://2captcha.com/res.php?key={API_KEY_2CAPTCHA}&action=get&id={captcha_id}&json=1"
        ).json()

        if resultado.get("status") == 1:
            print("✅ Captcha resolvido!")
            return resultado.get("request")

        print("⏳ Aguardando captcha...")

    raise Exception("❌ Timeout ao resolver captcha")


# =====================================================
# ✅ ROBÔ PRINCIPAL
# =====================================================
class RobotAtendeNetV2:

    async def consultar_processo(self, processo):

        print("\n=== ROBÔ PINHAIS (ATENDENET V2) ===")

        url = "https://pinhais.atende.net/autoatendimento/servicos/consulta-de-processo-digital/detalhar/1"

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url)

            # =====================================================
            # ✅ 1. COOKIES
            # =====================================================
            try:
                await page.click("button:has-text('Aceitar')", timeout=5000)
                print("✅ Cookies aceitos")
            except:
                print("ℹ️ Banner de cookies não apareceu")

            await page.wait_for_timeout(3000)

            # =====================================================
            # ✅ 2. PREPARAR DADOS
            # =====================================================
            numero = processo.get("numero_processo")
            codigo = processo.get("codigo") or ""
            ano = processo.get("exercicio") or ""

            numero_base = re.sub(r"[^0-9]", "", str(numero))

            print(f"Número: {numero_base}")
            print(f"Ano: {ano}")
            print(f"Código: {codigo}")

            # =====================================================
            # ✅ 3. CAPTURAR SITEKEY
            # =====================================================
            await page.wait_for_selector("iframe[src*='recaptcha']", timeout=15000)

            site_key = None

            for frame in page.frames:
                if "recaptcha" in frame.url:
                    content = await frame.content()
                    match = re.search(r'data-sitekey="(.*?)"', content)
                    if match:
                        site_key = match.group(1)
                        break

            if not site_key:
                raise Exception("❌ Sitekey do captcha não encontrada")

            print(f"✅ Sitekey encontrada: {site_key}")

            # =====================================================
            # ✅ 4. RESOLVER CAPTCHA
            # =====================================================
            token = await asyncio.to_thread(resolver_captcha, site_key, url)

            # =====================================================
            # ✅ 5. PREENCHER FORMULÁRIO
            # =====================================================
            await page.evaluate(
                """(dados) => {

                    const inputs = Array.from(document.querySelectorAll("input[type='text']"));

                    if (inputs.length < 2) {
                        throw new Error("Inputs insuficientes");
                    }

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
            # ✅ 6. INJETAR CAPTCHA
            # =====================================================
            await page.evaluate(f"""
                document.getElementById("g-recaptcha-response").style.display = "block";
                document.getElementById("g-recaptcha-response").value = "{token}";
            """)

            print("✅ Token captcha inserido")

            await page.wait_for_timeout(2000)

            # =====================================================
            # ✅ 7. CLICAR CONFIRMAR
            # =====================================================
            botao = page.locator("button[name='confirmar']")
            await botao.wait_for(state="visible", timeout=10000)
            await botao.click(force=True)

            print("✅ Consulta enviada")

            # =====================================================
            # ✅ 8. AGUARDAR RESULTADO
            # =====================================================
            await page.wait_for_timeout(6000)

            # =====================================================
            # ✅ 9. EXTRAÇÃO
            # =====================================================
            movimentacoes = []

            rows = page.locator("table tr")
            count = await rows.count()

            print(f"🔎 Linhas encontradas: {count}")

            for i in range(count):
                linha = rows.nth(i)
                texto = await linha.inner_text()
                texto_limpo = texto.strip()

                if texto_limpo and "Data" not in texto_limpo:
                    movimentacoes.append(texto_limpo)

            print(f"✅ Movimentações: {len(movimentacoes)}")

            # =====================================================
            # ✅ 10. STATUS
            # =====================================================
            texto_total = " ".join(movimentacoes).lower()

            if "deferido" in texto_total:
                status_processo = "Finalizado"
            elif "indeferido" in texto_total:
                status_processo = "Indeferido"
            elif "não encontrado" in texto_total:
                await browser.close()
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo não encontrado",
                }
            else:
                status_processo = "Em análise"

            print(f"📊 Status: {status_processo}")

            # =====================================================
            # ✅ 11. FINALIZAR
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
async def consultar_processo_pinhais(processo):
    robo = RobotAtendeNetV2()
    return await robo.consultar_processo(processo)