# PPP-IFSC

Comparação entre coordenadas obtidas pelo **IBGE-PPP** e a **coordenada oficial** da estação **IFSC** (RBMC/IBGE), avaliando o afastamento ao longo de diferentes datas e entre janelas diurnas e noturnas.

---

## Sobre o trabalho

Trabalho do **Módulo III — Programação Aplicada ao Geoprocessamento** (IFSC, 2026-2).

**Pergunta central:** se processarmos os dados da estação IFSC no IBGE-PPP como se ela fosse um ponto desconhecido, quanto o resultado se afasta da coordenada oficial? Esse afastamento muda entre o meio-dia e a meia-noite?

A estação IFSC está no topo do prédio do DACC (Departamento Acadêmico de Construção Civil) do IFSC, em Florianópolis/SC.

---

## Como o programa funciona

1. Obtém a coordenada oficial da estação via **API do BDG** (IBGE)
2. Baixa os arquivos de observação da estação do **servidor IFSC**
3. Descompacta os arquivos Hatanaka com **CRX2RNX**
4. Junta os arquivos de 15 min em janelas de 4h com **GFZRNX**
5. Reduz o intervalo de amostragem para 30s (para caber no limite da API)
6. Envia cada janela ao **IBGE-PPP** via API
7. Compara cada resultado com a coordenada oficial
8. Gera gráficos que respondem à pergunta

---

## Estrutura do repositório

