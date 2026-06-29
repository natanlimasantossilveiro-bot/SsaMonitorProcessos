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
from utils.evidencias import salvar_evidencia
from utils.logger import get_logger

log = get_logger("curitiba")


def montar_numero_processo_curitiba(processo):
    numero_processo = str(processo.get("numero_processo", "")).strip()
    exercicio = processo.get("exercicio")

    if "/" in numero_processo:
        return numero_processo

    if not exercicio:
        raise ValueError(f"Processo sem exercicio informado: {numero_processo}")

    return f"{numero_processo}/{str(exercicio).strip()}"


async def consultar_processo_curitiba(processo):
    browser = None
    page = None

    try:
        numero_processo_completo = montar_numero_processo_curitiba(processo)
        dados = separar_protocolo_curitiba(numero_processo_completo)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(URL_CURITIBA, wait_until="load")

            await page.fill(CAMPO_TIPO_PROTOCOLO, dados["prefixo"])
            await page.fill(CAMPO_NUMERO_PROTOCOLO, dados["numero"])
            await page.fill(CAMPO_ANO_PROTOCOLO, dados["ano"])

            log.info(f"Formulario preenchido — {numero_processo_completo}")

            # Com headless=True popups exigem expect_popup para serem capturados.
            pagina_resultado = None
            try:
                async with page.expect_popup(timeout=15000) as popup_info:
                    await page.click(BOTAO_PESQUISAR)
                pagina_resultado = await popup_info.value
                await pagina_resultado.wait_for_load_state("load")
            except Exception:
                pass

            # Fallback: percorre context.pages caso o popup ja esteja aberto
            if not pagina_resultado:
                for p2 in page.context.pages:
                    if "frmImprimeProtocolo" in p2.url:
                        pagina_resultado = p2
                        break

            if not pagina_resultado:
                log.warning("Janela de resultado nao localizada")
                evidencia = await salvar_evidencia(
                    page=page,
                    processo=processo,
                    status="PROCESSO_NAO_ENCONTRADO",
                    mensagem="Janela de resultado nao foi localizada.",
                )
                await browser.close()
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": f"Janela de resultado nao foi localizada. Evidencia: {evidencia}",
                    "dados": None,
                }

            conteudo = await pagina_resultado.text_content("body")
            dados_extraidos = extrair_dados_resultado_curitiba(conteudo)

            log.info(f"Dados extraidos: situacao={dados_extraidos.get('situacao')}")

            return {
                "status": "OK",
                "mensagem": "Consulta realizada com sucesso",
                "status_processo": dados_extraidos["situacao"],
                "ultima_data_movimento": dados_extraidos["ultima_data_movimento"],
                "ultima_movimentacao": dados_extraidos["ultima_movimentacao"],
            }

    except Exception as erro:
        mensagem = str(erro)
        log.error(f"Erro na consulta: {mensagem}")

        if page:
            try:
                evidencia = await salvar_evidencia(
                    page=page,
                    processo=processo,
                    status="ERRO_CONSULTA",
                    mensagem=mensagem,
                )
                mensagem = f"{mensagem} | Evidencia: {evidencia}"
            except Exception as erro_ev:
                mensagem = f"{mensagem} | Falha ao salvar evidencia: {erro_ev}"

        if browser:
            await browser.close()

        return {"status": "ERRO_CONSULTA", "mensagem": mensagem, "dados": None}