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


def extrair_dados_resultado_atende_net(dados_tela):
    campos = dados_tela.get("campos", {})
    texto = normalizar_texto(dados_tela.get("texto", ""))

    situacao = normalizar_texto(
        campos.get("situacao_atual")
    )

    if not situacao:
        situacao = extrair_situacao(texto)

    data_abertura = normalizar_texto(
        campos.get("data_abertura")
    )

    previsao = normalizar_texto(
        campos.get("previsao")
    )

    observacao = normalizar_texto(
        campos.get("observacao_abertura")
    )

    datas = extrair_datas(texto)

    ultima_data = datas[-1] if datas else data_abertura

    ultima_movimentacao = (
        observacao
        if observacao
        else "Nenhuma movimentação identificada automaticamente."
    )

    return {
        "situacao": situacao,
        "ultima_data_movimento": ultima_data,
        "ultima_movimentacao": ultima_movimentacao,
        "movimentacoes": [],
        "observacoes": observacao,
        "dados_atende_net": {
            "numero_ano": normalizar_texto(campos.get("numero_ano")),
            "codigo_verificador": normalizar_texto(
                campos.get("codigo_verificador")
            ),
            "data_abertura": data_abertura,
            "previsao": previsao,
            "assunto": normalizar_texto(campos.get("assunto")),
            "subassunto": normalizar_texto(campos.get("subassunto")),
            "tipo": normalizar_texto(campos.get("tipo")),
            "requerente": normalizar_texto(campos.get("requerente")),
            "responsavel": normalizar_texto(campos.get("responsavel")),
            "observacao_abertura": observacao,
        },
        "texto_extraido": texto[:3000],
    }


def extrair_situacao(texto):
    padroes = [
        r"Situação Atual[:\s]+([A-Za-zÀ-ÿ0-9\s\-\/]+)",
        r"Situação[:\s]+([A-Za-zÀ-ÿ0-9\s\-\/]+)",
        r"Status[:\s]+([A-Za-zÀ-ÿ0-9\s\-\/]+)",
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