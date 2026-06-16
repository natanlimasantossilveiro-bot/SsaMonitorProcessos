from datetime import datetime

from database.repositories import (
    listar_orgaos,
    listar_processos_ativos_com_orgao,
    registrar_historico_consulta,
)

from robots.curitiba.robot import consultar_processo_curitiba
from robots.atende_net.robot import consultar_processo_atende_net

from services.relatorio_execucao_service import salvar_relatorio_execucao


STATUS_SEM_ROBO_CONFIGURADO = "SEM_ROBO_CONFIGURADO"
STATUS_ERRO_CONSULTA = "ERRO_CONSULTA"
STATUS_PENDENTE_INTEGRACAO_CAPTCHA = "PENDENTE_INTEGRACAO_CAPTCHA"


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


async def monitorar_processos_ativos():
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

    for processo in processos:
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
            f"Robô: {processo.get('chave_robo')}"
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
    chave_robo = processo.get("chave_robo")

    if chave_robo == "curitiba":
        return await consultar_com_robo(
            processo=processo,
            nome_robo="curitiba",
            funcao_consulta=consultar_processo_curitiba,
        )

    if chave_robo == "atende_net":
        return await consultar_com_robo(
            processo=processo,
            nome_robo="atende_net",
            funcao_consulta=consultar_processo_atende_net,
        )

    registrar_historico_consulta(
        processo_id=processo_id,
        status=STATUS_SEM_ROBO_CONFIGURADO,
        mensagem=f"Não existe robô configurado para a chave: {chave_robo}",
    )

    if not modo_silencioso_sem_robo:
        print("\n========================================")
        print(f"Processo ID: {processo_id}")
        print(f"Número: {numero_processo}")
        print(f"Empresa: {processo.get('empresa')}")
        print(f"Município: {processo.get('municipio')}")
        print(f"Órgão: {processo.get('nome_orgao')}")
        print(f"Robô: {chave_robo}")
        print("Status final: SEM_ROBO_CONFIGURADO")

    return {
        "status": STATUS_SEM_ROBO_CONFIGURADO,
        "mensagem": f"Não existe robô configurado para a chave: {chave_robo}",
    }