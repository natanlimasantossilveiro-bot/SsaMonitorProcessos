import asyncio
import re
from datetime import datetime

try:
    from pyvirtualdisplay import Display
    _HAS_DISPLAY = True
except ImportError:
    _HAS_DISPLAY = False

from playwright.async_api import async_playwright
from robots.base.robot_base import RobotBase
from utils.logger import get_logger

log = get_logger("ridigital")

_URL_LOGIN     = "https://ridigital.org.br/Acesso.aspx"
_URL_PROTOCOLO = "https://ridigital.org.br/eProtocolo/listagem_contratos.aspx?comum=1"


class RobotRIDigital(RobotBase):
    async def consultar_processo(self, processo):
        log.info(f"Iniciando consulta — processo: {processo.get('numero_processo')}")
        return await _executar_consulta(processo)


# ─────────────────────────────────────────────────
# ETAPAS
# ─────────────────────────────────────────────────

async def _fazer_login(page, login, senha):
    await page.goto(_URL_LOGIN, timeout=30000)
    await page.wait_for_load_state("networkidle", timeout=20000)

    campo_email = page.locator(
        'input[type="email"], input[id*="mail"], input[id*="Login"], input[name*="login"]'
    ).first
    await campo_email.fill(login)

    campo_senha = page.locator('input[type="password"], input[id*="enha"]').first
    await campo_senha.fill(senha)

    btn = page.locator(
        'button[type="submit"], input[type="submit"], '
        'button:has-text("Entrar"), button:has-text("Acessar")'
    ).first
    await btn.click()

    await page.wait_for_load_state("networkidle", timeout=30000)
    log.info(f"Login concluído — URL: {page.url}")


async def _ir_para_listagem(page):
    if "listagem_contratos" not in page.url:
        await page.goto(_URL_PROTOCOLO, timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)


async def _filtrar_por_protocolo(page, numero):
    campo = page.locator(
        'input[id*="Protocolo"], input[id*="protocolo"], '
        'input[placeholder*="Protocolo"], input[placeholder*="protocolo"]'
    ).first
    await campo.wait_for(state="visible", timeout=10000)
    await campo.fill(numero)

    # Data "De" bem antiga para não perder protocolos antigos
    try:
        campo_de = page.locator('input[id*="txtDe"], input[id*="txtde"]').first
        await campo_de.fill("01/01/2020")
    except Exception:
        pass

    btn = page.locator('button:has-text("Filtrar"), input[value="Filtrar"]').first
    await btn.click()
    await page.wait_for_load_state("networkidle", timeout=20000)
    log.info(f"Filtro aplicado para protocolo: {numero}")


async def _extrair_linha(page, numero):
    """Encontra a linha do protocolo e retorna (locator, status, data_status)."""
    try:
        await page.wait_for_selector("table tr", timeout=15000)
    except Exception:
        return None, None, None

    linhas = await page.locator("table tr").all()
    for linha in linhas:
        texto = await linha.inner_text()
        if numero in texto:
            colunas = await linha.locator("td").all()
            status  = (await colunas[3].inner_text()).strip() if len(colunas) > 3 else None
            dt_stat = (await colunas[4].inner_text()).strip() if len(colunas) > 4 else None
            return linha, status, dt_stat

    return None, None, None


async def _abrir_detalhes(context, page, linha):
    """Clica no ícone de Detalhes Pedido e retorna a página resultante (popup ou mesma página)."""
    link = linha.locator("td:first-child a, td:first-child button").first

    nova_pagina = []

    def _capturar(p):
        nova_pagina.append(p)

    context.on("page", _capturar)
    await link.click()
    await asyncio.sleep(3)
    context.remove_listener("page", _capturar)

    if nova_pagina:
        pag = nova_pagina[0]
        await pag.wait_for_load_state("networkidle", timeout=20000)
        return pag

    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    return page


async def _extrair_resposta(pagina):
    """Extrai texto da seção 'Resposta:' e a lista de anexos."""
    texto = await pagina.inner_text("body")

    resposta = None
    if "Resposta:" in texto:
        idx = texto.index("Resposta:") + len("Resposta:")
        trecho = texto[idx:idx + 2000].strip()
        linhas_nv = [l.strip() for l in trecho.split("\n") if l.strip()]
        resposta = " ".join(linhas_nv[:5])

    movimentacoes = []
    try:
        tabelas = await pagina.locator("table").all()
        for tabela in tabelas:
            cab = await tabela.inner_text()
            if "Descrição" in cab or "Anexo" in cab:
                linhas_t = await tabela.locator("tr").all()
                for linha_t in linhas_t[1:]:  # pula cabeçalho
                    cols = await linha_t.locator("td").all()
                    if len(cols) >= 2:
                        dt   = (await cols[0].inner_text()).strip()
                        desc = (await cols[1].inner_text()).strip()
                        if dt and desc:
                            movimentacoes.append(f"{dt} — {desc}")
    except Exception as e:
        log.warning(f"Erro ao extrair tabela de anexos: {e}")

    return resposta, movimentacoes


# ─────────────────────────────────────────────────
# PONTO DE ENTRADA
# ─────────────────────────────────────────────────

async def _executar_consulta(processo):
    numero = processo.get("numero_processo")
    login  = processo.get("login_acesso")
    senha  = processo.get("senha_acesso")

    if not login or not senha:
        return {
            "status": "ERRO_CONSULTA",
            "mensagem": "Credenciais de acesso não configuradas para este processo",
        }

    display = None
    if _HAS_DISPLAY:
        display = Display(visible=False, size=(1280, 900))
        display.start()

    try:
        async with async_playwright() as p:
            kwargs = dict(
                ignore_default_args=["--enable-automation", "--disable-infobars"],
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            if _HAS_DISPLAY:
                kwargs["headless"] = False
                kwargs["executable_path"] = "/usr/bin/google-chrome"
            else:
                kwargs["headless"] = True

            browser = await p.chromium.launch(**kwargs)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/151.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()

            await _fazer_login(page, login, senha)
            await _ir_para_listagem(page)
            await _filtrar_por_protocolo(page, numero)

            linha, status_processo, data_status_str = await _extrair_linha(page, numero)

            if not linha:
                log.warning(f"Protocolo {numero} não encontrado na listagem")
                await browser.close()
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": f"Protocolo {numero} não encontrado na listagem RI Digital",
                }

            log.info(f"Processo encontrado — status: {status_processo} | dt_status: {data_status_str}")

            pagina_detalhe = await _abrir_detalhes(context, page, linha)
            resposta, movimentacoes = await _extrair_resposta(pagina_detalhe)

            data_ultimo_movimento = None
            if data_status_str:
                m = re.search(r"\d{2}/\d{2}/\d{4}", data_status_str)
                if m:
                    try:
                        data_ultimo_movimento = datetime.strptime(
                            m.group(), "%d/%m/%Y"
                        ).strftime("%Y-%m-%d")
                    except Exception:
                        pass

            await browser.close()
            log.info(f"Consulta OK — {numero} | movs: {len(movimentacoes)}")

            return {
                "status": "OK",
                "status_processo": status_processo,
                "movimentacoes": movimentacoes,
                "ultima_data_movimento": data_ultimo_movimento,
                "ultima_movimentacao": resposta,
                "objeto": None,
            }

    except Exception as e:
        log.error(f"Erro RIDigital [{numero}]: {e}")
        return {"status": "ERRO_CONSULTA", "mensagem": str(e)}

    finally:
        if display:
            display.stop()


async def consultar_processo_ridigital(processo):
    robo = RobotRIDigital()
    return await robo.consultar_processo(processo)