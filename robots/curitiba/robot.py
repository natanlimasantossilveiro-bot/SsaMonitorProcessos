from playwright.async_api import async_playwright

from robots.curitiba.parser import separar_protocolo_curitiba
from robots.curitiba.selectors import URL_CURITIBA


async def abrir_pagina_curitiba():
    """
    Abre a página de consulta de protocolo da Prefeitura de Curitiba.
    Nesta etapa, apenas validamos se o site carrega corretamente.
    """

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False
        )

        page = await browser.new_page()

        await page.goto(
            URL_CURITIBA,
            wait_until="load"
        )

        titulo = await page.title()

        print("=== PÁGINA CURITIBA ===")
        print(f"Título da página: {titulo}")

        await page.wait_for_timeout(5000)

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