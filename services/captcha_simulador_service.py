import os
import json

from services.captcha_service import (
    PASTA_PENDENTES,
    PASTA_RESOLVIDOS,
    criar_pastas_captcha,
)


def simular_resposta_captcha():
    criar_pastas_captcha()

    arquivos = [
        arquivo
        for arquivo in os.listdir(PASTA_PENDENTES)
        if arquivo.endswith(".json")
    ]

    if not arquivos:
        print("\nNenhum captcha pendente encontrado.")
        return

    print("\n=== CAPTCHAS PENDENTES ===")

    for indice, arquivo in enumerate(arquivos, start=1):
        print(f"{indice} - {arquivo}")

    escolha = input("\nEscolha o captcha para simular a resolução: ").strip()

    if not escolha.isdigit():
        print("Opção inválida.")
        return

    indice = int(escolha)

    if indice < 1 or indice > len(arquivos):
        print("Captcha não encontrado.")
        return

    nome_arquivo = arquivos[indice - 1]

    resposta = input("\nDigite a resposta simulada do captcha: ").strip()

    if not resposta:
        print("Resposta vazia. Operação cancelada.")
        return

    caminho_origem = os.path.join(PASTA_PENDENTES, nome_arquivo)

    with open(caminho_origem, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    dados["status"] = "RESOLVIDO"
    dados["captcha"]["resposta"] = resposta

    caminho_destino = os.path.join(PASTA_RESOLVIDOS, nome_arquivo)

    with open(caminho_destino, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)

    print("\n✅ Captcha resolvido com sucesso.")
    print(f"Arquivo criado em: {caminho_destino}")