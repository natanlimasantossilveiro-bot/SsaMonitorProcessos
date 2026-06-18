import os
from datetime import datetime

from playwright.async_api import async_playwright

from robots.base.robot_base import RobotBase

from robots.atende_net.parser import (
    montar_dados_consulta_atende_net,
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

        await browser.close()

    return {
        "status": "ATENDE_NET_CONSULTA_EXECUTADA",
        "mensagem": (
            "Consulta Atende.Net executada. "
            "Próxima etapa será interpretar a tela de resultado."
        ),
        "dados": {
            "numero": dados_consulta["numero"],
            "ano": dados_consulta["ano"],
            "codigo_verificador": dados_consulta["codigo_verificador"],
            "evidencia_resultado": caminho_evidencia_resultado,
            "processo_id": processo.get("id"),
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

    resultado_debug = await frame.evaluate(
        """
        () => {
            const inputs = Array.from(document.querySelectorAll("input"));

            return inputs.map((input, index) => {
                const rect = input.getBoundingClientRect();
                const style = window.getComputedStyle(input);

                return {
                    index: index,
                    type: input.type,
                    name: input.name,
                    id: input.id,
                    value: input.value,
                    placeholder: input.placeholder,
                    visible: (
                        style.display !== "none" &&
                        style.visibility !== "hidden" &&
                        rect.width > 0 &&
                        rect.height > 0
                    ),
                    width: rect.width,
                    height: rect.height,
                    x: rect.x,
                    y: rect.y
                };
            });
        }
        """
    )

    print("\n=== DEBUG INPUTS IFRAME ===")
    print(resultado_debug)

    campos_visiveis = await frame.locator(
        "input:not([type='hidden'])"
    ).all()

    if len(campos_visiveis) < 3:
        raise Exception(
            "Não foram encontrados 3 campos visíveis dentro do iframe."
        )

    await campos_visiveis[0].click()
    await campos_visiveis[0].fill(str(numero))

    await campos_visiveis[1].click()
    await campos_visiveis[1].fill(str(ano))

    await campos_visiveis[2].click()
    await campos_visiveis[2].fill(str(codigo_verificador))

    valores_apos_preenchimento = await frame.evaluate(
        """
        () => {
            const inputs = Array.from(document.querySelectorAll("input"));

            return inputs.map((input, index) => ({
                index: index,
                type: input.type,
                name: input.name,
                id: input.id,
                value: input.value,
                placeholder: input.placeholder
            }));
        }
        """
    )

    print("\n=== VALORES APÓS PREENCHIMENTO ===")
    print(valores_apos_preenchimento)


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
            "button:has-text('Confirmar')"
        ).first.click(timeout=10000)

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