import asyncio

from database.repositories import buscar_processos_por_orgao
from robots.curitiba.robot import consultar_processo_curitiba


async def main():

    processos = buscar_processos_por_orgao(1)

    for processo in processos:

        print(f"\nConsultando processo: {processo['numero_processo']}")

        await consultar_processo_curitiba(processo)


if __name__ == "__main__":
    asyncio.run(main())