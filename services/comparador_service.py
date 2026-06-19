from database.repositories import buscar_processo_por_id


def comparar_processo(processo_id, dados_novos):
    processo_atual = buscar_processo_por_id(processo_id)

    alteracoes = []

    if not processo_atual:
        return alteracoes

    # STATUS
    status_antigo = processo_atual.get("status_atual")
    status_novo = dados_novos.get("situacao")

    if status_antigo != status_novo:
        alteracoes.append({
            "tipo": "STATUS_ALTERADO",
            "antes": status_antigo,
            "depois": status_novo
        })

    # RESPONSÁVEL
    responsavel_antigo = processo_atual.get("responsavel")
    responsavel_novo = dados_novos.get("responsavel")

    if responsavel_antigo != responsavel_novo:
        alteracoes.append({
            "tipo": "RESPONSAVEL_ALTERADO",
            "antes": responsavel_antigo,
            "depois": responsavel_novo
        })

    return alteracoes