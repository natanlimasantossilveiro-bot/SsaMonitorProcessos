import os
import json
from datetime import datetime


PASTA_CAPTCHAS = "captchas"
PASTA_PENDENTES = os.path.join(PASTA_CAPTCHAS, "pendentes")
PASTA_RESOLVIDOS = os.path.join(PASTA_CAPTCHAS, "resolvidos")
PASTA_PROCESSADOS = os.path.join(PASTA_CAPTCHAS, "processados")


def criar_pastas_captcha():
    os.makedirs(PASTA_PENDENTES, exist_ok=True)
    os.makedirs(PASTA_RESOLVIDOS, exist_ok=True)
    os.makedirs(PASTA_PROCESSADOS, exist_ok=True)


def limpar_nome_arquivo(texto):
    texto = str(texto)
    caracteres_invalidos = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']

    for caractere in caracteres_invalidos:
        texto = texto.replace(caractere, "_")

    return texto


def gerar_nome_arquivo_captcha(processo):
    processo_id = processo.get("id", "sem_id")
    numero = limpar_nome_arquivo(
        processo.get("numero_processo", "sem_numero")
    )
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"captcha_processo_{processo_id}_{numero}_{agora}.json"


def criar_solicitacao_captcha(
    processo,
    caminho_imagem=None,
):
    criar_pastas_captcha()

    nome_arquivo = gerar_nome_arquivo_captcha(processo)
    caminho_arquivo = os.path.join(PASTA_PENDENTES, nome_arquivo)

    dados = {
        "status": "PENDENTE",
        "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "processo": {
            "id": processo.get("id"),
            "numero_processo": processo.get("numero_processo"),
            "empresa": processo.get("empresa"),
            "municipio": processo.get("municipio"),
            "orgao": processo.get("nome_orgao"),
            "acesso": processo.get("acesso"),
        },
        "captcha": {
            "caminho_imagem": caminho_imagem,
            "resposta": None,
        },
    }

    with open(caminho_arquivo, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)

    return caminho_arquivo


async def solicitar_resolucao_captcha(
    processo,
    caminho_imagem=None,
):
    print("\n=== CAPTCHA DETECTADO ===")
    print(f"Processo: {processo.get('numero_processo')}")

    if caminho_imagem:
        print(f"Imagem do captcha: {caminho_imagem}")

    caminho_solicitacao = criar_solicitacao_captcha(
        processo=processo,
        caminho_imagem=caminho_imagem,
    )

    print(f"Solicitação de captcha criada: {caminho_solicitacao}")

    return {
        "status": "PENDENTE_INTEGRACAO_CAPTCHA",
        "mensagem": (
            "Captcha detectado. Solicitação criada para futura integração "
            f"com API: {caminho_solicitacao}"
        ),
        "resposta": None,
        "caminho_solicitacao": caminho_solicitacao,
    }