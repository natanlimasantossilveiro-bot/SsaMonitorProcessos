import os


CAPTCHA_API_URL = os.getenv("CAPTCHA_API_URL")
CAPTCHA_API_TOKEN = os.getenv("CAPTCHA_API_TOKEN")


async def enviar_captcha_para_api(
    processo,
    caminho_imagem,
):
    """
    Cliente preparado para futura API de resolução de captcha.

    Por enquanto, não envia nada de verdade.
    Quando a API existir, vamos implementar aqui:
    - POST para API
    - envio da imagem
    - envio dos dados do processo
    - retorno do protocolo/id da solicitação
    """

    if not CAPTCHA_API_URL:
        return {
            "status": "API_NAO_CONFIGURADA",
            "mensagem": "API de captcha ainda não configurada no .env.",
            "protocolo_api": None,
        }

    return {
        "status": "PENDENTE_IMPLEMENTACAO",
        "mensagem": "Cliente da API criado, mas integração HTTP ainda não implementada.",
        "protocolo_api": None,
    }