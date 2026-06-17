import os
import json
import shutil
from datetime import datetime

from services.captcha_api_client import (
    enviar_captcha_para_api,
    consultar_resultado_captcha_api,
)


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


def extrair_resposta_manual(dados_resolvidos):
    return (
        dados_resolvidos
        .get("captcha", {})
        .get("resposta")
    )


def extrair_protocolo_api(dados_solicitacao):
    return (
        dados_solicitacao
        .get("api", {})
        .get("protocolo_api")
    )


def montar_retorno_pendente(caminho_resolvido):
    return {
        "status": "PENDENTE",
        "mensagem": "Captcha ainda não foi resolvido.",
        "resposta": None,
        "caminho_resolvido": caminho_resolvido,
    }


def finalizar_captcha_resolvido(
    caminho_solicitacao,
    dados_resolvidos,
    resposta,
):
    caminho_processado = obter_caminho_processado(caminho_solicitacao)

    dados_resolvidos["status"] = "PROCESSADO"
    dados_resolvidos["processado_em"] = datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    dados_resolvidos.setdefault("captcha", {})
    dados_resolvidos["captcha"]["resposta"] = resposta

    salvar_json(caminho_solicitacao, dados_resolvidos)

    shutil.move(caminho_solicitacao, caminho_processado)

    return {
        "status": "RESOLVIDO",
        "mensagem": "Captcha resolvido e movido para processados.",
        "resposta": resposta,
        "caminho_processado": caminho_processado,
    }


def buscar_resposta_manual_resolvida(caminho_solicitacao):
    caminho_resolvido = obter_caminho_resolvido(caminho_solicitacao)

    if not os.path.exists(caminho_resolvido):
        return None

    dados_resolvidos = ler_json(caminho_resolvido)
    resposta = extrair_resposta_manual(dados_resolvidos)

    if not resposta:
        return {
            "status": "RESOLVIDO_SEM_RESPOSTA",
            "mensagem": (
                "Arquivo resolvido encontrado, mas sem resposta do captcha."
            ),
            "resposta": None,
            "caminho_resolvido": caminho_resolvido,
        }

    caminho_processado = obter_caminho_processado(caminho_solicitacao)

    dados_resolvidos["status"] = "PROCESSADO"
    dados_resolvidos["processado_em"] = datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

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


async def buscar_resposta_captcha_resolvido(caminho_solicitacao):
    criar_pastas_captcha()

    resultado_manual = buscar_resposta_manual_resolvida(
        caminho_solicitacao
    )

    if resultado_manual:
        return resultado_manual

    caminho_resolvido = obter_caminho_resolvido(caminho_solicitacao)

    if not os.path.exists(caminho_solicitacao):
        return montar_retorno_pendente(caminho_resolvido)

    dados_solicitacao = ler_json(caminho_solicitacao)

    protocolo_api = extrair_protocolo_api(dados_solicitacao)

    if not protocolo_api:
        return montar_retorno_pendente(caminho_resolvido)

    resultado_api = await consultar_resultado_captcha_api(protocolo_api)

    dados_solicitacao.setdefault("api", {})
    dados_solicitacao["api"]["ultimo_status_resultado"] = resultado_api.get(
        "status"
    )
    dados_solicitacao["api"]["ultima_mensagem_resultado"] = resultado_api.get(
        "mensagem"
    )
    dados_solicitacao["api"]["consultado_em"] = datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    salvar_json(caminho_solicitacao, dados_solicitacao)

    if resultado_api.get("status") != "RESOLVIDO":
        return {
            "status": "PENDENTE",
            "mensagem": resultado_api.get(
                "mensagem",
                "Captcha ainda não foi resolvido pela API.",
            ),
            "resposta": None,
            "caminho_resolvido": caminho_resolvido,
        }

    resposta = resultado_api.get("resposta")

    dados_solicitacao.setdefault("captcha", {})
    dados_solicitacao["captcha"]["resposta"] = resposta

    return finalizar_captcha_resolvido(
        caminho_solicitacao=caminho_solicitacao,
        dados_resolvidos=dados_solicitacao,
        resposta=resposta,
    )


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