from database.repositories import buscar_processos_por_orgao


def main():

    processos = buscar_processos_por_orgao(1)

    for processo in processos:
        print(processo)


if __name__ == "__main__":
    main()