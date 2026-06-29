from datetime import datetime

from database.repositories import (
    listar_orgaos,
    listar_processos_ativos_com_orgao,
    registrar_historico_consulta,
    registrar_movimentacao,
    atualizar_caminho_solicitacao_captcha,
    limpar_caminho_solicitacao_captcha,
)

from robots.curitiba.robot import consultar_processo_curitiba

from robots.atendenet_v2.robot import consultar_processo_pinhais

from services.relatorio_execucao_service import salvar_relatorio_execucao

from robots.sjp.robot import consultar_processo_sjp

from database.repositories import atualizar_dados_processo

from robots.franco_rocha.robot import consultar_processo_franco_rocha

import asyncio

fila_processos = asyncio.Queue()


STATUS_SEM_ROBO_CONFIGURADO = "SEM_ROBO_CONFIGURADO"
STATUS_ERRO_CONSULTA = "ERRO_CONSULTA"
STATUS_PENDENTE_INTEGRACAO_CAPTCHA = "PENDENTE_INTEGRACAO_CAPTCHA"
STATUS_CAPTCHA_RESOLVIDO_FLUXO_PENDENTE = "CAPTCHA_RESOLVIDO_FLUXO_PENDENTE"


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

    print("\n========================================")
    print("RESUMO DA EXECUÇÃO")
    print("========================================")
    print(f"Total de processos: {resumo.get('TOTAL_PROCESSOS', 0)}")
    print(f"Nova movimentação: {resumo.get('NOVA_MOVIMENTACAO', 0)}")
    print(f"Sem nova movimentação: {resumo.get('SEM_NOVA_MOVIMENTACAO', 0)}")
    print(f"Processo não encontrado: {resumo.get('PROCESSO_NAO_ENCONTRADO', 0)}")
    print(f"Erro de consulta: {resumo.get('ERRO_CONSULTA', 0)}")
    print(f"Sistema fora: {resumo.get('SISTEMA_FORA', 0)}")
    print(f"Sem robô configurado: {resumo.get('SEM_ROBO_CONFIGURADO', 0)}")
    print(f"Pendente integração captcha: {resumo.get('PENDENTE_INTEGRACAO_CAPTCHA', 0)}")
    print(
        "Captcha resolvido com fluxo pendente: "
        f"{resumo.get('CAPTCHA_RESOLVIDO_FLUXO_PENDENTE', 0)}"
    )
    print(f"OK: {resumo.get('OK', 0)}")
    print(f"Tempo total: {formatar_tempo(tempo_total)}")
    print("========================================")

    if resumo.get("ORGAOS_SEM_ROBO"):
        print("\n=== ÓRGÃOS/LINKS SEM ROBÔ CONFIGURADO ===")

        for item in resumo["ORGAOS_SEM_ROBO"].values():
            print("\n----------------------------------------")
            print(f"Órgão: {item['nome']}")
            print(f"Total de processos: {item['total']}")
            print(f"URL: {item['url']}")


def validar_orgaos_importados():
    orgaos = listar_orgaos()

    print("\n=== ÓRGÃOS / LINKS IMPORTADOS ===")

    if not orgaos:
        print("Nenhum órgão encontrado no banco.")
        return

    for orgao in orgaos:
        print("\n----------------------------------------")
        print(f"ID: {orgao.get('id')}")
        print(f"Nome: {orgao.get('nome')}")
        print(f"Tipo: {orgao.get('tipo')}")
        print(f"URL: {orgao.get('url')}")
        print(f"Chave robô: {orgao.get('chave_robo')}")


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

    print("\n=== MONITORAMENTO DE PROCESSOS ATIVOS ===")
    print(f"Total de processos encontrados: {len(processos)}")

    if not processos:
        print("Nenhum processo ativo encontrado.")

        exibir_resumo_execucao(resumo, inicio_execucao)

        caminho_relatorio = salvar_relatorio_execucao(
            resumo=resumo,
            inicio_execucao=inicio_execucao,
            eventos_processos=eventos_processos,
        )

        print(f"\nRelatório salvo em: {caminho_relatorio}")
        return

    # ==========================================================
    # ✅ AGRUPA PROCESSOS POR ROBÔ
    # ==========================================================
    processos_por_robo = {}

    for processo in processos:
        nome_robo = processo.get("robo") or processo.get("chave_robo")
        processos_por_robo.setdefault(nome_robo, []).append(processo)

    # ==========================================================
    # ✅ EXECUÇÃO POR ROBÔ
    # ==========================================================
    for nome_robo, lista_processos in processos_por_robo.items():

        print(f"\n🚀 Processando robô: {nome_robo}")
        print(f"Total de processos: {len(lista_processos)}")

        # ======================================================
        # 🔥 FRANCO DA ROCHA (MODO OTIMIZADO)
        # ======================================================
        if nome_robo == "franco_rocha":

            try:
                resultado_lista = await consultar_processo_franco_rocha(lista_processos[0])

                texto = resultado_lista.get("texto_completo", "")

                for processo in lista_processos:

                    numero = str(processo.get("numero_processo"))

                    print(f"\n🔎 Processando processo {numero}")

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

            except Exception as e:
                print(f"❌ Erro no robô Franco da Rocha: {e}")

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

    print(f"\nRelatório salvo em: {caminho_relatorio}")


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
            f"Robô: {processo.get('robo') or processo.get('chave_robo')}"
        )

    escolha = input("\nDigite o número do processo para testar: ").strip()

    if not escolha.isdigit():
        print("Opção inválida.")
        return

    indice_escolhido = int(escolha)

    if indice_escolhido < 1 or indice_escolhido > len(processos):
        print("Processo não encontrado na lista.")
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


async def consultar_com_robo(
    processo,
    nome_robo,
    funcao_consulta,
):
    processo_id = processo.get("id")

    print("\n========================================")
    print(f"Processo ID: {processo_id}")
    print(f"Número: {processo.get('numero_processo')}")
    print(f"Empresa: {processo.get('empresa')}")
    print(f"Município: {processo.get('municipio')}")
    print(f"Órgão: {processo.get('nome_orgao')}")
    print(f"Robô: {nome_robo}")

    try:
        resultado = await funcao_consulta(processo)

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
            print("✅ Entrou no bloco de movimentações")

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
            print("✅ Entrou no bloco estruturado")

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
            print("❌ Sem dados válidos (não monitorado)")

        # =====================================================
        # ✅ ATUALIZA SOMENTE SE FOI MONITORADO
        # =====================================================
        print("⚙️ Atualizando banco (sempre)")

        atualizar_dados_processo(
            processo_id,
            status_processo,
            data_ultimo_movimento,
            ultima_movimentacao,
            monitorado
        )

        if monitorado:
            print("✅ Monitorado com sucesso")
        else:
            print("🚫 Não monitorado (falha na consulta)")

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

        print(f"Status final: {status}")

        return resultado

    except Exception as erro:
        mensagem = str(erro)

        registrar_historico_consulta(
            processo_id=processo_id,
            status=STATUS_ERRO_CONSULTA,
            mensagem=mensagem,
        )

        print(f"Erro ao consultar processo: {mensagem}")

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
    print("\n🚀 MODO AUTOMÁTICO INICIADO")

    while True:
        agora = datetime.now()

        print("\n========================================")
        print(f"⏱️ Execução iniciada em: {agora.strftime('%d/%m/%Y %H:%M:%S')}")
        print("========================================")

        try:
            await monitorar_processos_ativos()
        except Exception as e:
            print(f"❌ Erro na execução automática: {e}")

        # calcula tempo até próxima hora cheia
        agora = datetime.now()
        segundos_passados = agora.minute * 60 + agora.second
        segundos_restantes = 3600 - segundos_passados

        print(f"\n⏳ Próxima execução em {segundos_restantes} segundos...")

        await asyncio.sleep(segundos_restantes)