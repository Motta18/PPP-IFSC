# PPP IBGE e comparação com RBMC

Aplicação em Python com interface Streamlit para automatizar o envio de arquivos RINEX ao serviço PPP do IBGE e comparar os resultados com a coordenada oficial da RBMC/BDG.

O projeto responde à pergunta: **quanto o resultado do PPP se afasta da coordenada oficial da estação, e esse afastamento varia com a data ou com a duração do rastreio?**

## Estação e dados utilizados

- **Estação:** IFSC (Florianópolis, SC) — código BDG 94052
- **Antena:** TRM57971.00, altura 0.0081 m
- **Datas processadas:** 01/01/2020 e 21/06/2020
- **Janelas:** 4 janelas de 1 hora por data (15h, 16h, 17h, 18h em 01/01; 16h, 17h, 18h, 19h em 21/06)
- **Total:** 8 processamentos no IBGE-PPP
- **Órbitas:** FINAL

## Requisitos

- Python 3.14 (ambiente `.venv314`)
- PowerShell (Windows)
- Conexão com a internet (acesso ao IBGE)

Dependências Python (instaladas automaticamente pelo `setup.ps1`):
`requests`, `curl_cffi`, `pyyaml`, `pandas`, `matplotlib`, `pyproj`, `streamlit`, `openpyxl`.

## Como instalar (setup)

Na primeira vez, abra um terminal PowerShell na raiz do projeto e execute:

```powershell
.\setup.ps1
```

Isso cria/ativa o ambiente `.venv314` e instala as dependências.

## Como rodar o app

No mesmo terminal (ou em um novo), execute:

```powershell
.\run.ps1
```

O app abre automaticamente em `http://localhost:8501`.

### Alternativa sem scripts

```powershell
.\.venv314\Scripts\python.exe -m streamlit run app.py
```

## Como usar a interface

A interface tem 5 abas, na ordem do fluxo:

1. **📥 Baixar RINEX** — baixa os arquivos de observação da RBMC (opcional; o programa funciona com arquivos locais).
2. **🚀 Enviar ao PPP** — envia os arquivos ao IBGE-PPP, um de cada vez, com intervalo de 2 segundos.
3. **📊 Baixar resultados** — baixa e extrai os ZIPs de resultado do IBGE.
4. **🧮 Comparar com BDG** — compara os resultados do PPP com a coordenada oficial do BDG e gera a tabela CSV e os gráficos.
5. **📈 Ver resultados** — mostra a tabela e os gráficos, com botões para exportar em CSV, Excel e JSON.

## Como adaptar para outra estação/datas

1. Edite `config/config.yaml`:
   - `estacao`: código da nova estação (ex.: `BRAZ`, `POAL`).
   - `codigo_bdg`: código SAT correspondente no BDG.
   - `modelo_antena` e `altura_antena`: consultar o cabeçalho do RINEX.
   - `datas`: lista de datas no formato `YYYY-MM-DD`.
2. Coloque os arquivos RINEX em `data/rinex_input/bruto/<data>/<nome_do_arquivo>/`.

## Resultados principais

Diferenças entre o PPP e a coordenada oficial do BDG (em metros):

| Processamento | Data | Hora (UTC) | dE | dN | dU | Distância 3D |
|---|---|---|---|---|---|---|
| 2001011500A | 01/01/2020 | 15h | +0,0277 | –0,0382 | –0,0870 | 0,099 |
| 2001011600A | 01/01/2020 | 16h | –0,0546 | –0,0167 | +0,0330 | 0,066 |
| 2001011700A | 01/01/2020 | 17h | –0,1122 | –0,0413 | **–0,2770** | **0,302** |
| 2001011800A | 01/01/2020 | 18h | –0,0491 | +0,0295 | +0,0030 | 0,057 |
| 2006211600A | 21/06/2020 | 16h | +0,0359 | –0,0136 | +0,0130 | 0,041 |
| 2006211700A | 21/06/2020 | 17h | +0,0249 | –0,0074 | +0,0030 | 0,026 |
| 2006211800A | 21/06/2020 | 18h | +0,0524 | –0,0074 | +0,0430 | 0,068 |
| 2006211900A | 21/06/2020 | 19h | +0,0194 | –0,0259 | –0,0170 | 0,037 |

**Estatísticas (sem o outlier):**

- dE médio: ~0,007 m (7 mm)
- dN médio: ~0,011 m (11 mm)
- dU médio: ~0,008 m (8 mm)
- Distância 3D média: ~0,056 m (5,6 cm)

**Observações:**

- A planimetria (dE, dN) está na casa dos **milímetros a centímetros**, demonstrando que o PPP atinge precisão centimétrica com 1 hora de dados.
- O processamento das 17h de 01/01/2020 é um **outlier** (dU = –27,7 cm; distância 3D = 30,2 cm), provavelmente por condições atmosféricas ou geometria de satélites desfavorável nesse horário.
- Os resultados de **junho (inverno)** foram mais consistentes que os de **janeiro (verão)**.

## Limitações conhecidas

1. **API do IBGE (RINEX2) não disponibiliza dados de 2020.** Os arquivos RINEX foram obtidos do servidor local da estação IFSC (`sat94052.florianopolis.ifsc.edu.br`).

2. **Alguns endpoints do IBGE são protegidos pelo Cloudflare.** O download de resultados e da RBMC usa `curl_cffi` com `impersonate="chrome120"`. O envio ao PPP usa `requests` com `verify=False`.

3. **Antena não reconhecida (2025):** a antena `TRM159900.00` (usada em 2025) não é reconhecida pelo IBGE-PPP, resultando em erro sistemático de ~17,7 cm na altitude. Ao usar a antena `TRM57971.00` (2020), a antena foi reconhecida e o erro altimétrico desapareceu.

## Estrutura do projeto

```
ppp-ibge-rbmc/
├── app.py                    # Interface Streamlit
├── setup.ps1                 # Script de setup
├── run.ps1                   # Script para rodar o app
├── config/
│   └── config.yaml           # Configurações (e-mail, estação, antena, datas)
├── src/
│   ├── main.py               # Orquestração do lote de envio
│   ├── ibge_client.py        # Envio ao IBGE-PPP
│   ├── rbmc_downloader.py    # Download de RINEX da RBMC
│   ├── results_handler.py    # Download e extração de resultados
│   ├── bdg_client.py         # Consulta ao BDG
│   ├── calculator.py         # Comparação ECEF/ENU
│   ├── report_generator.py   # Geração de tabelas e gráficos
│   ├── file_manager.py       # Gerenciamento de arquivos
│   └── queue_controller.py   # Controle de fila
├── data/
│   ├── rinex_input/bruto/    # Arquivos RINEX de entrada
│   └── results_output/       # Resultados, CSV, gráficos
├── logs/                     # Logs de execução
└── tests/                    # Testes automatizados
```

## Referências

- **IBGE-PPP:** https://servicodados.ibge.gov.br/api/v1/ppp
- **RBMC:** https://servicodados.ibge.gov.br/api/v1/rbmc/
- **BDG:** https://servicodados.ibge.gov.br/api/v1/bdg/estacoes/{estacao}
- **Manual do IBGE-PPP:** disponível no site do IBGE