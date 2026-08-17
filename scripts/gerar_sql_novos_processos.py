processos = [
    # (numero_processo, orgao_id)
    # Orgao nao informado (11)
    ("42.015.001.21-0000551",      11),
    ("23.1003.10001-00096301",     11),
    ("2403005600100200000",        11),
    ("24.09.0063.001.00386-3",     11),
    ("2510004400100119301",        11),
    ("2510005600101728302",        11),
    ("2511005600100243302",        11),
    ("2601031000100850301",        11),
    ("2601031000100850302",        11),
    ("2601031000101048301",        11),
    ("2603005600100138301",        11),
    ("2512005600100491302",        11),
    ("2512005600100491301",        11),
    ("2602031000101012302",        11),
    ("2602031000101012301",        11),
    ("2602031000100821301",        11),
    ("2602031000100821302",        11),
    ("2603031000100380302",        11),
    ("2603031000100380301",        11),
    ("2602031000101084302",        11),
    ("2602031000101084301",        11),
    ("2603031000100029302",        11),
    ("2603031000100029301",        11),
    ("2602031000101122302",        11),
    ("2602031000101122301",        11),
    ("2603031000100133301",        11),
    ("2603031000100133302",        11),
    ("2602031000101164301",        11),
    ("2602005600100750301",        11),
    ("2602003900102345301",        11),
    ("2603003900100354301",        11),
    ("2604031000100687301",        11),
    ("2604031000100687302",        11),
    ("2604003900100101302",        11),
    ("19362/2025",                 11),
    ("59363/2026",                 11),
    ("12270",                      11),
    ("02023.005045/2025-02",       11),
    ("02023.002189/2025-07",       11),
    # Curitiba (1)
    ("01-080428/2026",              1),
    ("01-151537/2026",              1),
    ("01-151540/2026",              1),
    # Caieiras (10)
    ("19362",                      10),
    # Orgao nao informado - prefixo 02- (averiguar responsavel)
    ("02-006172/2026",             11),
    ("02-006497/2026",             11),
    ("02-006498/2026",             11),
    ("02-006500/2026",             11),
    ("02-006502/2026",             11),
    ("02-006503/2026",             11),
]

linhas = [
    "-- Insercao de processos novos (pula duplicatas)",
    "-- Execute no VPS: sudo mysql ssa_monitor_processos < inserir_novos_processos.sql",
    "",
]

for num, orgao in processos:
    linhas.append(
        "INSERT INTO processos (orgao_id, empresa, numero_processo, ativo) "
        "SELECT {}, 'PREENCHER', '{}', 1 "
        "FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM processos WHERE numero_processo = '{}');".format(
            orgao, num, num
        )
    )

linhas.append("")
linhas.append("SELECT COUNT(*) AS total_processos FROM processos;")

sql = "\n".join(linhas)
with open("inserir_novos_processos.sql", "w", encoding="utf-8") as f:
    f.write(sql)

print("Gerado: {} processos".format(len(processos)))
print("Arquivo: inserir_novos_processos.sql")
