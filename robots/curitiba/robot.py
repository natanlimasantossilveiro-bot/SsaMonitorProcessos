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

from database.repositories import (
    atualizar_dados_processo,
    registrar_movimentacao,
)


async def consultar_processo_curitiba(processo):

    dados = separar_protocolo_curitiba(
        processo["numero_processo"]
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

        await page.wait_for_timeout(7000)

        print("\n=== TODAS AS PÁGINAS ABERTAS ===\n")

        for indice, pagina in enumerate(
            context.pages,
            start=1
        ):

            titulo = await pagina.title()

            print(f"Página {indice}")
            print(f"Título: {titulo}")
            print(f"URL: {pagina.url}")
            print("-" * 50)

        paginas_depois = context.pages

        novas_paginas = [
            pagina
            for pagina in paginas_depois
            if pagina not in paginas_antes
        ]

        pagina_resultado = None

        for pagina in novas_paginas:

            if "frmImprimeProtocolo" in pagina.url:

                pagina_resultado = pagina

        if not pagina_resultado:

            texto_pagina_principal = await page.text_content(
                "body"
            )

            if texto_pagina_principal and "Este Protocolo não existe" in texto_pagina_principal:

                print("\n=== PROCESSO NÃO ENCONTRADO ===\n")
                print("Este Protocolo não existe.")

            else:

                print("\n=== RESULTADO NÃO LOCALIZADO ===\n")
                print("Nenhuma janela de resultado foi encontrada.")

            await page.wait_for_timeout(5000)
            await browser.close()
            return None

        print("\n=== RESULTADO ENCONTRADO ===\n")

        conteudo = await pagina_resultado.text_content(
            "body"
        )

        dados_extraidos = extrair_dados_resultado_curitiba(
            conteudo
        )

        print("\n=== DADOS EXTRAÍDOS ===\n")
        print(dados_extraidos)

        atualizar_dados_processo(
            processo_id=processo["id"],
            status_atual=dados_extraidos["situacao"],
            data_ultimo_movimento=dados_extraidos["ultima_data_movimento"],
            ultima_movimentacao=dados_extraidos["ultima_movimentacao"],
        )

        registrar_movimentacao(
            processo_id=processo["id"],
            data_movimento=dados_extraidos["ultima_data_movimento"],
            descricao=dados_extraidos["ultima_movimentacao"],
        )

        print("\nDados salvos no banco com sucesso.")

        await page.wait_for_timeout(10000)

        await browser.close()

        return dados_extraidos