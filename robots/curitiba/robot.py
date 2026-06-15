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

from utils.evidencias import salvar_evidencia


def montar_numero_processo_curitiba(processo):
    numero_processo = str(processo.get("numero_processo", "")).strip()
    exercicio = processo.get("exercicio")

    if "/" in numero_processo:
        return numero_processo

    if not exercicio:
        raise ValueError(
            f"Processo Curitiba sem exercício informado: {numero_processo}"
        )

    exercicio = str(exercicio).strip()

    return f"{numero_processo}/{exercicio}"


async def consultar_processo_curitiba(processo):
    browser = None
    page = None

    try:
        numero_processo_completo = montar_numero_processo_curitiba(processo)

        dados = separar_protocolo_curitiba(
            numero_processo_completo
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

            await page.fill(CAMPO_TIPO_PROTOCOLO, dados["prefixo"])
            await page.fill(CAMPO_NUMERO_PROTOCOLO, dados["numero"])
            await page.fill(CAMPO_ANO_PROTOCOLO, dados["ano"])

            print("Campos preenchidos com sucesso.")

            context = page.context

            await page.click(BOTAO_PESQUISAR)

            print("Pesquisa realizada.")

            await page.wait_for_timeout(7000)

            pagina_resultado = None

            for pagina in context.pages:
                if "frmImprimeProtocolo" in pagina.url:
                    pagina_resultado = pagina

            if not pagina_resultado:
                print("\n=== RESULTADO NÃO LOCALIZADO ===")

                evidencia = await salvar_evidencia(
                    page=page,
                    processo=processo,
                    status="PROCESSO_NAO_ENCONTRADO",
                    mensagem="Janela de resultado não foi localizada.",
                )

                await browser.close()

                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": f"Janela de resultado não foi localizada. Evidência: {evidencia}",
                    "dados": None,
                }

            conteudo = await pagina_resultado.text_content("body")

            dados_extraidos = extrair_dados_resultado_curitiba(
                conteudo
            )

            print("\n=== DADOS EXTRAÍDOS ===")
            print(dados_extraidos)

            atualizar_dados_processo(
                processo_id=processo["id"],
                status_atual=dados_extraidos["situacao"],
                data_ultimo_movimento=dados_extraidos["ultima_data_movimento"],
                ultima_movimentacao=dados_extraidos["ultima_movimentacao"],
            )

            movimentacao_nova = registrar_movimentacao(
                processo_id=processo["id"],
                data_movimento=dados_extraidos["ultima_data_movimento"],
                descricao=dados_extraidos["ultima_movimentacao"],
            )

            if movimentacao_nova:
                print("\n🚨 NOVA MOVIMENTAÇÃO DETECTADA E REGISTRADA.")
                status = "NOVA_MOVIMENTACAO"
                mensagem = "Nova movimentação detectada e registrada."

            else:
                print("\n✅ Sem nova movimentação. Registro já existia.")
                status = "SEM_NOVA_MOVIMENTACAO"
                mensagem = "Movimentação já existia no banco."

            await page.wait_for_timeout(3000)

            await browser.close()

            return {
                "status": status,
                "mensagem": mensagem,
                "dados": dados_extraidos,
            }

    except Exception as erro:
        mensagem = str(erro)

        if page:
            try:
                evidencia = await salvar_evidencia(
                    page=page,
                    processo=processo,
                    status="ERRO_CONSULTA",
                    mensagem=mensagem,
                )

                mensagem = f"{mensagem} | Evidência: {evidencia}"

            except Exception as erro_evidencia:
                mensagem = f"{mensagem} | Falha ao salvar evidência: {erro_evidencia}"

        if browser:
            await browser.close()

        return {
            "status": "ERRO_CONSULTA",
            "mensagem": mensagem,
            "dados": None,
        }