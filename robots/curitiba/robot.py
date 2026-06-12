from playwright.async_api import async_playwright

from robots.curitiba.parser import separar_protocolo_curitiba
from robots.curitiba.selectors import (
    URL_CURITIBA,
    CAMPO_TIPO_PROTOCOLO,
    CAMPO_NUMERO_PROTOCOLO,
    CAMPO_ANO_PROTOCOLO,
    BOTAO_PESQUISAR,
)


async def abrir_pagina_curitiba():

    dados = separar_protocolo_curitiba(
        "01-144125/2026"
    )

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False
        )

        page = await browser.new_page()

        await page.goto(
            URL_CURITIBA,
            wait_until="load"
        )

        await page.fill(
            CAMPO_TIPO_PROTOCOLO,
            dados["prefixo"]
        )

        await page.fill(
            CAMPO_NUMERO_PROTOCOLO,
            dados["numero"]
        )

        await page.fill(
            CAMPO_ANO_PROTOCOLO,
            dados["ano"]
        )

        await page.click(
            BOTAO_PESQUISAR
        )

        print("Pesquisa realizada.")

        print("Campos preenchidos com sucesso.")

        await page.wait_for_timeout(15000)

        await browser.close()


def consultar_processo(processo):
    """
    Prepara os dados do processo de Curitiba para consulta.
    """

    protocolo = processo["numero_processo"]

    dados_protocolo = separar_protocolo_curitiba(
        protocolo
    )

    print("=== CONSULTA CURITIBA ===")
    print(f"Processo ID: {processo['id']}")
    print(f"Cliente: {processo['cliente']}")
    print(f"Protocolo completo: {protocolo}")
    print(f"Prefixo: {dados_protocolo['prefixo']}")
    print(f"Número: {dados_protocolo['numero']}")
    print(f"Ano: {dados_protocolo['ano']}")

    return dados_protocolo