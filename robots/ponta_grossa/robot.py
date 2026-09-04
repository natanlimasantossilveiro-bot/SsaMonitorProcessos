from playwright.async_api import async_playwright
from datetime import datetime
import re

from utils.logger import get_logger

log = get_logger("ponta_grossa")

BASE_URL  = "https://pontagrossa.oxy.elotech.com.br/governo-digital"
LOGIN_URL = f"{BASE_URL}/login"


async def consultar_processo_ponta_grossa(processo):
    numero    = str(processo.get("numero_processo")).strip()
    url_proc  = processo.get("acesso")
    login     = processo.get("login_acesso")
    senha     = processo.get("senha_acesso")

    log.info(f"Iniciando consulta — numero: {numero}")

    if not url_proc:
        log.warning(f"Campo 'acesso' vazio para processo {numero} — sem URL individual cadastrada")
        return {
            "status": "ERRO_CONSULTA",
            "mensagem": "URL individual do processo não cadastrada (campo 'acesso' vazio)",
        }

    if not login or not senha:
        log.warning(f"Credenciais ausentes para processo {numero}")
        return {
            "status": "ERRO_CONSULTA",
            "mensagem": "Login ou senha não cadastrados para este processo",
        }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()

            # ── 1. Login ─────────────────────────────────────────────────
            log.info(f"Acessando login: {LOGIN_URL}")
            await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)

            # Tenta seletores comuns de e-mail/login em portais Elotech
            seletores_login = [
                "input[type='email']",
                "input[name='email']",
                "input[name='login']",
                "input[placeholder*='e-mail' i]",
                "input[placeholder*='email' i]",
                "input[placeholder*='usuário' i]",
                "input[placeholder*='usuario' i]",
                "input[placeholder*='cpf' i]",
            ]
            seletores_senha = [
                "input[type='password']",
                "input[name='senha']",
                "input[name='password']",
            ]

            campo_login = None
            for sel in seletores_login:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        campo_login = el
                        log.info(f"Campo login encontrado: {sel}")
                        break
                except Exception:
                    continue

            campo_senha = None
            for sel in seletores_senha:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        campo_senha = el
                        log.info("Campo senha encontrado")
                        break
                except Exception:
                    continue

            if not campo_login or not campo_senha:
                log.error("Campos de login/senha não encontrados na página")
                await browser.close()
                return {
                    "status": "ERRO_CONSULTA",
                    "mensagem": "Campos de login não encontrados no portal Ponta Grossa",
                }

            await campo_login.fill(login)
            await campo_senha.fill(senha)
            log.info("Credenciais preenchidas")

            # Submete login
            botao_login = None
            for sel in ["button[type='submit']", "button:has-text('Entrar')",
                        "button:has-text('Acessar')", "button:has-text('Login')"]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        botao_login = el
                        break
                except Exception:
                    continue

            if botao_login:
                await botao_login.click()
            else:
                await campo_senha.press("Enter")

            await page.wait_for_load_state("networkidle", timeout=20_000)

            # Verifica se autenticou
            url_atual = page.url
            texto_pos_login = (await page.inner_text("body")).lower()
            log.info(f"URL apos login: {url_atual}")

            if "login" in url_atual or "senha incorreta" in texto_pos_login \
                    or "credenciais" in texto_pos_login or "inválid" in texto_pos_login:
                log.error("Falha no login — credenciais incorretas ou captcha")
                await browser.close()
                return {
                    "status": "ERRO_CONSULTA",
                    "mensagem": "Falha no login — credenciais incorretas ou portal alterado",
                }

            log.info("Login realizado com sucesso")

            # ── 2. Acessa URL individual do processo ─────────────────────
            log.info(f"Acessando processo: {url_proc}")
            await page.goto(url_proc, wait_until="networkidle", timeout=30_000)

            texto = await page.inner_text("body")
            texto_lower = texto.lower()
            log.debug(f"Pagina do processo (300 chars): {texto[:300]}")

            # ── 3. Verifica processo não encontrado ──────────────────────
            nao_encontrado = any(f in texto_lower for f in (
                "não encontrado", "nao encontrado",
                "registro não encontrado", "sem resultado",
                "404", "página não encontrada",
            ))
            if nao_encontrado:
                log.warning(f"Processo {numero} nao encontrado na URL: {url_proc}")
                await browser.close()
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo não encontrado na URL cadastrada",
                    "texto_completo": texto,
                }

            # ── 4. Detecta status ────────────────────────────────────────
            if "finalizado" in texto_lower:
                status_processo = "Finalizado"
            elif "indeferido" in texto_lower:
                status_processo = "Indeferido"
            elif "deferido" in texto_lower:
                status_processo = "Deferido"
            elif "encerrado" in texto_lower:
                status_processo = "Encerrado"
            elif "em andamento" in texto_lower:
                status_processo = "Em andamento"
            elif "em análise" in texto_lower or "em analise" in texto_lower:
                status_processo = "Em analise"
            elif "aguardando" in texto_lower:
                status_processo = "Em andamento"
            else:
                log.warning("Status nao reconhecido, marcando como Em andamento")
                status_processo = "Em andamento"

            # ── 5. Extrai última movimentação ────────────────────────────
            linhas = texto.split("\n")
            movimentacoes = [
                l.strip() for l in linhas
                if re.search(r"\d{2}/\d{2}/\d{4}", l.strip())
            ]

            objeto = None
            for marcador in ("Assunto:", "Objeto:", "Descrição:", "Descricao:"):
                if marcador in texto:
                    idx = texto.index(marcador) + len(marcador)
                    objeto = texto[idx:idx + 500].strip().split("\n")[0].strip() or None
                    break

            ultima_movimentacao = None
            data_ultimo_movimento = None
            if movimentacoes:
                ultima_movimentacao = movimentacoes[-1]
                match = re.search(r"\d{2}/\d{2}/\d{4}", ultima_movimentacao)
                if match:
                    try:
                        data_ultimo_movimento = datetime.strptime(
                            match.group(), "%d/%m/%Y"
                        ).strftime("%Y-%m-%d")
                    except Exception:
                        pass

            log.info(f"Status: {status_processo} | Data: {data_ultimo_movimento}")
            await browser.close()

            return {
                "status": "OK",
                "mensagem": "Consulta realizada com sucesso",
                "status_processo": status_processo,
                "ultima_data_movimento": data_ultimo_movimento,
                "ultima_movimentacao": ultima_movimentacao,
                "texto_completo": texto,
                "objeto": objeto,
            }

    except Exception as e:
        log.error(f"Erro na consulta: {e}")
        return {"status": "ERRO_CONSULTA", "mensagem": str(e)}
