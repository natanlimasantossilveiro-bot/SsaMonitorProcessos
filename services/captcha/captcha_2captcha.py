import asyncio
import random

from services.captcha.base_captcha_solver import CaptchaSolverBase
from services.captcha_api_client import (
    enviar_captcha_para_api,
    consultar_resultado_captcha_api
)


class Captcha2CaptchaSolver(CaptchaSolverBase):

    SITEKEY = "6LenD30sAAAAADTdG6GJYoAxOIZy9SEYg1VSY24j"

    async def resolver_captcha(self, page):

        print("\n=== CAPTCHA 2CAPTCHA (FLOW CORRETO) ===")

        # =====================================================
        # ✅ 1. SIMULA COMPORTAMENTO HUMANO
        # =====================================================
        await page.wait_for_timeout(random.randint(2000, 4000))

        await page.mouse.move(200, 200)
        await page.wait_for_timeout(500)

        await page.mouse.move(500, 350)
        await page.wait_for_timeout(500)

        print("✅ Movimento inicial realizado")

        # =====================================================
        # ✅ 2. CLICA NO CAPTCHA (ATIVA ELE)
        # =====================================================
        print("🔘 Tentando clicar no checkbox...")

        try:
            # ✅ ESPERA O IFRAME DO RECAPTCHA aparecer
            await page.wait_for_selector("iframe[src*='recaptcha']", timeout=15000)

            # ✅ SELECIONA O IFRAME CORRETO
            frames = page.frames

            recaptcha_frame = None

            for frame in frames:
                if "api2/anchor" in frame.url:
                    recaptcha_frame = frame
                    break

            if not recaptcha_frame:
                raise Exception("Iframe do captcha não encontrado")

            # ✅ CLICA NO CHECKBOX
            await recaptcha_frame.click("#recaptcha-anchor")

            print("✅ Checkbox clicado com sucesso")

            await page.wait_for_timeout(4000)

            # ✅ VERIFICA SE JÁ RESOLVEU
            checked = await recaptcha_frame.get_attribute(
                "#recaptcha-anchor",
                "aria-checked"
            )

            if checked == "true":
                print("✅ Resolvido automaticamente pelo Google")
                return True

        except Exception as e:
            print(f"⚠️ Erro ao clicar no checkbox: {e}")


        # =====================================================
        # ✅ 3. ENVIA PARA 2CAPTCHA
        # =====================================================
        resultado_envio = await enviar_captcha_para_api(
            processo={},
            sitekey=self.SITEKEY,
            url=page.url
        )

        if resultado_envio.get("status") != "ENVIADO_API":
            raise Exception(f"Erro envio captcha: {resultado_envio}")

        protocolo = resultado_envio.get("protocolo_api")
        print(f"📌 Protocolo: {protocolo}")

        # =====================================================
        # ✅ 4. AGUARDA SOLUÇÃO
        # =====================================================
        for tentativa in range(24):

            await asyncio.sleep(5)

            resultado = await consultar_resultado_captcha_api(protocolo)

            status = resultado.get("status")
            print(f"⏳ Status API: {status}")

            if status == "RESOLVIDO":

                token = resultado.get("resposta")

                print("✅ Token recebido!")

                # =====================================================
                # ✅ 5. INJETA TOKEN
                # =====================================================
                await page.evaluate(
                    """
                    (token) => {
                        const areas = document.querySelectorAll("textarea[name='g-recaptcha-response']");
                        areas.forEach(el => el.value = token);
                    }
                    """,
                    token
                )

                print("✅ Token injetado")

                # =====================================================
                # ✅ 6. INTERAÇÃO HUMANA FINAL
                # =====================================================
                await page.mouse.move(400, 300)
                await page.wait_for_timeout(800)

                await page.mouse.click(400, 300)

                await page.wait_for_timeout(6000)

                print("✅ Fluxo final executado")

                return True

            elif status == "ERRO_API_CAPTCHA":
                print("❌ 2Captcha não conseguiu resolver (UNSOLVABLE)")
                break

        raise Exception("❌ Falha ao resolver captcha")