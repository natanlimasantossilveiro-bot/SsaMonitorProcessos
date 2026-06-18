import re
from datetime import datetime


def normalizar_texto(valor):
    if valor is None:
        return ""

    return " ".join(str(valor).strip().split())


def normalizar_numero_processo_atende_net(processo):
    numero = normalizar_texto(
        processo.get("numero_processo")
    )

    if not numero:
        raise ValueError("Número do processo não informado.")

    return numero


def normalizar_exercicio_atende_net(processo):
    exercicio = normalizar_texto(
        processo.get("exercicio")
    )

    if not exercicio:
        raise ValueError(
            "Exercício/Ano do processo não informado."
        )

    return exercicio


def normalizar_codigo_verificador_atende_net(processo):
    codigo = normalizar_texto(
        processo.get("codigo")
    )

    if not codigo:
        raise ValueError(
            "Código verificador do processo não informado."
        )

    return codigo


def montar_dados_consulta_atende_net(processo):
    return {
        "numero": normalizar_numero_processo_atende_net(processo),
        "ano": normalizar_exercicio_atende_net(processo),
        "codigo_verificador": normalizar_codigo_verificador_atende_net(processo),
        "url": normalizar_texto(processo.get("acesso")),
    }


def extrair_dados_resultado_atende_net(conteudo):
    texto = normalizar_texto(conteudo)

    if not texto:
        return {
            "situacao": "SEM_CONTEUDO",
            "ultima_data_movimento": None,
            "ultima_movimentacao": "Nenhum conteúdo retornado pela página.",
            "observacoes": "",
        }

    situacao = extrair_situacao(texto)
    datas = extrair_datas(texto)
    movimentacoes = extrair_movimentacoes(texto)

    ultima_data = datas[-1] if datas else None
    ultima_movimentacao = (
        movimentacoes[-1]
        if movimentacoes
        else "Nenhuma movimentação identificada automaticamente."
    )

    return {
        "situacao": situacao,
        "ultima_data_movimento": ultima_data,
        "ultima_movimentacao": ultima_movimentacao,
        "movimentacoes": movimentacoes,
        "observacoes": texto[:1000],
    }


def extrair_situacao(texto):
    padroes = [
        r"Situação[:\s]+([A-Za-zÀ-ÿ0-9\s\-\/]+)",
        r"Status[:\s]+([A-Za-zÀ-ÿ0-9\s\-\/]+)",
        r"Situação Atual[:\s]+([A-Za-zÀ-ÿ0-9\s\-\/]+)",
    ]

    for padrao in padroes:
        resultado = re.search(
            padrao,
            texto,
            re.IGNORECASE,
        )

        if resultado:
            return normalizar_texto(resultado.group(1))[:150]

    return "NAO_IDENTIFICADA"


def extrair_datas(texto):
    datas_encontradas = re.findall(
        r"\b\d{2}/\d{2}/\d{4}\b",
        texto,
    )

    datas_validas = []

    for data in datas_encontradas:
        try:
            datetime.strptime(data, "%d/%m/%Y")
            datas_validas.append(data)
        except ValueError:
            continue

    return datas_validas


def extrair_movimentacoes(texto):
    partes = re.split(
        r"(?=\b\d{2}/\d{2}/\d{4}\b)",
        texto,
    )

    movimentacoes = []

    for parte in partes:
        parte_limpa = normalizar_texto(parte)

        if not parte_limpa:
            continue

        if re.search(r"\b\d{2}/\d{2}/\d{4}\b", parte_limpa):
            movimentacoes.append(parte_limpa[:500])

    return movimentacoes