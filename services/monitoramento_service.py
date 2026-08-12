from datetime import datetime, timedelta
import asyncio

from database.repositories import (
    listar_orgaos,
    listar_processos_ativos_com_orgao,
    registrar_historico_consulta,
    registrar_movimentacao,
    atualizar_dados_processo,
    atualizar_objeto_processo,
    atualizar_caminho_solicitacao_captcha,
    limpar_caminho_solicitacao_captcha,
)

from robots.curitiba.robot import consultar_processo_curitiba
from robots.atendenet_v2.robot import consultar_processo_pinhais
from robots.sjp.robot import consultar_processo_sjp
from robots.franco_rocha.robot import consultar_processo_franco_rocha
from robots.ridigital.robot import consultar_processo_ridigital
from services.relatorio_execucao_service import salvar_relatorio_execucao
from utils.logger import configurar_logger, get_logger

configurar_logger()
log = get_logger("monitoramento")
fila_processos = asyncio.Queue()


STATUS_SEM_ROBO_CONFIGURADO = "SEM_ROBO_CONFIGURADO"
STATUS_ERRO_CONSULTA = "ERRO_CONSULTA"
STATUS_PENDENTE_INTEGRACAO_CAPTCHA = "PENDENTE_INTEGRACAO_CAPTCHA"
STATUS_CAPTCHA_RESOLVIDO_FLUXO_PENDENTE = "CAPTCHA_RESOLVIDO_FLUXO_PENDENTE"

_MAX_TENTATIVAS = 3
_DELAY_RETRY = 30  # segundos entre tentativas

# Progresso da execução atual — atualizado durante o monitoramento
_progresso = {"total": 0, "concluidos": 0, "orgao_atual": ""}

_NOMES_ROBO = {
    "atende_net": "AtendNet (Pinhais / Araucária)",
    "curitiba": "Curitiba",
    "sjp": "São José dos Pinhais",
    "franco_rocha": "Franco da Rocha",
    "caieiras": "Caieiras",
    "esic": "eSIC",
    "ponta_grossa": "Ponta Grossa",
    "pinhais": "Pinhais",
    "ridigital": "RI Digital (Registradores)",
}


def criar_resumo_execucao():
    return {
        "TOTAL_PROCESSOS": 0,
        "NOVA_MOVIMENTACAO": 0,
        "SEM_NOVA_MOVIMENTACAO": 0,
        "PROCESSO_NAO_ENCONTRADO": 0,
        "ERRO_CONSULTA": 0,
        "SISTEMA_FORA": 0,
        "SEM_ROBO_CONFIGURADO": 0,
        "PENDENTE_INTEGRACAO_CAPTCHA": 0,
        "CAPTCHA_RESOLVIDO_FLUXO_PENDENTE": 0,
        "OK": 0,
        "ORGAOS_SEM_ROBO": {},
    }


def criar_evento_processo(processo, resultado):
    return {
        "processo_id": processo.get("id"),
        "numero_processo": processo.get("numero_processo"),
        "empresa": processo.get("empresa"),
        "municipio": processo.get("municipio"),
        "orgao": processo.get("nome_orgao"),
        "chave_robo": processo.get("chave_robo"),
        "status": resultado.get("status"),
        "mensagem": resultado.get("mensagem"),
    }


def incrementar_resumo(resumo, status):
    if status not in resumo:
        resumo[status] = 0

    resumo[status] += 1


def registrar_orgao_sem_robo(resumo, processo):
    nome_orgao = processo.get("nome_orgao") or "Órgão não informado"
    url_orgao = processo.get("url_orgao") or "URL não informada"

    chave = f"{nome_orgao} | {url_orgao}"

    if chave not in resumo["ORGAOS_SEM_ROBO"]:
        resumo["ORGAOS_SEM_ROBO"][chave] = {
            "nome": nome_orgao,
            "url": url_orgao,
            "total": 0,
        }

    resumo["ORGAOS_SEM_ROBO"][chave]["total"] += 1


def formatar_tempo(segundos):
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segundos = int(segundos % 60)

    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def exibir_resumo_execucao(resumo, inicio_execucao):
    fim_execucao = datetime.now()
    tempo_total = (fim_execucao - inicio_execucao).total_seconds()

    log.info("=" * 50)
    log.info("RESUMO DA EXECUCAO")
    log.info(f"  Total de processos     : {resumo.get('TOTAL_PROCESSOS', 0)}")
    log.info(f"  OK                     : {resumo.get('OK', 0)}")
    log.info(f"  Nova movimentacao      : {resumo.get('NOVA_MOVIMENTACAO', 0)}")
    log.info(f"  Sem nova movimentacao  : {resumo.get('SEM_NOVA_MOVIMENTACAO', 0)}")
    log.info(f"  Processo nao encontrado: {resumo.get('PROCESSO_NAO_ENCONTRADO', 0)}")
    log.info(f"  Erro de consulta       : {resumo.get('ERRO_CONSULTA', 0)}")
    log.info(f"  Sem robo configurado   : {resumo.get('SEM_ROBO_CONFIGURADO', 0)}")
    log.info(f"  Tempo total            : {formatar_tempo(tempo_total)}")
    log.info("=" * 50)

    if resumo.get("ORGAOS_SEM_ROBO"):
        log.warning("Orgaos sem robo configurado:")
        for item in resumo["ORGAOS_SEM_ROBO"].values():
            log.warning(f"  {item['nome']} | processos: {item['total']} | url: {item['url']}")


def validar_orgaos_importados():
    orgaos = listar_orgaos()

    log.info("Orgaos/links importados:")

    if not orgaos:
        log.warning("Nenhum orgao encontrado no banco.")
        return

    for orgao in orgaos:
        log.info(
            f"  id={orgao.get('id')} | {orgao.get('nome')} | "
            f"robo={orgao.get('chave_robo')} | url={orgao.get('url')}"
        )


def obter_caminho_solicitacao_resultado(resultado):
    dados = resultado.get("dados") or {}

    return (
        dados.get("caminho_solicitacao")
        or resultado.get("caminho_solicitacao")
    )


def tratar_estado_captcha_processo(processo_id, status, resultado):
    if status == STATUS_PENDENTE_INTEGRACAO_CAPTCHA:
        caminho_solicitacao = obter_caminho_solicitacao_resultado(resultado)

        if caminho_solicitacao:
            atualizar_caminho_solicitacao_captcha(
                processo_id=processo_id,
                caminho_solicitacao=caminho_solicitacao,
            )

        return

    if status == STATUS_CAPTCHA_RESOLVIDO_FLUXO_PENDENTE:
        limpar_caminho_solicitacao_captcha(processo_id)


async def processar_processo_individual(processo, resumo, eventos_processos):
    resultado = await rotear_consulta_processo(
        processo=processo,
        modo_silencioso_sem_robo=True,
    )

    status = resultado.get("status", "OK")

    incrementar_resumo(resumo, status)

    eventos_processos.append(
        criar_evento_processo(processo, resultado)
    )

    if status == STATUS_SEM_ROBO_CONFIGURADO:
        registrar_orgao_sem_robo(resumo, processo)

    _progresso["concluidos"] += 1
    return resultado


async def worker(resumo, eventos_processos):
    while True:
        try:
            processo = await fila_processos.get()

            await processar_processo_individual(
                processo,
                resumo,
                eventos_processos
            )

            fila_processos.task_done()

        except asyncio.CancelledError:
            break


async def monitorar_processos_ativos():
    import asyncio

    inicio_execucao = datetime.now()
    resumo = criar_resumo_execucao()
    eventos_processos = []

    processos = listar_processos_ativos_com_orgao()
    resumo["TOTAL_PROCESSOS"] = len(processos)
    _progresso.update({"total": len(processos), "concluidos": 0, "orgao_atual": ""})

    log.info(f"Iniciando monitoramento — {len(processos)} processo(s) ativos")

    if not processos:
        log.warning("Nenhum processo ativo encontrado")

        exibir_resumo_execucao(resumo, inicio_execucao)

        caminho_relatorio = salvar_relatorio_execucao(
            resumo=resumo,
            inicio_execucao=inicio_execucao,
            eventos_processos=eventos_processos,
        )

        log.info(f"Relatorio salvo em: {caminho_relatorio}")
        return

    # Agrupa processos por robo
    processos_por_robo = {}

    for processo in processos:
        nome_robo = processo.get("robo") or processo.get("chave_robo")
        processos_por_robo.setdefault(nome_robo, []).append(processo)

    # ==========================================================
    # ✅ EXECUÇÃO POR ROBÔ
    # ==========================================================
    for nome_robo, lista_processos in processos_por_robo.items():
        _progresso["orgao_atual"] = _NOMES_ROBO.get(nome_robo, nome_robo)

        log.info(f"Processando robo: {nome_robo} | {len(lista_processos)} processo(s)")

        # ======================================================
        # 🔥 FRANCO DA ROCHA (MODO OTIMIZADO)
        # ======================================================
        if nome_robo == "franco_rocha":

            try:
                resultado_lista = await consultar_processo_franco_rocha(lista_processos[0])

                texto = resultado_lista.get("texto_completo", "")

                for processo in lista_processos:

                    numero = str(processo.get("numero_processo"))

                    log.info(f"Franco da Rocha: processando processo {numero}")

                    if numero not in texto:
                        resultado_individual = {
                            "status": "PROCESSO_NAO_ENCONTRADO",
                            "mensagem": "Processo não encontrado na lista",
                        }
                    else:
                        linhas = texto.split("\n")

                        linha_processo = None
                        for linha in linhas:
                            if numero in linha:
                                linha_processo = linha
                                break

                        status_processo = "Em andamento"

                        import re

                        datas = re.findall(r"\d{2}/\d{2}/\d{4}", linha_processo or "")

                        data_ultimo_movimento = None
                        if datas:
                            data_convertida = datetime.strptime(datas[-1], "%d/%m/%Y")
                            data_ultimo_movimento = data_convertida.strftime("%Y-%m-%d")

                        resultado_individual = {
                            "status": "OK",
                            "mensagem": "Consulta realizada com sucesso",
                            "status_processo": status_processo,
                            "ultima_data_movimento": data_ultimo_movimento,
                            "ultima_movimentacao": linha_processo,
                        }

                    status = resultado_individual.get("status", "OK")
                    incrementar_resumo(resumo, status)

                    eventos_processos.append(
                        criar_evento_processo(processo, resultado_individual)
                    )

                    async def retorno_fixo(_):
                        return resultado_individual

                    await consultar_com_robo(
                        processo=processo,
                        nome_robo="franco_rocha",
                        funcao_consulta=retorno_fixo,
                    )

                    _progresso["concluidos"] += 1

            except Exception as e:
                log.error(f"Erro no robo Franco da Rocha: {e}")

            continue

        # ======================================================
        # ✅ OUTROS ROBÔS (AGORA PARALELO ⚡)
        # ======================================================

        # 🔥 adiciona processos na fila
        for processo in lista_processos:
            await fila_processos.put(processo)

        # 🔥 cria workers (consumidores)
        workers = [
            asyncio.create_task(worker(resumo, eventos_processos))
            for _ in range(5)
        ]

        # 🔥 espera terminar tudo
        await fila_processos.join()

        # 🔥 finaliza workers
        for w in workers:
            w.cancel()

    # ==========================================================
    # ✅ FINALIZA EXECUÇÃO
    # ==========================================================
    exibir_resumo_execucao(resumo, inicio_execucao)

    caminho_relatorio = salvar_relatorio_execucao(
        resumo=resumo,
        inicio_execucao=inicio_execucao,
        eventos_processos=eventos_processos,
    )

    log.info(f"Relatorio salvo em: {caminho_relatorio}")


async def monitorar_um_processo_teste():
    processos = listar_processos_ativos_com_orgao()

    if not processos:
        print("\nNenhum processo ativo encontrado para teste.")
        return

    print("\n=== PROCESSOS DISPONÍVEIS PARA TESTE ===")

    for indice, processo in enumerate(processos, start=1):
        print(
            f"{indice} - "
            f"{processo.get('numero_processo')} | "
            f"{processo.get('empresa')} | "
            f"{processo.get('nome_orgao')} | "
            f"Robo: {processo.get('robo') or processo.get('chave_robo')}"
        )

    escolha = input("\nDigite o numero do processo para testar: ").strip()

    if not escolha.isdigit():
        print("Opcao invalida.")
        return

    indice_escolhido = int(escolha)

    if indice_escolhido < 1 or indice_escolhido > len(processos):
        print("Processo nao encontrado na lista.")
        return

    processo = processos[indice_escolhido - 1]

    resultado = await rotear_consulta_processo(
        processo=processo,
        modo_silencioso_sem_robo=False,
    )

    print("\n=== RESUMO DO TESTE ===")
    print(f"Processo: {processo.get('numero_processo')}")
    print(f"Status: {resultado.get('status')}")
    print(f"Mensagem: {resultado.get('mensagem')}")


_TIMEOUT_CONSULTA = 240  # segundos maximos por tentativa (evita Chrome pendurado)


async def _executar_com_retry(funcao_consulta, processo, processo_id):
    for tentativa in range(1, _MAX_TENTATIVAS + 1):
        try:
            resultado = await asyncio.wait_for(
                funcao_consulta(processo), timeout=_TIMEOUT_CONSULTA
            )
            if resultado.get("status") != STATUS_ERRO_CONSULTA:
                return resultado
            log.warning(
                f"Processo {processo_id}: tentativa {tentativa}/{_MAX_TENTATIVAS} retornou ERRO_CONSULTA"
                + (f" — aguardando {_DELAY_RETRY}s" if tentativa < _MAX_TENTATIVAS else "")
            )
        except Exception as e:
            log.error(
                f"Processo {processo_id}: tentativa {tentativa}/{_MAX_TENTATIVAS} — excecao: {e}"
                + (f" — aguardando {_DELAY_RETRY}s" if tentativa < _MAX_TENTATIVAS else "")
            )
            if tentativa == _MAX_TENTATIVAS:
                raise

        if tentativa < _MAX_TENTATIVAS:
            await asyncio.sleep(_DELAY_RETRY)

    return {"status": STATUS_ERRO_CONSULTA, "mensagem": f"Falha apos {_MAX_TENTATIVAS} tentativas"}


async def consultar_com_robo(
    processo,
    nome_robo,
    funcao_consulta,
):
    processo_id = processo.get("id")

    log.info(
        f"Consultando processo {processo_id} | "
        f"num={processo.get('numero_processo')} | "
        f"empresa={processo.get('empresa')} | "
        f"orgao={processo.get('nome_orgao')} | "
        f"robo={nome_robo}"
    )

    try:
        resultado = await _executar_com_retry(funcao_consulta, processo, processo_id)

        status = resultado.get("status", "OK")
        mensagem = resultado.get("mensagem", "")



        movimentacoes = resultado.get("movimentacoes") or []

        # ✅ NÃO MASCARA MAIS
        status_processo = resultado.get("status_processo")

        data_ultimo_movimento = None
        ultima_movimentacao = None

        # ✅ DEFINE SE FOI MONITORADO DE VERDADE
        monitorado = 1 if status == "OK" else 0

        # =====================================================
        # CASO 1: COM MOVIMENTAÇÕES
        # =====================================================
        if movimentacoes:
            log.debug("Processando bloco de movimentacoes")

            import re

            ultima_movimentacao = movimentacoes[0]

            for movimento in movimentacoes:
                match = re.search(r"\d{2}/\d{2}/\d{4}", movimento)

                if match:
                    data_str = match.group()
                    data_convertida = datetime.strptime(data_str, "%d/%m/%Y")
                    data_ultimo_movimento = data_convertida.strftime("%Y-%m-%d")
                    break

            # Salva cada movimentação individual (apenas as que têm data)
            # na tabela movimentacoes — alimenta o dashboard "Últimas movimentações"
            for movimento in movimentacoes:
                match = re.search(r"\d{2}/\d{2}/\d{4}", movimento)
                if match:
                    try:
                        data_str = match.group()
                        data_mov = datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                        registrar_movimentacao(processo_id, data_mov, movimento[:500])
                    except Exception:
                        pass

        # =====================================================
        # CASO 2: DADOS DIRETOS
        # =====================================================
        elif resultado.get("ultima_data_movimento"):
            log.debug("Processando bloco estruturado (ultima_data_movimento)")

            data_str = resultado.get("ultima_data_movimento")
            ultima_movimentacao = resultado.get("ultima_movimentacao")

            try:
                if "-" in data_str:
                    data_ultimo_movimento = data_str
                else:
                    data_convertida = datetime.strptime(data_str, "%d/%m/%Y")
                    data_ultimo_movimento = data_convertida.strftime("%Y-%m-%d")
            except Exception:
                data_ultimo_movimento = None

        else:
            log.warning(f"Processo {processo_id}: consulta sem dados de movimentacao")

        atualizar_dados_processo(
            processo_id,
            status_processo,
            data_ultimo_movimento,
            ultima_movimentacao,
            monitorado,
        )

        objeto = resultado.get("objeto")
        if objeto:
            atualizar_objeto_processo(processo_id, objeto)

        if monitorado:
            log.info(f"Processo {processo_id} monitorado — status: {status_processo}")
        else:
            log.warning(f"Processo {processo_id} nao monitorado — status consulta: {status}")

        tratar_estado_captcha_processo(
            processo_id=processo_id,
            status=status,
            resultado=resultado,
        )

        registrar_historico_consulta(
            processo_id=processo_id,
            status=status,
            mensagem=mensagem,
        )

        log.debug(f"Processo {processo_id}: status final = {status}")

        return resultado

    except Exception as erro:
        mensagem = str(erro)
        log.error(f"Processo {processo_id}: excecao na consulta — {mensagem}")

        registrar_historico_consulta(
            processo_id=processo_id,
            status=STATUS_ERRO_CONSULTA,
            mensagem=mensagem,
        )

        return {
            "status": STATUS_ERRO_CONSULTA,
            "mensagem": mensagem,
        }


async def rotear_consulta_processo(processo, modo_silencioso_sem_robo=False):

    processo_id = processo.get("id")
    numero_processo = processo.get("numero_processo")

    nome_robo = processo.get("robo") or processo.get("chave_robo")

    # atende_net = mesma plataforma IPM/AtendNet usada por Pinhais e Araucária
    if nome_robo == "atende_net":
        return await consultar_com_robo(
            processo=processo,
            nome_robo="atende_net",
            funcao_consulta=consultar_processo_pinhais,
        )

    if nome_robo == "curitiba":
        return await consultar_com_robo(
            processo=processo,
            nome_robo="curitiba",
            funcao_consulta=consultar_processo_curitiba,
        )

    if nome_robo == "sjp":
        return await consultar_com_robo(
            processo=processo,
            nome_robo="sjp",
            funcao_consulta=consultar_processo_sjp,
        )

    if nome_robo == "esic":  # ✅ AGORA VAI FUNCIONAR!
        from robots.esic.robot import consultar_processo_esic

        return await consultar_com_robo(
            processo=processo,
            nome_robo="esic",
            funcao_consulta=consultar_processo_esic,
        )
    
    if nome_robo == "caieiras":
        from robots.caieiras.robot import consultar_processo_caieiras

        return await consultar_com_robo(
            processo=processo,
            nome_robo="caieiras",
            funcao_consulta=consultar_processo_caieiras,
        )
    
    if nome_robo == "franco_rocha":
        return await consultar_com_robo(
            processo=processo,
            nome_robo="franco_rocha",
            funcao_consulta=consultar_processo_franco_rocha,
        )
    
    if nome_robo == "ponta_grossa":
        from robots.ponta_grossa.robot import consultar_processo_ponta_grossa

        return await consultar_com_robo(
            processo=processo,
            nome_robo="ponta_grossa",
            funcao_consulta=consultar_processo_ponta_grossa,
        )
    
    if nome_robo == "pinhais":
        return await consultar_com_robo(
            processo=processo,
            nome_robo="pinhais",
            funcao_consulta=consultar_processo_pinhais,
        )

    if nome_robo == "ridigital":
        return await consultar_com_robo(
            processo=processo,
            nome_robo="ridigital",
            funcao_consulta=consultar_processo_ridigital,
        )

    registrar_historico_consulta(
        processo_id=processo_id,
        status=STATUS_SEM_ROBO_CONFIGURADO,
        mensagem=f"Não existe robô configurado para: {nome_robo}",
    )

    return {
        "status": STATUS_SEM_ROBO_CONFIGURADO,
        "mensagem": f"Não existe robô configurado para: {nome_robo}",
    }

async def scheduler_monitoramento():
    log.info("Modo automatico iniciado — executa todo dia as 08h00")

    while True:
        agora = datetime.now()
        log.info(f"Execucao iniciada em: {agora.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            await monitorar_processos_ativos()
        except Exception as e:
            log.error(f"Erro na execucao automatica: {e}")

        agora = datetime.now()
        proximo = agora.replace(hour=8, minute=0, second=0, microsecond=0)
        if proximo <= agora:
            proximo += timedelta(days=1)

        segundos_restantes = int((proximo - agora).total_seconds())
        log.info(f"Proxima execucao: {proximo.strftime('%Y-%m-%d %H:%M:%S')} (em {segundos_restantes // 3600}h{(segundos_restantes % 3600) // 60}min)")

        await asyncio.sleep(segundos_restantes)