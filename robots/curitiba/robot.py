from robots.curitiba.parser import separar_protocolo_curitiba


def consultar_processo(processo):

    protocolo = processo["numero_processo"]

    dados = separar_protocolo_curitiba(
        protocolo
    )

    print("=== DADOS EXTRAÍDOS ===")
    print(dados)

    return dados