import os
import asyncio
import httpx

from dotenv import load_dotenv

load_dotenv()

CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY")
CAPTCHA_API_ENVIAR_URL = os.getenv("CAPTCHA_API_ENVIAR_URL")
CAPTCHA_API_RESULTADO_URL = os.getenv("CAPTCHA_API_RESULTADO_URL")

TEMPO_ESPERA_ENTRE_CONSULTAS = 5
TOTAL_TENTATIVAS_RESULTADO = 24


def api_configurada():
    return all([
        CAPTCHA_API_KEY,
        CAPTCHA_API_ENVIAR_URL,
        CAPTCHA_API_RESULTADO_URL
    ])


async def enviar_captcha_para_api(
    processo=None,
    caminho_imagem=None,
    sitekey=None,
    url=None
):
    if not api_configurada():
        return {
            "status": "API_NAO_CONFIGURADA",
            "mensagem": "API não configurada",
            "protocolo_api": None,
        }

    pageurl = url or (processo.get("acesso") if processo else None)

    dados = {
        "key": CAPTCHA_API_KEY,
        "method": "userrecaptcha",
        "googlekey": sitekey,
        "pageurl": pageurl,
        "json": "0",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resposta = await client.post(CAPTCHA_API_ENVIAR_URL, data=dados)

    texto = resposta.text.strip()

    print("Resposta envio API:", texto)

    if texto.startswith("OK|"):
        protocolo = texto.split("|")[1]

        return {
            "status": "ENVIADO_API",
            "protocolo_api": protocolo,
        }

    return {
        "status": "ERRO_API_CAPTCHA",
        "mensagem": texto,
    }


async def consultar_resultado_captcha_api(protocolo_api):

    if not api_configurada():
        return {"status": "API_NAO_CONFIGURADA"}

    async with httpx.AsyncClient(timeout=60) as client:
        for tentativa in range(TOTAL_TENTATIVAS_RESULTADO):

            resposta = await client.get(
                CAPTCHA_API_RESULTADO_URL,
                params={
                    "key": CAPTCHA_API_KEY,
                    "action": "get",
                    "id": protocolo_api,
                    "json": "0",
                }
            )

            texto = resposta.text.strip()

            print("Resposta consulta API:", texto)

            if texto == "CAPCHA_NOT_READY":
                await asyncio.sleep(TEMPO_ESPERA_ENTRE_CONSULTAS)
                continue

            if texto.startswith("OK|"):
                return {
                    "status": "RESOLVIDO",
                    "resposta": texto.split("|")[1],
                }

            return {
                "status": "ERRO_API_CAPTCHA",
                "mensagem": texto,
            }

    return {"status": "PENDENTE"}