from database.repositories import (
    buscar_processos_por_orgao
)

from robots.curitiba.robot import (
    consultar_processo
)


def main():

    processos = buscar_processos_por_orgao(1)

    for processo in processos:

        consultar_processo(
            processo
        )


if __name__ == "__main__":
    main()