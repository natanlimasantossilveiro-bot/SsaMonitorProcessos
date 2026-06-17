import os
import asyncio
import httpx

from dotenv import load_dotenv


load_dotenv()


CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY")
CAPTCHA_API_ENVIAR_URL = os.getenv("CAPTCHA_API_ENVIAR_URL")
CAPTCHA_API_RESULTADO_URL = os.getenv("CAPTCHA_API_RESULTADO_URL")

RECAPTCHA_SITEKEY_ATENDE_NET = "6LenD30sAAAAADTdG6GJYoAxOIZy9SEYg1VSY24j"

TEMPO_ESPERA_ENTRE_CONSULTAS = 5
TOTAL_TENTATIVAS_RESULTADO = 24


def api_configurada():
    return bool(
        CAPTCHA_API_KEY
        and CAPTCHA_API_ENVIAR_URL
        and CAPTCHA_API_RESULTADO_URL
    )


async def enviar_captcha_para_api(
    processo,
    caminho_imagem=None,
):
    print("\n=== ENTRANDO EM ENVIAR_CAPTCHA_PARA_API ===")
    print("API configurada?", api_configurada())
    print("URL envio:", CAPTCHA_API_ENVIAR_URL)
    print("Tipo: Google reCAPTCHA v2")

    if not api_configurada():
        return {
            "status": "API_NAO_CONFIGURADA",
            "mensagem": "API de captcha não configurada no .env.",
            "protocolo_api": None,
            "resposta": None,
        }

    try:
        pageurl = processo.get("acesso")

        dados = {
            "key": CAPTCHA_API_KEY,
            "method": "userrecaptcha",
            "googlekey": RECAPTCHA_SITEKEY_ATENDE_NET,
            "pageurl": pageurl,
            "json": "0",
        }

        print("ENVIANDO RECAPTCHA PARA 2CAPTCHA...")
        print(f"Page URL: {pageurl}")
        print(f"Sitekey: {RECAPTCHA_SITEKEY_ATENDE_NET}")

        async with httpx.AsyncClient(timeout=60) as client:
            resposta = await client.post(
                CAPTCHA_API_ENVIAR_URL,
                data=dados,
            )

        print("Status HTTP:", resposta.status_code)

        resposta.raise_for_status()

        texto_resposta = resposta.text.strip()

        print("Resposta API BRUTA:")
        print(texto_resposta)

        if texto_resposta.startswith("OK|"):
            protocolo_api = texto_resposta.split("|", 1)[1]

            return {
                "status": "ENVIADO_API",
                "mensagem": "reCAPTCHA enviado para 2Captcha com sucesso.",
                "protocolo_api": protocolo_api,
                "resposta": None,
                "raw": texto_resposta,
            }

        return {
            "status": "ERRO_API_CAPTCHA",
            "mensagem": texto_resposta,
            "protocolo_api": None,
            "resposta": None,
            "raw": texto_resposta,
        }

    except Exception as erro:
        print("ERRO AO ENVIAR RECAPTCHA PARA API:", erro)

        return {
            "status": "ERRO_API_CAPTCHA",
            "mensagem": f"Erro ao enviar reCAPTCHA para API: {erro}",
            "protocolo_api": None,
            "resposta": None,
        }


async def consultar_resultado_captcha_api(
    protocolo_api,
):
    if not api_configurada():
        return {
            "status": "API_NAO_CONFIGURADA",
            "mensagem": "API de captcha não configurada no .env.",
            "resposta": None,
        }

    if not protocolo_api:
        return {
            "status": "SEM_PROTOCOLO_API",
            "mensagem": "Não há protocolo da API para consultar.",
            "resposta": None,
        }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            for tentativa in range(1, TOTAL_TENTATIVAS_RESULTADO + 1):
                print(
                    f"Consultando resultado do reCAPTCHA na 2Captcha "
                    f"({tentativa}/{TOTAL_TENTATIVAS_RESULTADO})..."
                )

                resposta = await client.get(
                    CAPTCHA_API_RESULTADO_URL,
                    params={
                        "key": CAPTCHA_API_KEY,
                        "action": "get",
                        "id": protocolo_api,
                        "json": "0",
                    },
                )

                print("Status HTTP resultado:", resposta.status_code)

                resposta.raise_for_status()

                texto_resposta = resposta.text.strip()

                print("Resposta resultado API BRUTA:")
                print(texto_resposta)

                if texto_resposta == "CAPCHA_NOT_READY":
                    await asyncio.sleep(TEMPO_ESPERA_ENTRE_CONSULTAS)
                    continue

                if texto_resposta.startswith("OK|"):
                    token_recaptcha = texto_resposta.split("|", 1)[1]

                    return {
                        "status": "RESOLVIDO",
                        "mensagem": "reCAPTCHA resolvido pela 2Captcha.",
                        "resposta": token_recaptcha,
                        "raw": texto_resposta,
                    }

                return {
                    "status": "ERRO_API_CAPTCHA",
                    "mensagem": texto_resposta,
                    "resposta": None,
                    "raw": texto_resposta,
                }

        return {
            "status": "PENDENTE",
            "mensagem": "reCAPTCHA ainda não foi resolvido pela API.",
            "resposta": None,
        }

    except Exception as erro:
        print("ERRO AO CONSULTAR RESULTADO DA API:", erro)

        return {
            "status": "ERRO_API_CAPTCHA",
            "mensagem": f"Erro ao consultar resultado da API: {erro}",
            "resposta": None,
        }