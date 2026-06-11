from database.models import listar_orgaos


def main():

    orgaos = listar_orgaos()

    for orgao in orgaos:
        print(orgao)


if __name__ == "__main__":
    main()