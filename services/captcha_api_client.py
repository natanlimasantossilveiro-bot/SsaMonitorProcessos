import os
import asyncio
import httpx

from dotenv import load_dotenv
from utils.logger import get_logger

load_dotenv()

log = get_logger("2captcha")

CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY")
CAPTCHA_API_ENVIAR_URL = os.getenv("CAPTCHA_API_ENVIAR_URL")
CAPTCHA_API_RESULTADO_URL = os.getenv("CAPTCHA_API_RESULTADO_URL")

TEMPO_ESPERA_ENTRE_CONSULTAS = 5
TOTAL_TENTATIVAS_RESULTADO = 24


def api_configurada():
    return all([CAPTCHA_API_KEY, CAPTCHA_API_ENVIAR_URL, CAPTCHA_API_RESULTADO_URL])


async def enviar_captcha_para_api(processo=None, caminho_imagem=None, sitekey=None, url=None, method="userrecaptcha"):
    if not api_configurada():
        log.warning("API de captcha nao configurada — verifique as variaveis de ambiente")
        return {
            "status": "API_NAO_CONFIGURADA",
            "mensagem": "API nao configurada",
            "protocolo_api": None,
        }

    pageurl = url or (processo.get("acesso") if processo else None)

    if method == "turnstile":
        dados = {
            "key": CAPTCHA_API_KEY,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": pageurl,
            "json": "0",
        }
    else:
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
    log.debug(f"Resposta envio: {texto[:80]}")

    if texto.startswith("OK|"):
        protocolo = texto.split("|")[1]
        log.info(f"Captcha enviado — protocolo: {protocolo}")
        return {"status": "ENVIADO_API", "protocolo_api": protocolo}

    log.error(f"Erro ao enviar captcha: {texto}")
    return {"status": "ERRO_API_CAPTCHA", "mensagem": texto}


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
                },
            )

            texto = resposta.text.strip()

            if texto == "CAPCHA_NOT_READY":
                log.debug(f"Captcha ainda nao resolvido — tentativa {tentativa + 1}/{TOTAL_TENTATIVAS_RESULTADO}")
                await asyncio.sleep(TEMPO_ESPERA_ENTRE_CONSULTAS)
                continue

            if texto.startswith("OK|"):
                log.info("Captcha resolvido pela API")
                return {"status": "RESOLVIDO", "resposta": texto.split("|")[1]}

            log.error(f"Erro na consulta do captcha: {texto}")
            return {"status": "ERRO_API_CAPTCHA", "mensagem": texto}

    log.warning(f"Timeout: captcha nao foi resolvido em {TOTAL_TENTATIVAS_RESULTADO} tentativas")
    return {"status": "PENDENTE"}