import re


def separar_protocolo_curitiba(protocolo_completo):
    """
    Separa o protocolo da Prefeitura de Curitiba.

    Exemplo:
    Entrada: 01-828832/2012

    Saída:
    {
        "prefixo": "01",
        "numero": "828832",
        "ano": "2012"
    }
    """

    padrao = r"^(\d{2})-(\d+)\/(\d{4})$"

    resultado = re.match(padrao, protocolo_completo.strip())

    if not resultado:
        raise ValueError("Protocolo inválido. Use o formato correto: 01-828832/2012")

    prefixo = resultado.group(1)
    numero = resultado.group(2)
    ano = resultado.group(3)

    return {
        "prefixo": prefixo,
        "numero": numero,
        "ano": ano,
    }


def extrair_dados_resultado_curitiba(texto):
    """
    Extrai os principais dados da página de resultado
    da consulta de protocolo da Prefeitura de Curitiba.
    """

    linhas = [
        linha.strip()
        for linha in texto.splitlines()
        if linha.strip()
    ]

    dados = {
        "protocolo": None,
        "data_cadastro": None,
        "situacao": None,
        "ultima_data_movimento": None,
        "ultima_movimentacao": None,
        "observacoes": None,
    }

    if "PROTOCOLO Nº" in linhas:
        indice = linhas.index("PROTOCOLO Nº")
        if indice + 1 < len(linhas):
            dados["protocolo"] = linhas[indice + 1]

    if "Protocolo Cad. em:" in linhas:
        indice = linhas.index("Protocolo Cad. em:")
        if indice + 4 < len(linhas):
            dados["data_cadastro"] = linhas[indice + 4]

    if "Situação:" in linhas:
        indice = linhas.index("Situação:")
        if indice + 4 < len(linhas):
            dados["situacao"] = linhas[indice + 4]

    if "Em:" in linhas:
        indice = linhas.index("Em:")
        if indice + 5 < len(linhas):
            dados["ultima_data_movimento"] = linhas[indice + 5]

    if "Para Unidade:" in linhas:
        indice = linhas.index("Para Unidade:")
        if indice + 5 < len(linhas):
            dados["ultima_movimentacao"] = linhas[indice + 5]

    if "Observações:" in linhas:
        indice = linhas.index("Observações:")
        if indice + 1 < len(linhas):
            dados["observacoes"] = linhas[indice + 1]

    return dados


def extrair_dados_resultado_curitiba(texto):
    """
    Extrai os principais dados da página de resultado
    da consulta de protocolo da Prefeitura de Curitiba.
    """

    linhas = [
        linha.strip()
        for linha in texto.splitlines()
        if linha.strip()
    ]

    dados = {
        "protocolo": None,
        "data_cadastro": None,
        "situacao": None,
        "ultima_data_movimento": None,
        "ultima_movimentacao": None,
        "observacoes": None,
        "assunto": None,
    }

    if "PROTOCOLO Nº" in linhas:
        indice = linhas.index("PROTOCOLO Nº")

        if indice + 1 < len(linhas):
            dados["protocolo"] = linhas[indice + 1]

    if "Protocolo Cad. em:" in linhas:
        indice = linhas.index("Protocolo Cad. em:")

        if indice + 4 < len(linhas):
            dados["data_cadastro"] = linhas[indice + 4]

    if "Situação:" in linhas:
        indice = linhas.index("Situação:")

        if indice + 4 < len(linhas):
            dados["situacao"] = linhas[indice + 4]

    if "Em:" in linhas:
        indice = linhas.index("Em:")

        if indice + 5 < len(linhas):
            dados["ultima_data_movimento"] = linhas[indice + 5]

    if "Para Unidade:" in linhas:
        indice = linhas.index("Para Unidade:")

        if indice + 5 < len(linhas):
            dados["ultima_movimentacao"] = linhas[indice + 5]

    if "Observações:" in linhas:
        indice = linhas.index("Observações:")

        if indice + 1 < len(linhas):
            dados["observacoes"] = linhas[indice + 1]

    for label in ("Assunto:", "Objeto:", "Descrição:"):
        if label in linhas:
            indice = linhas.index(label)
            if indice + 1 < len(linhas):
                dados["assunto"] = linhas[indice + 1]
            break

    return dados


if __name__ == "__main__":

    print(separar_protocolo_curitiba("01-828832/2012"))

    print(separar_protocolo_curitiba("01-131243/2020"))

    print(separar_protocolo_curitiba("01-999999/2026"))