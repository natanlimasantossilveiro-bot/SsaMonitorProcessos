import asyncio

from robots.curitiba.robot import abrir_pagina_curitiba


async def main():

    await abrir_pagina_curitiba()


if __name__ == "__main__":
    asyncio.run(main())