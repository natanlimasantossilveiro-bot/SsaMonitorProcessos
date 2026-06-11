from database.repositories import cadastrar_processo, listar_processos_ativos


def main():

    processo_id = cadastrar_processo(
        orgao_id=1,
        numero_processo="01-828832/2012",
        cliente="TESTE CURITIBA"
    )

    print(f"Processo cadastrado com ID: {processo_id}")

    processos = listar_processos_ativos()

    for processo in processos:
        print(processo)


if __name__ == "__main__":
    main()