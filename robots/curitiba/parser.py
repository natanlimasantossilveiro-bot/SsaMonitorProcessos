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


if __name__ == "__main__":

    print(separar_protocolo_curitiba("01-828832/2012"))

    print(separar_protocolo_curitiba("01-131243/2020"))

    print(separar_protocolo_curitiba("01-999999/2026"))