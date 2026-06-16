import os
import json
import shutil
from datetime import datetime

from services.captcha_api_client import enviar_captcha_para_api


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


def obter_nome_arquivo(caminho_arquivo):
    return os.path.basename(caminho_arquivo)


def obter_caminho_resolvido(caminho_solicitacao):
    nome_arquivo = obter_nome_arquivo(caminho_solicitacao)
    return os.path.join(PASTA_RESOLVIDOS, nome_arquivo)


def obter_caminho_processado(caminho_solicitacao):
    nome_arquivo = obter_nome_arquivo(caminho_solicitacao)
    return os.path.join(PASTA_PROCESSADOS, nome_arquivo)


def ler_json(caminho_arquivo):
    with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_json(caminho_arquivo, dados):
    with open(caminho_arquivo, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def buscar_resposta_captcha_resolvido(caminho_solicitacao):
    criar_pastas_captcha()

    caminho_resolvido = obter_caminho_resolvido(caminho_solicitacao)

    if not os.path.exists(caminho_resolvido):
        return {
            "status": "PENDENTE",
            "mensagem": "Captcha ainda não foi resolvido.",
            "resposta": None,
            "caminho_resolvido": caminho_resolvido,
        }

    dados_resolvidos = ler_json(caminho_resolvido)

    resposta = (
        dados_resolvidos
        .get("captcha", {})
        .get("resposta")
    )

    if not resposta:
        return {
            "status": "RESOLVIDO_SEM_RESPOSTA",
            "mensagem": "Arquivo resolvido encontrado, mas sem resposta do captcha.",
            "resposta": None,
            "caminho_resolvido": caminho_resolvido,
        }

    caminho_processado = obter_caminho_processado(caminho_solicitacao)

    dados_resolvidos["status"] = "PROCESSADO"
    dados_resolvidos["processado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    salvar_json(caminho_resolvido, dados_resolvidos)

    shutil.move(caminho_resolvido, caminho_processado)

    if os.path.exists(caminho_solicitacao):
        os.remove(caminho_solicitacao)

    return {
        "status": "RESOLVIDO",
        "mensagem": "Captcha resolvido e movido para processados.",
        "resposta": resposta,
        "caminho_processado": caminho_processado,
    }


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

    resultado_api = await enviar_captcha_para_api(
        processo=processo,
        caminho_imagem=caminho_imagem,
    )

    dados_solicitacao = ler_json(caminho_solicitacao)

    dados_solicitacao["api"] = {
        "status": resultado_api.get("status"),
        "mensagem": resultado_api.get("mensagem"),
        "protocolo_api": resultado_api.get("protocolo_api"),
        "enviado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }

    salvar_json(caminho_solicitacao, dados_solicitacao)

    return {
        "status": "PENDENTE_INTEGRACAO_CAPTCHA",
        "mensagem": (
            "Captcha detectado. Solicitação criada e tentativa de envio "
            f"para API registrada: {caminho_solicitacao}"
        ),
        "resposta": None,
        "caminho_solicitacao": caminho_solicitacao,
        "api": resultado_api,
    }