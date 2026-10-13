@'
# PPP-IFSC

Comparação entre coordenadas obtidas pelo IBGE-PPP e a coordenada oficial da estação IFSC (RBMC/IBGE).

## Sobre o trabalho

Trabalho do Módulo III — Programação Aplicada ao Geoprocessamento (IFSC, 2026-2).

Pergunta central: se processarmos os dados da estação IFSC no IBGE-PPP como se ela fosse um ponto desconhecido, quanto o resultado se afasta da coordenada oficial? Esse afastamento muda entre o meio-dia e a meia-noite?

## Como o programa funciona

1. Obtém a coordenada oficial da estação via API do BDG (IBGE)
2. Baixa os arquivos de observação do servidor IFSC
3. Descompacta Hatanaka com CRX2RNX
4. Junta os arquivos em janelas de 4h com GFZRNX
5. Reamostra para 30s
6. Envia cada janela ao IBGE-PPP via API
7. Compara cada resultado com a coordenada oficial
8. Gera gráficos

## Estrutura

- src/1_baixar.py - baixa arquivos do servidor IFSC
- src/2_descompactar.py - descompacta Hatanaka
- src/3_juntar.py - junta arquivos com GFZRNX
- src/4_enviar.py - envia ao IBGE-PPP
- src/5_comparar.py - compara com a coordenada oficial
- src/6_loop.py - roda tudo nas datas x janelas
- src/7_graficos.py - gera os gráficos

## Como rodar

python -m venv .venv
.venv\Scripts\activate
python -m pip install requests pandas matplotlib pyproj
python src\6_loop.py
python src\7_graficos.py

## Referências

- IBGE-PPP Manual do Usuário (2023)
- FRANÇA, R. M.; ARAÚJO, A. L.; LIMA, A. P. B. COBRAC 2024
- GFZRNX - GFZ Potsdam
'@ | Out-File -FilePath README.md -Encoding utf8