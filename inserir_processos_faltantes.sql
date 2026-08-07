-- =================================================================
-- Inserção em massa — processos faltantes
-- Gerado: 07/08/2026
--
-- Mapeamento de órgãos (tabela orgaos):
--   ID  1 → Prefeitura Municipal de Curitiba  (robo: curitiba)
--   ID  3 → Ponta Grossa                      (robo: ponta_grossa)
--   ID  5 → Araucária                         (robo: atende_net)
--   ID 10 → Caieiras                          (robo: caieiras)
--   ID 11 → Órgão não informado               (robo: NULL)
--
-- ATENÇÃO antes de executar:
--   • Linha marcada [EMPRESA?]: preencher empresa antes de rodar
--   • Linhas marcadas [REVISAR ÓRGÃO]: confirmar prefeitura correta
-- =================================================================

INSERT INTO processos
    (orgao_id, empresa, cnpj, municipio, numero_processo, cliente)
VALUES

-- ── Araucária (ID 5) — formato AC… ──────────────────────────
(5, 'D. Borcath',  NULL, 'Araucária', 'AC004299410', 'D. Borcath'),
(5, 'Rajasthan',   NULL, 'Araucária', 'AC014015420', 'Rajasthan'),
(5, 'Terrasse',    NULL, 'Araucária', 'AC014130529', 'Terrasse'),
(5, 'Withers',     NULL, 'Araucária', 'AC014276629', 'Withers'),
(5, 'Pessoa',      NULL, 'Araucária', 'AC015480244', 'Pessoa'),
(5, 'Pessoa',      NULL, 'Araucária', 'AC015589195', 'Pessoa'),
(5, 'Pessoa',      NULL, 'Araucária', 'AC015816458', 'Pessoa'),
(5, 'Pessoa',      NULL, 'Araucária', 'AC015589335', 'Pessoa'),
(5, 'Pessoa',      NULL, 'Araucária', 'AC015938344', 'Pessoa'),
(5, 'Vanguard',    NULL, 'Araucária', 'AC015641151', 'Vanguard'),
(5, 'Vanguard',    NULL, 'Araucária', 'AC015930048', 'Vanguard'),
(5, 'Vanguard',    NULL, 'Araucária', 'AC015639265', 'Vanguard'),
(5, 'Vanguard',    NULL, 'Araucária', 'AC015930027', 'Vanguard'),
(5, 'Equilíbrio',  NULL, 'Araucária', 'AC015721529', 'Equilíbrio'),
(5, 'Pastre',      NULL, 'Araucária', 'AC015744556', 'Pastre'),
(5, 'Pastre',      NULL, 'Araucária', 'AC015744590', 'Pastre'),
(5, 'Pastre',      NULL, 'Araucária', 'AC015744622', 'Pastre'),
(5, 'Pastre',      NULL, 'Araucária', 'AC015744673', 'Pastre'),
(5, 'San Remo',    NULL, 'Araucária', 'AC015910112', 'San Remo'),
(5, 'Equilíbrio',  NULL, 'Araucária', 'AC015930084', 'Equilíbrio'),

-- ── Araucária (ID 5) — formato 02-006XXX/2026 ───────────────
(5, 'DG4',  NULL, 'Araucária', '02-006172/2026', 'DG4'),
(5, 'Fito', NULL, 'Araucária', '02-006497/2026', 'Fito'),
(5, 'Fito', NULL, 'Araucária', '02-006498/2026', 'Fito'),
(5, 'Fito', NULL, 'Araucária', '02-006500/2026', 'Fito'),
(5, 'Fito', NULL, 'Araucária', '02-006502/2026', 'Fito'),
(5, 'Fito', NULL, 'Araucária', '02-006503/2026', 'Fito'),

-- ── Curitiba (ID 1) — formato 01-151XXX/2026 ────────────────
(1, 'Fito', NULL, 'Prefeitura Municipal de Curitiba', '01-151516/2026', 'Fito'),
(1, 'Fito', NULL, 'Prefeitura Municipal de Curitiba', '01-151520/2026', 'Fito'),
(1, 'Fito', NULL, 'Prefeitura Municipal de Curitiba', '01-151528/2026', 'Fito'),
(1, 'Fito', NULL, 'Prefeitura Municipal de Curitiba', '01-151537/2026', 'Fito'),
(1, 'Fito', NULL, 'Prefeitura Municipal de Curitiba', '01-151540/2026', 'Fito'),

-- ── Curitiba (ID 1) — outros ────────────────────────────────
-- [EMPRESA? — preencher o nome da empresa antes de executar]
(1, 'PREENCHER',  NULL, 'Prefeitura Municipal de Curitiba', '01-149925', 'PREENCHER'),

-- ── Ponta Grossa (ID 3) — [REVISAR ÓRGÃO se não for PG] ─────
(3, 'AMF',         NULL, 'Ponta Grossa', '90451/2025', 'AMF'),

-- ── Caieiras (ID 10) ────────────────────────────────────────
(10, 'Golgi FII',  NULL, 'Caieiras', '19362', 'Golgi FII'),

-- ── Órgão não identificado (ID 11) — [REVISAR ÓRGÃO] ────────
(11, 'Arch Capital', NULL, 'Órgão não informado', '19362/2025',           'Arch Capital'),
(11, 'Vanguard',     NULL, 'Órgão não informado', '02023.005045/2025-02', 'Vanguard'),
(11, 'Vanguard',     NULL, 'Órgão não informado', '02023.002189/2025-07', 'Vanguard');

-- Confirma o que foi inserido
SELECT p.id, p.numero_processo, p.empresa, o.nome AS orgao
FROM processos p
JOIN orgaos o ON o.id = p.orgao_id
WHERE p.numero_processo IN (
    'AC004299410','AC014015420','AC014130529','AC014276629','AC015480244',
    'AC015589195','AC015816458','AC015589335','AC015938344','AC015641151',
    'AC015930048','AC015639265','AC015930027','AC015721529','AC015744556',
    'AC015744590','AC015744622','AC015744673','AC015910112','AC015930084',
    '02-006172/2026','02-006497/2026','02-006498/2026','02-006500/2026',
    '02-006502/2026','02-006503/2026',
    '01-151516/2026','01-151520/2026','01-151528/2026','01-151537/2026',
    '01-151540/2026','01-149925','90451/2025','19362',
    '19362/2025','02023.005045/2025-02','02023.002189/2025-07'
)
ORDER BY o.nome, p.numero_processo;
