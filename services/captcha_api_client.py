import os
import httpx


CAPTCHA_API_URL = os.getenv("CAPTCHA_API_URL")
CAPTCHA_API_TOKEN = os.getenv("CAPTCHA_API_TOKEN")


async def enviar_captcha_para_api(processo, caminho_imagem):
    if not CAPTCHA_API_URL:
        return {
            "status": "API_NAO_CONFIGURADA",
            "mensagem": "API de captcha ainda não configurada no .env.",
            "protocolo_api": None,
        }

    headers = {}

    if CAPTCHA_API_TOKEN:
        headers["Authorization"] = f"Bearer {CAPTCHA_API_TOKEN}"

    dados = {
        "processo_id": processo.get("id"),
        "numero_processo": processo.get("numero_processo"),
        "empresa": processo.get("empresa"),
        "municipio": processo.get("municipio"),
        "orgao": processo.get("nome_orgao"),
    }

    try:
        with open(caminho_imagem, "rb") as imagem:
            arquivos = {
                "captcha": imagem,
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resposta = await client.post(
                    CAPTCHA_API_URL,
                    data=dados,
                    files=arquivos,
                    headers=headers,
                )

        resposta.raise_for_status()
        dados_resposta = resposta.json()

        return {
            "status": "ENVIADO_API",
            "mensagem": "Captcha enviado para API com sucesso.",
            "protocolo_api": dados_resposta.get("protocolo")
            or dados_resposta.get("id")
            or dados_resposta.get("protocolo_api"),
        }

    except Exception as erro:
        return {
            "status": "ERRO_API_CAPTCHA",
            "mensagem": f"Erro ao enviar captcha para API: {erro}",
            "protocolo_api": None,
        }