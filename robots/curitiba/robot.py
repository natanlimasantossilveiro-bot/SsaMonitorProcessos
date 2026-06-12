from playwright.async_api import async_playwright

from robots.curitiba.parser import (
    separar_protocolo_curitiba,
    extrair_dados_resultado_curitiba,
)

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

        print("Campos preenchidos com sucesso.")

        context = page.context

        paginas_antes = context.pages.copy()

        await page.click(
            BOTAO_PESQUISAR
        )

        print("Pesquisa realizada.")

        await page.wait_for_timeout(5000)

        paginas_depois = context.pages

        novas_paginas = [
            pagina
            for pagina in paginas_depois
            if pagina not in paginas_antes
        ]

        print("\n=== JANELAS ABERTAS ===\n")

        pagina_resultado = None

        for indice, pagina in enumerate(
            novas_paginas,
            start=1
        ):

            titulo = await pagina.title()

            print(f"Janela {indice}")
            print(f"Título: {titulo}")
            print(f"URL: {pagina.url}")
            print("-" * 50)

            if "frmImprimeProtocolo" in pagina.url:

                pagina_resultado = pagina

        if pagina_resultado:

            print("\n=== RESULTADO ENCONTRADO ===\n")

            conteudo = await pagina_resultado.text_content(
                "body"
            )

            dados_extraidos = extrair_dados_resultado_curitiba(
                conteudo
            )

            print("\n=== DADOS EXTRAÍDOS ===\n")
            print(dados_extraidos)

        await page.wait_for_timeout(15000)

        await browser.close()