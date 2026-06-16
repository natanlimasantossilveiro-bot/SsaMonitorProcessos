async def solicitar_resolucao_captcha(
    processo,
    caminho_imagem=None,
):
    print("\n=== CAPTCHA DETECTADO ===")
    print(f"Processo: {processo.get('numero_processo')}")

    if caminho_imagem:
        print(f"Imagem do captcha: {caminho_imagem}")

    return {
        "status": "PENDENTE_INTEGRACAO_CAPTCHA",
        "mensagem": "Captcha detectado. Integração com API ainda será implementada.",
        "resposta": None,
    }