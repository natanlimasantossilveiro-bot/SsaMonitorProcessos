from playwright.async_api import async_playwright
from datetime import datetime
import re

from pyvirtualdisplay import Display
from utils.logger import get_logger

log = get_logger("ponta_grossa")

CONSULTA_URL = "https://servicos.pontagrossa.pr.gov.br/protocolo/consultaProcesso"


async def consultar_processo_ponta_grossa(processo):
    numero_completo = str(processo.get("numero_processo", "")).strip()
    acesso = str(processo.get("acesso") or "").strip()
    cpf_cnpj = processo.get("login_acesso") or ""

    # Extrai número e ano: "90451/2025" → ("90451", "2025")
    # Para processos sem ano no número, usa o campo acesso como ano
    if "/" in numero_completo:
        partes = numero_completo.split("/", 1)
        numero = partes[0].strip()
        ano = partes[1].strip()
    else:
        numero = numero_completo
        ano = acesso if (acesso.isdigit() and len(acesso) == 4) else ""

    log.info(f"Iniciando consulta — numero: {numero}, ano: {ano}")

    if not cpf_cnpj:
        log.warning(f"CPF/CNPJ ausente para processo {numero_completo}")
        return {
            "status": "ERRO_CONSULTA",
            "mensagem": "CPF/CNPJ não cadastrado para este processo",
        }

    display = Display(visible=False, size=(1280, 800))
    display.start()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                executable_path="/usr/bin/google-chrome",
                ignore_default_args=["--enable-automation", "--disable-infobars"],
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()

            log.info(f"Acessando: {CONSULTA_URL}")
            await page.goto(CONSULTA_URL, wait_until="networkidle", timeout=30_000)
            await page.wait_for_timeout(3_000)

            await page.screenshot(path="/tmp/pg_formulario.png")

            # ── Tipo Processo (obrigatório — sempre "2 - OnLine") ────────
            try:
                campo_tipo = page.get_by_label("Tipo Processo", exact=False)
                await campo_tipo.fill("Online")
                await page.wait_for_timeout(1_500)
                opcao = page.locator(
                    "li:has-text('OnLine'), li:has-text('Online'), "
                    ".v-list-item:has-text('OnLine'), .v-list-item:has-text('Online')"
                ).first
                if await opcao.count() > 0:
                    await opcao.click()
                    log.info("Tipo Processo selecionado: 2 - OnLine")
                else:
                    log.warning("Opcao OnLine nao encontrada no autocomplete")
            except Exception as ex:
                log.warning(f"Erro campo Tipo Processo: {ex}")

            # ── Preenche Número ───────────────────────────────────────────
            try:
                await page.get_by_label("Número", exact=False).fill(numero)
                log.info(f"Campo Numero preenchido: {numero}")
            except Exception as ex:
                log.warning(f"get_by_label Numero falhou ({ex}) — tentando seletores alternativos")
                for sel in ["input[placeholder*='úmero' i]", "input[name*='numero' i]",
                            "input[name*='num' i]"]:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible():
                            await el.fill(numero)
                            log.info(f"Campo Numero preenchido via {sel}")
                            break
                    except Exception:
                        continue

            # ── Preenche Ano ──────────────────────────────────────────────
            if ano:
                try:
                    await page.get_by_label("Ano", exact=False).fill(ano)
                    log.info(f"Campo Ano preenchido: {ano}")
                except Exception as ex:
                    log.warning(f"get_by_label Ano falhou ({ex}) — tentando seletores alternativos")
                    for sel in ["input[placeholder*='ano' i]", "input[name*='ano' i]"]:
                        try:
                            el = page.locator(sel).first
                            if await el.count() > 0 and await el.is_visible():
                                await el.fill(ano)
                                log.info(f"Campo Ano preenchido via {sel}")
                                break
                        except Exception:
                            continue

            # ── Preenche CPF/CNPJ ou Senha ────────────────────────────────
            try:
                await page.get_by_label("CPF", exact=False).fill(cpf_cnpj)
                log.info("Campo CPF/CNPJ preenchido")
            except Exception as ex:
                log.warning(f"get_by_label CPF falhou ({ex}) — tentando seletores alternativos")
                for sel in ["input[placeholder*='cpf' i]", "input[placeholder*='cnpj' i]",
                            "input[name*='cpf' i]", "input[name*='senha' i]",
                            "input[placeholder*='senha' i]"]:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible():
                            await el.fill(cpf_cnpj)
                            log.info(f"Campo CPF/CNPJ preenchido via {sel}")
                            break
                    except Exception:
                        continue

            # ── Clica em Pesquisar ────────────────────────────────────────
            try:
                await page.locator(
                    "button:has-text('PESQUISAR'), button:has-text('Pesquisar')"
                ).first.click()
                log.info("Botao PESQUISAR clicado")
            except Exception as ex:
                log.warning(f"Erro ao clicar PESQUISAR: {ex}")

            await page.wait_for_load_state("networkidle", timeout=15_000)
            await page.wait_for_timeout(3_000)

            await page.screenshot(path=f"/tmp/pg_resultado_{numero}.png")
            texto = await page.inner_text("body")
            texto_lower = texto.lower()
            log.info(f"Resultado pesquisa (400 chars): {texto[:400]}")

            # ── Verifica não encontrado ───────────────────────────────────
            nao_encontrado = any(f in texto_lower for f in (
                "nenhum resultado", "não encontrado", "nao encontrado",
                "sem resultado", "nenhum registro", "0 resultado",
            ))
            if nao_encontrado:
                log.warning(f"Processo {numero_completo} nao encontrado no portal")
                await browser.close()
                return {
                    "status": "PROCESSO_NAO_ENCONTRADO",
                    "mensagem": "Processo não encontrado no portal",
                    "texto_completo": texto,
                }

            # ── Detecta status a partir da tabela de Trâmites ────────────
            # Localiza a seção "Trâmites" para evitar falso positivo com
            # as opções de filtro da página (ex: "Finalizado" no dropdown)
            tramites_m = re.search(r'Tr[aâ]mites\b(.+)', texto, re.IGNORECASE | re.DOTALL)
            tramites_texto = tramites_m.group(1) if tramites_m else texto
            if not tramites_m:
                log.warning("Secao Tramites nao encontrada — usando texto completo")

            # Dentro da seção, o status aparece como "N - Status" na coluna Situação
            # A ordem dos rows é decrescente (maior = mais recente), então pega o primeiro match
            _SITUACAO_RE = re.compile(
                r'\d+\s*-\s*(Em\s+tr[aâ]mite|Em\s+andamento|Em\s+an[aá]lise'
                r'|Aguardando|Finalizado|Conclu[íi]do|Deferido|Indeferido|Encerrado)',
                re.IGNORECASE,
            )
            situacao_m = _SITUACAO_RE.search(tramites_texto)
            if situacao_m:
                situacao_raw = situacao_m.group(1).strip()
                log.info(f"Situacao extraida da tabela Tramites: {situacao_raw}")
            else:
                situacao_raw = ""
                log.warning("Situacao nao encontrada na tabela Tramites")

            _MAP_STATUS = [
                (r'em\s+tr[aâ]mite', "Em andamento"),
                (r'em\s+andamento', "Em andamento"),
                (r'aguardando', "Em andamento"),
                (r'em\s+an[aá]lise', "Em analise"),
                (r'indeferido', "Indeferido"),
                (r'deferido', "Deferido"),
                (r'finalizado', "Finalizado"),
                (r'conclu[íi]do', "Finalizado"),
                (r'encerrado', "Encerrado"),
            ]

            status_processo = None
            for padrao, valor in _MAP_STATUS:
                if re.search(padrao, situacao_raw, re.IGNORECASE):
                    status_processo = valor
                    break

            if not status_processo:
                log.warning("Status nao reconhecido — marcando como Em andamento")
                status_processo = "Em andamento"

            # ── Extrai última movimentação ────────────────────────────────
            linhas = texto.split("\n")
            movimentacoes = [
                l.strip() for l in linhas
                if re.search(r"\d{2}/\d{2}/\d{4}", l.strip())
            ]

            objeto = None
            for marcador in ("Assunto:", "Objeto:", "Descrição:", "Descricao:", "Tipo:"):
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
    finally:
        display.stop()
