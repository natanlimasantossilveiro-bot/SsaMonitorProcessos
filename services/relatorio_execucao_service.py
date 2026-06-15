import os
from datetime import datetime


PASTA_RELATORIOS = "relatorios"


def criar_pasta_relatorios():
    if not os.path.exists(PASTA_RELATORIOS):
        os.makedirs(PASTA_RELATORIOS)


def formatar_tempo(segundos):
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segundos = int(segundos % 60)

    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def gerar_nome_arquivo_relatorio():
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(
        PASTA_RELATORIOS,
        f"monitoramento_{agora}.txt"
    )


def salvar_relatorio_execucao(resumo, inicio_execucao, eventos_processos):
    criar_pasta_relatorios()

    fim_execucao = datetime.now()
    tempo_total = (fim_execucao - inicio_execucao).total_seconds()

    caminho_arquivo = gerar_nome_arquivo_relatorio()

    with open(caminho_arquivo, "w", encoding="utf-8") as arquivo:
        arquivo.write("========================================\n")
        arquivo.write("RELATÓRIO DE MONITORAMENTO DE PROCESSOS\n")
        arquivo.write("========================================\n")
        arquivo.write(f"Início: {inicio_execucao.strftime('%d/%m/%Y %H:%M:%S')}\n")
        arquivo.write(f"Fim: {fim_execucao.strftime('%d/%m/%Y %H:%M:%S')}\n")
        arquivo.write(f"Tempo total: {formatar_tempo(tempo_total)}\n\n")

        arquivo.write("=== RESUMO DA EXECUÇÃO ===\n")
        arquivo.write(f"Total de processos: {resumo.get('TOTAL_PROCESSOS', 0)}\n")
        arquivo.write(f"Nova movimentação: {resumo.get('NOVA_MOVIMENTACAO', 0)}\n")
        arquivo.write(f"Sem nova movimentação: {resumo.get('SEM_NOVA_MOVIMENTACAO', 0)}\n")
        arquivo.write(f"Processo não encontrado: {resumo.get('PROCESSO_NAO_ENCONTRADO', 0)}\n")
        arquivo.write(f"Erro de consulta: {resumo.get('ERRO_CONSULTA', 0)}\n")
        arquivo.write(f"Sistema fora: {resumo.get('SISTEMA_FORA', 0)}\n")
        arquivo.write(f"Sem robô configurado: {resumo.get('SEM_ROBO_CONFIGURADO', 0)}\n")
        arquivo.write(f"OK: {resumo.get('OK', 0)}\n\n")

        arquivo.write("=== EVENTOS POR PROCESSO ===\n")

        if not eventos_processos:
            arquivo.write("Nenhum evento registrado.\n")
        else:
            for evento in eventos_processos:
                arquivo.write("----------------------------------------\n")
                arquivo.write(f"Processo ID: {evento.get('processo_id')}\n")
                arquivo.write(f"Número: {evento.get('numero_processo')}\n")
                arquivo.write(f"Empresa: {evento.get('empresa')}\n")
                arquivo.write(f"Município: {evento.get('municipio')}\n")
                arquivo.write(f"Órgão: {evento.get('orgao')}\n")
                arquivo.write(f"Robô: {evento.get('chave_robo')}\n")
                arquivo.write(f"Status: {evento.get('status')}\n")
                arquivo.write(f"Mensagem: {evento.get('mensagem')}\n")

        if resumo.get("ORGAOS_SEM_ROBO"):
            arquivo.write("\n=== ÓRGÃOS/LINKS SEM ROBÔ CONFIGURADO ===\n")

            for item in resumo["ORGAOS_SEM_ROBO"].values():
                arquivo.write("----------------------------------------\n")
                arquivo.write(f"Órgão: {item['nome']}\n")
                arquivo.write(f"Total de processos: {item['total']}\n")
                arquivo.write(f"URL: {item['url']}\n")

    return caminho_arquivo