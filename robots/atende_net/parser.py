def normalizar_numero_processo_atende_net(processo):
    numero = str(processo.get("numero_processo", "")).strip()

    if not numero:
        raise ValueError("Número do processo não informado.")

    return numero


def extrair_dados_resultado_atende_net(conteudo):
    return {
        "situacao": "PENDENTE_PARSER",
        "ultima_data_movimento": None,
        "ultima_movimentacao": "Parser Atende.Net ainda não implementado.",
        "observacoes": conteudo[:500] if conteudo else "",
    }