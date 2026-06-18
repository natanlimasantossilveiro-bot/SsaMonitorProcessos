import os
from datetime import datetime

from playwright.async_api import async_playwright

from robots.base.robot_base import RobotBase

from robots.atende_net.parser import (
    montar_dados_consulta_atende_net,
    extrair_dados_resultado_atende_net,
)


class RobotAtendeNet(RobotBase):

    async def consultar_processo(self, processo):
        dados_consulta = montar_dados_consulta_atende_net(processo)

        print("\n=== ROBÔ ATENDE.NET ===")
        print(f"Processo: {dados_consulta['numero']}")
        print(f"Ano: {dados_consulta['ano']}")
        print(f"Código verificador: {dados_consulta['codigo_verificador']}")
        print(f"Empresa: {processo.get('empresa')}")
        print(f"Município: {processo.get('municipio')}")
        print(f"Acesso: {dados_consulta['url']}")

        return await executar_consulta_atende_net(
            dados_consulta=dados_consulta,
            processo=processo,
        )


async def executar_consulta_atende_net(dados_consulta, processo):
    print("\n=== CONSULTA ATENDE.NET ===")
    print(f"Processo: {dados_consulta['numero']}")
    print(f"Ano: {dados_consulta['ano']}")
    print(f"Código verificador: {dados_consulta['codigo_verificador']}")

    caminho_evidencia_resultado = gerar_caminho_evidencia_resultado(processo)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False
        )

        page = await browser.new_page(
            viewport={
                "width": 1280,
                "height": 1000,
            }
        )

        await page.goto(
            dados_consulta["url"],
            wait_until="networkidle",
        )

        await aceitar_cookies_se_existir(page)

        print("\n=== VERIFICAÇÃO DE CAPTCHA ===")
        print("Resolva o reCAPTCHA manualmente na janela aberta.")
        print("Depois que o formulário aparecer, volte ao terminal.")

        input("Pressione ENTER após resolver o reCAPTCHA...")

        await page.wait_for_timeout(2000)

        await salvar_html_debug(page)

        print("\nPreenchendo formulário dentro do iframe...")

        await preencher_formulario_iframe(
            page=page,
            numero=dados_consulta["numero"],
            ano=dados_consulta["ano"],
            codigo_verificador=dados_consulta["codigo_verificador"],
        )

        await page.wait_for_timeout(1000)

        print("Clicando em Confirmar...")

        await clicar_confirmar_iframe(page)

        await page.wait_for_timeout(5000)

        await page.screenshot(
            path=caminho_evidencia_resultado,
            full_page=True,
        )

        print(
            f"Evidência do resultado salva em: "
            f"{caminho_evidencia_resultado}"
        )

        print("\nExtraindo dados da tela de resultado...")

        dados_tela = await extrair_dados_tela_resultado(page)
        dados_resultado = extrair_dados_resultado_atende_net(dados_tela)

        print("\n=== DADOS EXTRAÍDOS ATENDE.NET ===")
        print(f"Situação: {dados_resultado.get('situacao')}")
        print(
            "Última data movimento: "
            f"{dados_resultado.get('ultima_data_movimento')}"
        )
        print(
            "Última movimentação: "
            f"{dados_resultado.get('ultima_movimentacao')}"
        )
        print(f"Dados Atende.Net: {dados_resultado.get('dados_atende_net')}")

        await browser.close()

    return {
        "status": "ATENDE_NET_CONSULTA_EXECUTADA",
        "mensagem": (
            "Consulta Atende.Net executada e dados iniciais extraídos."
        ),
        "dados": {
            "numero": dados_consulta["numero"],
            "ano": dados_consulta["ano"],
            "codigo_verificador": dados_consulta["codigo_verificador"],
            "evidencia_resultado": caminho_evidencia_resultado,
            "processo_id": processo.get("id"),
            "resultado": dados_resultado,
        },
    }


async def obter_frame_consulta(page):
    iframe = page.locator("iframe").first

    await iframe.wait_for(
        state="visible",
        timeout=30000,
    )

    frame_element = await iframe.element_handle()
    frame = await frame_element.content_frame()

    if frame is None:
        raise Exception("Não foi possível acessar o iframe do Atende.Net.")

    return frame


async def preencher_formulario_iframe(
    page,
    numero,
    ano,
    codigo_verificador,
):
    frame = await obter_frame_consulta(page)

    await frame.locator("input[name='numero']").fill(str(numero))
    await frame.locator("input[name='ano']").fill(str(ano))
    await frame.locator(
        "input[name='codigo_verificador']"
    ).fill(str(codigo_verificador))


async def clicar_confirmar_iframe(page):
    frame = await obter_frame_consulta(page)

    try:
        await frame.get_by_role(
            "button",
            name="Confirmar",
        ).click(timeout=10000)

        return

    except Exception:
        pass

    try:
        await frame.locator(
            "input[value='Confirmar']"
        ).first.click(timeout=10000)

        return

    except Exception:
        pass

    raise Exception("Botão Confirmar não encontrado dentro do iframe.")


async def extrair_dados_tela_resultado(page):
    frame = await obter_frame_consulta(page)

    return await frame.evaluate(
        """
        () => {
            function limpar(valor) {
                if (!valor) {
                    return "";
                }

                return String(valor)
                    .replace(/\\s+/g, " ")
                    .trim();
            }

            function valorPorName(name, indice = 0) {
                const campos = Array.from(
                    document.querySelectorAll(`[name="${name}"]`)
                );

                const campo = campos[indice];

                if (!campo) {
                    return "";
                }

                return limpar(
                    campo.value ||
                    campo.title ||
                    campo.innerText ||
                    campo.textContent
                );
            }

            function valorSelectPorName(name) {
                const campo = document.querySelector(`[name="${name}"]`);

                if (!campo) {
                    return "";
                }

                const opcao = campo.options[campo.selectedIndex];

                return limpar(
                    campo.title ||
                    (opcao ? opcao.text : "") ||
                    campo.value
                );
            }

            const textoPagina = limpar(document.body.innerText || "");

            const matchSituacao = textoPagina.match(
                /Situação Atual:\\s*([^\\n]+)/i
            );

            return {
                texto: textoPagina,
                campos: {
                    situacao_atual: matchSituacao
                        ? limpar(matchSituacao[1].split("Número")[0])
                        : "",

                    numero_ano: (
                        valorPorName("numero", 1) +
                        "/" +
                        valorPorName("ano", 1)
                    ),

                    codigo_verificador: valorPorName(
                        "codigo_verificador",
                        1
                    ),

                    data_abertura: valorPorName(
                        "historico_processo_abertura.data"
                    ),

                    previsao: valorPorName("data_previsao"),

                    assunto: (
                        valorPorName("assunto_subassunto.assunto.numero") +
                        " - " +
                        valorPorName("assunto_subassunto.assunto.descricao")
                    ),

                    subassunto: (
                        valorPorName("assunto_subassunto.subassunto.numero") +
                        " - " +
                        valorPorName("assunto_subassunto.subassunto.descricao")
                    ),

                    tipo: valorSelectPorName("tipo_assunto_subassunto"),

                    requerente: (
                        valorPorName("requerente.codigo", 0) +
                        " - " +
                        valorPorName("requerente.nomeRazao", 0)
                    ),

                    responsavel: (
                        valorPorName("Procurador.codigo") +
                        " - " +
                        valorPorName("Procurador.nomeRazao")
                    ),

                    observacao_abertura: valorPorName(
                        "historico_processo.observacao"
                    )
                }
            };
        }
        """
    )


async def salvar_html_debug(page):
    os.makedirs("evidencias", exist_ok=True)

    html = await page.content()

    caminho_html = "evidencias/debug_html_atende_net.html"

    with open(
        caminho_html,
        "w",
        encoding="utf-8",
    ) as arquivo:
        arquivo.write(html)

    print(f"HTML salvo em {caminho_html}")


async def aceitar_cookies_se_existir(page):
    try:
        botao_aceitar = page.locator(
            "button:has-text('Aceitar')"
        ).first

        await botao_aceitar.wait_for(timeout=5000)
        await botao_aceitar.click()

        print("Cookies aceitos.")

        await page.wait_for_timeout(2000)

    except Exception:
        print("Banner de cookies não encontrado. Continuando.")


def gerar_caminho_evidencia_resultado(processo):
    os.makedirs("evidencias", exist_ok=True)

    processo_id = processo.get("id", "sem_id")
    numero = str(
        processo.get("numero_processo", "sem_numero")
    ).replace("/", "_")
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"evidencias/atende_net_resultado_{processo_id}_{numero}_{agora}.png"


async def consultar_processo_atende_net(processo):
    robo = RobotAtendeNet()
    return await robo.consultar_processo(processo)