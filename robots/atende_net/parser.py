def normalizar_texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


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
    return {
        "situacao": "PENDENTE_PARSER",
        "ultima_data_movimento": None,
        "ultima_movimentacao": "Parser Atende.Net ainda não implementado.",
        "observacoes": conteudo[:500] if conteudo else "",
    }