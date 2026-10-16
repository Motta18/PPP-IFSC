"""Interface Streamlit inicial para configuração do processamento PPP."""

import json
import sys
import logging
import re
import tempfile
import time
from io import BytesIO
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

# Permite importar módulos do diretório `src` sem pacotes
sys.path.insert(0, "src")
import activity_logger
import rbmc_downloader
from pathlib import Path

import calculator
import report_generator
import results_handler

try:
    import ibge_client
    import main as main_orchestrator
except Exception:
    # Import de módulos locais; erros serão tratados em tempo de execução.
    ibge_client = None
    main_orchestrator = None

LOGGER = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parent
CAMINHO_CONFIG = PROJECT_ROOT / "config" / "config.yaml"
CAMINHO_HISTORICO = PROJECT_ROOT / "data" / "results_output" / "historico_processamentos.json"
DIRETORIO_RESULTADOS = PROJECT_ROOT / "data" / "results_output"

DATAS_PADRAO = [
    "2020-01-01",
    "2020-01-01",
    "2020-01-01",
    "2020-01-01",
    "2020-06-21",
    "2020-06-21",
    "2020-06-21",
    "2020-06-21",
]
CONFIGURACAO_PADRAO = {
    "email": "Delamotta18@gmail.com",
    "diretorio_rinex_bruto": "data/rinex_input/bruto/",
    "estacao": "IFSC",
    "modelo_antena": "TRM57971.00",
    "altura_antena": 0.0081,
    "tipo_levantamento": "estatico",
    "intervalo_envio_segundos": 2,
    "datas": DATAS_PADRAO,
    "codigo_bdg": "94052",
}
CHAVES_WIDGETS = {
    "email": "config_email",
    "diretorio_rinex_bruto": "config_diretorio_rinex",
    "estacao": "config_estacao",
    "modelo_antena": "config_modelo_antena",
    "altura_antena": "config_altura_antena",
    "tipo_levantamento": "config_tipo_levantamento",
    "intervalo_envio_segundos": "config_intervalo_envio",
    "datas_texto": "config_datas_texto",
    "codigo_bdg": "config_codigo_bdg",
}


def _ler_configuracao() -> dict:
    """Lê e valida o arquivo YAML de configuração do projeto."""
    with CAMINHO_CONFIG.open("r", encoding="utf-8") as arquivo:
        configuracao = yaml.safe_load(arquivo)
    if not isinstance(configuracao, dict):
        raise ValueError("O arquivo de configuração deve conter um objeto YAML.")
    return configuracao


def _aplicar_configuracao(configuracao: dict) -> None:
    """Transfere os valores carregados para o estado dos campos da interface."""
    datas = configuracao.get("datas", CONFIGURACAO_PADRAO["datas"])
    datas_normalizadas: list[str] = []
    if isinstance(datas, list):
        for item in datas:
            if isinstance(item, str):
                datas_normalizadas.append(item)
            elif isinstance(item, dict):
                valor = item.get("data")
                if isinstance(valor, str) and valor.strip():
                    datas_normalizadas.append(valor.strip())
    if not datas_normalizadas:
        raise ValueError("O campo 'datas' da configuração deve conter pelo menos uma data.")

    valores = {
        "config_email": configuracao.get("email", CONFIGURACAO_PADRAO["email"]),
        "config_diretorio_rinex": configuracao.get(
            "diretorio_rinex_bruto",
            CONFIGURACAO_PADRAO["diretorio_rinex_bruto"],
        ),
        "config_estacao": configuracao.get("estacao", CONFIGURACAO_PADRAO["estacao"]),
        "config_modelo_antena": configuracao.get(
            "modelo_antena", CONFIGURACAO_PADRAO["modelo_antena"]
        ),
        "config_altura_antena": float(
            configuracao.get("altura_antena", CONFIGURACAO_PADRAO["altura_antena"])
        ),
        "config_tipo_levantamento": configuracao.get(
            "tipo_levantamento", CONFIGURACAO_PADRAO["tipo_levantamento"]
        ),
        "config_intervalo_envio": int(
            configuracao.get(
                "intervalo_envio_segundos",
                CONFIGURACAO_PADRAO["intervalo_envio_segundos"],
            )
        ),
        "config_datas_texto": "\n".join(datas_normalizadas),
        "config_codigo_bdg": configuracao.get(
            "codigo_bdg", CONFIGURACAO_PADRAO["codigo_bdg"]
        ),
    }
    st.session_state.update(valores)


def _obter_datas(texto: str) -> list[str]:
    """Valida e retorna as datas informadas, uma por linha."""
    datas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    for valor in datas:
        try:
            data_convertida = date.fromisoformat(valor)
        except ValueError as exc:
            raise ValueError(
                f"Data inválida: {valor!r}. Use o formato YYYY-MM-DD."
            ) from exc
        if data_convertida.isoformat() != valor:
            raise ValueError(f"Data inválida: {valor!r}. Use o formato YYYY-MM-DD.")
    return datas


def _ultima_data_processamento() -> str:
    """Retorna a data e hora mais recentes registradas no histórico."""
    if not CAMINHO_HISTORICO.exists():
        return "—"
    with CAMINHO_HISTORICO.open("r", encoding="utf-8") as arquivo:
        historico = json.load(arquivo)
    if not isinstance(historico, list):
        raise ValueError("O histórico de processamentos deve conter uma lista JSON.")

    horarios = []
    for item in historico:
        if not isinstance(item, dict) or not item.get("hora_envio"):
            continue
        horarios.append(datetime.fromisoformat(str(item["hora_envio"])))
    if not horarios:
        return "—"
    return max(horarios).strftime("%d/%m/%Y %H:%M")


def _contar_resultados() -> int:
    """Conta as pastas de resultados PPP existentes."""
    if not DIRETORIO_RESULTADOS.exists():
        return 0
    return sum(
        1
        for caminho in DIRETORIO_RESULTADOS.iterdir()
        if caminho.is_dir() and caminho.name.endswith("_resultado")
    )


def listar_rinex_observacao(diretorio_base: Path) -> list[Path]:
    """Lista observações RINEX, mantendo a cópia mais recente por nome."""
    base = Path(diretorio_base)
    if not base.is_absolute():
        base = PROJECT_ROOT / base
    if not base.exists():
        return []

    padrao_observacao = re.compile(r"\.\d{2}[oO]$")
    arquivos_por_nome: dict[str, Path] = {}
    for caminho in base.rglob("*"):
        if not caminho.is_file():
            continue
        if caminho.suffix.lower() != ".rnx" and not padrao_observacao.search(caminho.name):
            continue

        chave_nome = caminho.name.casefold()
        arquivo_atual = arquivos_por_nome.get(chave_nome)
        if (
            arquivo_atual is None
            or caminho.stat().st_mtime > arquivo_atual.stat().st_mtime
        ):
            arquivos_por_nome[chave_nome] = caminho

    return sorted(
        arquivos_por_nome.values(),
        key=lambda caminho: (caminho.name.casefold(), caminho.name),
    )


def _baixar_resultados_da_sessao(envios: list[dict]) -> list[dict]:
    """Usa o downloader existente com um histórico temporário da sessão atual."""
    with tempfile.TemporaryDirectory() as diretorio_temporario:
        caminho_historico_sessao = Path(diretorio_temporario) / "historico.json"
        caminho_historico_sessao.write_text(
            json.dumps(envios, ensure_ascii=False),
            encoding="utf-8",
        )
        return results_handler.baixar_e_extrair_lote(
            caminho_historico_sessao,
            DIRETORIO_RESULTADOS,
        )


def _listar_envios_com_resultado() -> list[dict]:
    """Lê as respostas brutas salvas e reúne os links de resultado disponíveis."""
    envios = []
    for caminho_json in sorted(DIRETORIO_RESULTADOS.glob("*_resposta_bruta.json")):
        with caminho_json.open("r", encoding="utf-8") as arquivo_json:
            resposta = json.load(arquivo_json)
        if not isinstance(resposta, dict):
            raise ValueError(f"A resposta em {caminho_json} não contém um objeto JSON.")
        link = resposta.get("link")
        if not isinstance(link, str) or not link.strip():
            continue
        resumo = resposta.get("resumo", {})
        nome_arquivo = (
            resumo.get("RINEX")
            if isinstance(resumo, dict)
            else None
        )
        if not isinstance(nome_arquivo, str) or not nome_arquivo.strip():
            nome_arquivo = f"{caminho_json.name.removesuffix('_resposta_bruta.json')}.rnx"
        envios.append(
            {
                "nome_arquivo": nome_arquivo,
                "status": "OK",
                "link": link,
            }
        )
    return envios


def _comparar_relatorios(resultados: list[Path]) -> tuple[list[dict], int]:
    """Compara arquivos individualmente, ignorando os inválidos e atualiza saídas."""
    caminho_bdg = DIRETORIO_RESULTADOS / "94052_bdg_resposta_bruta.json"
    coordenada_bdg = calculator.ler_coordenada_bdg(caminho_bdg)
    comparacoes = []
    ignorados = 0
    for caminho in resultados:
        caminho = Path(caminho)
        try:
            report_generator.ler_resumo_ppp(caminho)
            comparacoes.extend(
                report_generator.comparar_todos([caminho], coordenada_bdg)
            )
        except Exception as exc:
            ignorados += 1
            st.warning(f"Arquivo {caminho.name} ignorado: {exc}")

    if comparacoes:
        report_generator.salvar_tabela_csv(
            comparacoes,
            DIRETORIO_RESULTADOS / "comparacao_geral.csv",
        )
        report_generator.gerar_graficos(
            comparacoes,
            DIRETORIO_RESULTADOS / "graficos",
        )
    return comparacoes, ignorados


def listar_datas_config() -> list[str]:
    """Lê o arquivo de configuração YAML e retorna a lista de datas.

    Aceita tanto o formato antigo (lista de strings) quanto o formato novo
    usado por config.yaml, onde cada entrada contém `data` e `horas`.
    """
    try:
        with CAMINHO_CONFIG.open("r", encoding="utf-8") as arquivo:
            cfg = yaml.safe_load(arquivo)
    except Exception as exc:
        LOGGER.debug("Não foi possível ler %s: %s", CAMINHO_CONFIG, exc)
        return []
    if not isinstance(cfg, dict):
        return []
    datas = cfg.get("datas", [])
    if not isinstance(datas, list):
        return []

    resultado: list[str] = []
    for item in datas:
        if isinstance(item, str):
            resultado.append(item)
        elif isinstance(item, dict):
            valor = item.get("data")
            if isinstance(valor, str) and valor.strip():
                resultado.append(valor.strip())
    return resultado


st.set_page_config(
    page_title="PPP IBGE - IFSC vs BDG",
    page_icon="🛰️",
    layout="wide",
)

if "configuracao_pendente" in st.session_state:
    _aplicar_configuracao(st.session_state.pop("configuracao_pendente"))

for chave, valor in CONFIGURACAO_PADRAO.items():
    chave_widget = CHAVES_WIDGETS["datas_texto"] if chave == "datas" else CHAVES_WIDGETS[chave]
    if chave_widget not in st.session_state:
        st.session_state[chave_widget] = "\n".join(valor) if chave == "datas" else valor

st.title("🛰️ Processamento PPP do IBGE - Comparação com a RBMC/BDG")
st.write(
    "Configure e acompanhe o processamento de observações RINEX pelo IBGE-PPP, "
    "com comparação à coordenada oficial da RBMC/BDG."
)

with st.sidebar:
    st.header("⚙️ Configuração")
    st.text_input("E-mail do usuário", key="config_email")
    st.text_input("Diretório dos RINEX", key="config_diretorio_rinex")
    st.text_input("Estação RBMC", key="config_estacao")
    st.text_input("Modelo de antena", key="config_modelo_antena")
    st.number_input(
        "Altura da antena (m)",
        min_value=0.0,
        step=0.0001,
        format="%.4f",
        key="config_altura_antena",
    )
    st.selectbox(
        "Tipo de levantamento",
        options=["estatico", "cinematico"],
        key="config_tipo_levantamento",
    )
    st.number_input(
        "Intervalo entre envios (s)",
        min_value=1,
        max_value=10,
        step=1,
        key="config_intervalo_envio",
    )
    st.text_area(
        "Datas de processamento (uma data YYYY-MM-DD por linha)",
        key="config_datas_texto",
        height=160,
    )
    st.text_input("Código do BDG", key="config_codigo_bdg")

    st.header("💾 Salvar/Ler configuração")
    if st.button("💾 Salvar configuração", use_container_width=True):
        try:
            datas_configuradas = _obter_datas(st.session_state["config_datas_texto"])
            configuracao_existente = (
                _ler_configuracao() if CAMINHO_CONFIG.exists() else {}
            )
            configuracao_existente.update(
                {
                    "email": st.session_state["config_email"],
                    "diretorio_rinex_bruto": st.session_state["config_diretorio_rinex"],
                    "estacao": st.session_state["config_estacao"],
                    "modelo_antena": st.session_state["config_modelo_antena"],
                    "altura_antena": st.session_state["config_altura_antena"],
                    "tipo_levantamento": st.session_state["config_tipo_levantamento"],
                    "intervalo_envio_segundos": st.session_state["config_intervalo_envio"],
                    "datas": datas_configuradas,
                    "codigo_bdg": st.session_state["config_codigo_bdg"],
                }
            )
            CAMINHO_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            with CAMINHO_CONFIG.open("w", encoding="utf-8") as arquivo:
                yaml.safe_dump(
                    configuracao_existente,
                    arquivo,
                    allow_unicode=True,
                    sort_keys=False,
                )
            st.success("Configuração salva com sucesso.")
        except (OSError, ValueError, yaml.YAMLError) as exc:
            st.error(f"Não foi possível salvar a configuração: {exc}")

    if st.button("📂 Carregar configuração", use_container_width=True):
        try:
            st.session_state["configuracao_pendente"] = _ler_configuracao()
            st.rerun()
        except (OSError, ValueError, yaml.YAMLError) as exc:
            st.error(f"Não foi possível carregar a configuração: {exc}")

try:
    datas_atuais = _obter_datas(st.session_state["config_datas_texto"])
except ValueError as exc:
    datas_atuais = []
    st.error(f"Configuração de datas inválida: {exc}")

st.session_state["configuracao_atual"] = {
    "email": st.session_state["config_email"],
    "diretorio_rinex_bruto": st.session_state["config_diretorio_rinex"],
    "estacao": st.session_state["config_estacao"],
    "modelo_antena": st.session_state["config_modelo_antena"],
    "altura_antena": st.session_state["config_altura_antena"],
    "tipo_levantamento": st.session_state["config_tipo_levantamento"],
    "intervalo_envio_segundos": st.session_state["config_intervalo_envio"],
    "datas": datas_atuais,
    "codigo_bdg": st.session_state["config_codigo_bdg"],
}

st.subheader("📌 Status do processamento")
colunas_status = st.columns(4)
colunas_status[0].metric("Estação", st.session_state["config_estacao"])
colunas_status[1].metric("Datas configuradas", len(datas_atuais))
try:
    ultimo_processamento = _ultima_data_processamento()
except (OSError, ValueError, json.JSONDecodeError) as exc:
    ultimo_processamento = "Erro ao ler"
    st.error(f"Não foi possível ler o histórico de processamentos: {exc}")
colunas_status[2].metric("Último processamento", ultimo_processamento)
try:
    total_resultados = _contar_resultados()
except OSError as exc:
    total_resultados = "Erro ao ler"
    st.error(f"Não foi possível contar as pastas de resultados: {exc}")
colunas_status[3].metric("Total de resultados", total_resultados)

st.header("📋 Sobre o projeto")
st.write(
    "O fluxo do sistema é configurar os parâmetros, baixar observações RINEX da RBMC, "
    "enviá-las ao IBGE-PPP, baixar os resultados, compará-los com o BDG e visualizar "
    "as tabelas e os gráficos gerados."
)
# Botão adicional para recarregar a configuração do arquivo YAML
with st.sidebar:
    if st.button("🔄 Recarregar config", use_container_width=True):
        try:
            cfg = _ler_configuracao()
            _aplicar_configuracao(cfg)
            st.success("Configuração recarregada com sucesso.")
            st.experimental_rerun()
        except Exception as exc:
            st.error(f"Falha ao recarregar configuração: {exc}")


# Inicializa chaves de estado usadas entre abas
if "rinex_baixados" not in st.session_state:
    st.session_state["rinex_baixados"] = []
if "ultimo_download" not in st.session_state:
    st.session_state["ultimo_download"] = []
if "ultimo_envio" not in st.session_state or not isinstance(
    st.session_state["ultimo_envio"], list
):
    st.session_state["ultimo_envio"] = []
if "ultimos_resultados" not in st.session_state:
    st.session_state["ultimos_resultados"] = []
if "ultima_comparacao" not in st.session_state:
    st.session_state["ultima_comparacao"] = []
if "historico" not in st.session_state:
    st.session_state["historico"] = []
if "comparacoes" not in st.session_state:
    st.session_state["comparacoes"] = []
if "resultados_baixados" not in st.session_state:
    st.session_state["resultados_baixados"] = []


# Cria as abas principais da interface.
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📥 Baixar RINEX",
        "🚀 Enviar ao PPP",
        "📊 Baixar resultados",
        "🧮 Comparar com BDG",
        "📈 Ver resultados",
    ]
)


with tab1:
    st.subheader("📥 Baixar RINEX")
    st.markdown(
        f"**Itens desta sessão: {len(st.session_state['ultimo_download'])}**"
    )
    col_info, col_recarregar = st.columns([3, 1])
    with col_info:
        st.caption("Próximo passo: envie os arquivos RINEX ao IBGE-PPP.")
    with col_recarregar:
        if st.button("🔄 Recarregar tudo", key="recarregar_aba1"):
            try:
                config_inicial = _ler_configuracao()
                entradas_config = config_inicial.get("datas", [])
                primeiro_id = st.session_state.get("proximo_id_data", 0)
                st.session_state["lista_datas"] = [
                    {
                        "id": primeiro_id + indice,
                        "data": (
                            item.get("data", "")
                            if isinstance(item, dict)
                            else item if isinstance(item, str) else ""
                        ),
                        "horas": (
                            ",".join(str(hora) for hora in item.get("horas", []))
                            if isinstance(item, dict)
                            and isinstance(item.get("horas", []), list)
                            else str(item.get("horas", "todas"))
                            if isinstance(item, dict)
                            else "todas"
                        ),
                    }
                    for indice, item in enumerate(entradas_config)
                ]
                st.session_state["proximo_id_data"] = (
                    primeiro_id + len(st.session_state["lista_datas"])
                )
                st.session_state["rinex_estacao"] = config_inicial.get(
                    "estacao", CONFIGURACAO_PADRAO["estacao"]
                )
                st.session_state["lista_datas_recarregada"] = True
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()
            except (OSError, ValueError, yaml.YAMLError) as exc:
                st.error(f"Não foi possível recarregar o config.yaml: {exc}")

    if st.session_state.pop("lista_datas_recarregada", False):
        st.success("Lista editável restaurada do config.yaml.")

    st.write(
        "Baixe arquivos RINEX do servidor local da estação IFSC. "
        "Os campos abaixo vêm do config.yaml, mas podem ser alterados livremente."
    )

    try:
        config_inicial = _ler_configuracao()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        config_inicial = {}
        st.error(f"Não foi possível ler config.yaml: {exc}")

    if "lista_datas" not in st.session_state:
        entradas_config = config_inicial.get("datas", [])
        st.session_state["lista_datas"] = [
            {
                "id": indice,
                "data": (
                    item.get("data", "")
                    if isinstance(item, dict)
                    else item if isinstance(item, str) else ""
                ),
                "horas": (
                    ",".join(str(hora) for hora in item.get("horas", []))
                    if isinstance(item, dict) and isinstance(item.get("horas", []), list)
                    else str(item.get("horas", "todas"))
                    if isinstance(item, dict)
                    else "todas"
                ),
            }
            for indice, item in enumerate(entradas_config)
        ]
        st.session_state["proximo_id_data"] = len(st.session_state["lista_datas"])

    if st.session_state.pop("lista_datas_restaurada", False):
        st.success("Lista restaurada a partir do config.yaml.")

    estacao = st.text_input(
        "Estação",
        value=str(config_inicial.get("estacao", CONFIGURACAO_PADRAO["estacao"])),
        key="rinex_estacao",
    )

    with st.container():
        st.write("Datas e horas UTC:")
        indices_remover = []
        for item in st.session_state["lista_datas"]:
            item_id = item["id"]
            col_data, col_horas, col_remover = st.columns([3, 3, 1])
            item["data"] = col_data.text_input(
                "Data",
                value=item["data"],
                key=f"rinex_data_{item_id}",
            )
            item["horas"] = col_horas.text_input(
                "Horas",
                value=item["horas"],
                key=f"rinex_horas_{item_id}",
            )
            if col_remover.button("❌", key=f"remover_data_{item_id}"):
                indices_remover.append(item_id)

        if indices_remover:
            st.session_state["lista_datas"] = [
                item
                for item in st.session_state["lista_datas"]
                if item["id"] not in indices_remover
            ]
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()

        col_adicionar, col_restaurar = st.columns(2)
        if col_adicionar.button("➕ Adicionar data", key="adicionar_data"):
            novo_id = st.session_state["proximo_id_data"]
            st.session_state["proximo_id_data"] = novo_id + 1
            st.session_state["lista_datas"].append(
                {"id": novo_id, "data": "", "horas": ""}
            )
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()

        if col_restaurar.button(
            "🔄 Restaurar padrões do config",
            key="restaurar_padroes_config",
        ):
            try:
                config_restaurada = _ler_configuracao()
                entradas_config = config_restaurada.get("datas", [])
                primeiro_id = st.session_state["proximo_id_data"]
                st.session_state["lista_datas"] = [
                    {
                        "id": primeiro_id + indice,
                        "data": (
                            item.get("data", "")
                            if isinstance(item, dict)
                            else item if isinstance(item, str) else ""
                        ),
                        "horas": (
                            ",".join(str(hora) for hora in item.get("horas", []))
                            if isinstance(item, dict)
                            and isinstance(item.get("horas", []), list)
                            else str(item.get("horas", "todas"))
                            if isinstance(item, dict)
                            else "todas"
                        ),
                    }
                    for indice, item in enumerate(entradas_config)
                ]
                st.session_state["proximo_id_data"] = (
                    primeiro_id + len(st.session_state["lista_datas"])
                )
                st.session_state["lista_datas_restaurada"] = True
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()
            except (OSError, ValueError, yaml.YAMLError) as exc:
                st.error(f"Não foi possível restaurar os padrões do config.yaml: {exc}")

    col_principal, col_config = st.columns(2)
    with col_principal:
        baixar_lista = st.button(
            "📥 Baixar RINEX das datas listadas",
            type="primary",
        )
    with col_config:
        baixar_todas_config = st.button("📥 Baixar todas as datas do config")

    if baixar_lista:
        resultados: list[Path] = []
        erros = []
        with st.spinner("Baixando arquivos do servidor IFSC..."):
            for item in st.session_state["lista_datas"]:
                if not item["data"].strip():
                    erros.append("Uma linha da lista está sem data e foi ignorada.")
                    continue
                try:
                    arquivos_data = rbmc_downloader.baixar(
                        estacao,
                        item["data"].strip(),
                        item["horas"].strip(),
                        Path("data/rinex_input/bruto/"),
                    )
                    resultados.extend(arquivos_data)
                    activity_logger.registrar(
                        "DOWNLOAD",
                        f"{estacao} {item['data'].strip()} {item['horas'].strip()}",
                        f"{len(arquivos_data)} arquivos",
                    )
                except Exception as exc:
                    erros.append(f"{item['data']}: {exc}")
                    LOGGER.exception("Erro ao baixar RINEX para %s", item["data"])
                    activity_logger.registrar(
                        "DOWNLOAD",
                        f"{estacao} {item['data'].strip()} {item['horas'].strip()}",
                        f"ERRO: {str(exc)}",
                    )

        resultados = sorted(set(resultados))
        st.session_state["rinex_baixados"] = resultados
        st.session_state["ultimo_download"] = resultados if resultados and not erros else []
        st.session_state["ultimo_envio"] = []
        st.session_state["ultimos_resultados"] = []
        st.session_state["ultima_comparacao"] = []
        st.success(
            f"Concluído: {len(resultados)} arquivo(s) .20O baixado(s)."
        )
        for erro in erros:
            st.error(f"Falha no download: {erro}")
        if resultados:
            df_resultados = pd.DataFrame(
                [
                    {
                        "arquivo": str(caminho),
                        "tamanho_mb": round(
                            caminho.stat().st_size / (1024 * 1024), 2
                        ),
                    }
                    for caminho in resultados
                ]
            )
            st.dataframe(df_resultados)
        else:
            st.info("Nenhum arquivo baixado.")

    if baixar_todas_config:
        resultados: list[Path] = []
        erros = []
        datas_config = config_inicial.get("datas", [])
        with st.spinner("Baixando todas as datas do config.yaml..."):
            for item in datas_config:
                if isinstance(item, dict):
                    data_item = item.get("data")
                    horas_item = item.get("horas", "todas")
                elif isinstance(item, str):
                    data_item = item
                    horas_item = "todas"
                else:
                    erros.append(f"Entrada de data inválida no config: {item!r}")
                    continue

                if not isinstance(data_item, str) or not data_item.strip():
                    erros.append(f"Entrada de data inválida no config: {item!r}")
                    continue
                try:
                    estacao_config = str(
                        config_inicial.get("estacao", CONFIGURACAO_PADRAO["estacao"])
                    )
                    arquivos_data = rbmc_downloader.baixar(
                        estacao_config,
                        data_item.strip(),
                        horas_item,
                        Path("data/rinex_input/bruto/"),
                    )
                    resultados.extend(arquivos_data)
                    activity_logger.registrar(
                        "DOWNLOAD",
                        f"{estacao_config} {data_item.strip()} {horas_item}",
                        f"{len(arquivos_data)} arquivos",
                    )
                except Exception as exc:
                    erros.append(f"{data_item}: {exc}")
                    LOGGER.exception("Erro ao baixar RINEX para %s", data_item)
                    activity_logger.registrar(
                        "DOWNLOAD",
                        f"{estacao_config} {data_item.strip()} {horas_item}",
                        f"ERRO: {str(exc)}",
                    )

        resultados = sorted(set(resultados))
        st.session_state["rinex_baixados"] = resultados
        st.session_state["ultimo_download"] = resultados if resultados and not erros else []
        st.session_state["ultimo_envio"] = []
        st.session_state["ultimos_resultados"] = []
        st.session_state["ultima_comparacao"] = []
        st.success(
            f"Concluído: {len(resultados)} arquivo(s) .20O baixado(s) no total."
        )
        for erro in erros:
            st.error(f"Falha no download: {erro}")
        if resultados:
            df_resultados = pd.DataFrame(
                [
                    {
                        "arquivo": str(caminho),
                        "tamanho_mb": round(
                            caminho.stat().st_size / (1024 * 1024), 2
                        ),
                    }
                    for caminho in resultados
                ]
            )
            st.dataframe(df_resultados)
        else:
            st.info("Nenhum arquivo baixado.")

    if st.button("🗑️ Limpar lista", key="limpar_aba1"):
        st.session_state["lista_datas"] = []
        st.session_state["ultimo_download"] = []
        st.session_state["rinex_baixados"] = []
        st.session_state["ultimo_envio"] = []
        st.session_state["ultimos_resultados"] = []
        st.session_state["ultima_comparacao"] = []
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


with tab2:
    st.subheader("🚀 Enviar ao IBGE-PPP")
    st.markdown(
        f"**Itens desta sessão: {len(st.session_state['ultimo_envio'])}**"
    )
    col_info, col_recarregar = st.columns([3, 1])
    with col_info:
        st.caption("Próximo passo: baixe os resultados do processamento PPP.")
    with col_recarregar:
        if st.button("🔄 Recarregar tudo", key="recarregar_aba2"):
            arquivos_completos = listar_rinex_observacao(
                Path("data/rinex_input/bruto")
            )
            st.session_state["ultimo_download"] = arquivos_completos
            st.session_state["ultimo_envio"] = []
            st.session_state["ultimos_resultados"] = []
            st.session_state["ultima_comparacao"] = []
            st.session_state["todos_rinex_recarregados"] = len(arquivos_completos)
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()

    if "todos_rinex_recarregados" in st.session_state:
        total_recarregado = st.session_state.pop("todos_rinex_recarregados")
        st.success(f"{total_recarregado} arquivos carregados de todas as sessões.")

    st.write("Envie os arquivos RINEX baixados (ou existentes) ao serviço IBGE-PPP.")

    arquivos_encontrados = [
        Path(caminho)
        for caminho in st.session_state.get("ultimo_download", [])
    ]
    if not arquivos_encontrados:
        st.warning("Baixe os RINEX na Aba 1 primeiro.")
        st.stop()

    anos_por_arquivo = {}
    for caminho in arquivos_encontrados:
        correspondencia = re.match(r"(\d{2})", caminho.name)
        if correspondencia is None:
            correspondencia = re.search(r"\.(\d{2})[oO]$", caminho.name)
        ano = 2000 + int(correspondencia.group(1)) if correspondencia else None
        anos_por_arquivo[caminho] = ano

    filtro_nome = st.text_input("Filtrar por nome (opcional)", key="filtro_rinex_nome")
    anos_disponiveis = sorted(
        {ano for ano in anos_por_arquivo.values() if ano is not None}
    )
    anos_selecionados = st.multiselect(
        "Filtrar por ano",
        options=anos_disponiveis,
        key="filtro_rinex_ano",
    )

    arquivos = [
        caminho
        for caminho in arquivos_encontrados
        if filtro_nome.casefold() in caminho.name.casefold()
        and (not anos_selecionados or anos_por_arquivo[caminho] in anos_selecionados)
    ]
    if not arquivos:
        if arquivos_encontrados:
            st.info("Nenhum arquivo corresponde aos filtros selecionados.")
        else:
            st.warning(
                "Nenhum arquivo RINEX de observação encontrado em "
                "data/rinex_input/bruto/. Baixe os RINEX primeiro na aba anterior "
                "ou coloque arquivos nessa pasta."
            )

    # Exibe os arquivos encontrados e filtrados.
    lista_files = [
        {
            "nome": caminho.name,
            "ano": anos_por_arquivo[caminho],
            "tamanho_mb": round(caminho.stat().st_size / (1024 * 1024), 2),
            "modificado": datetime.fromtimestamp(caminho.stat().st_mtime).isoformat(
                sep=" "
            ),
        }
        for caminho in arquivos
    ]
    st.dataframe(lista_files)

    email_envio = st.text_input("E-mail para envio (confirme)", value=st.session_state.get("config_email", CONFIGURACAO_PADRAO["email"]))
    enviar_todos = st.button(
        "🚀 Enviar todos ao IBGE-PPP",
        type="primary",
        disabled=not arquivos,
    )
    if enviar_todos:
        if ibge_client is None:
            st.error("O módulo ibge_client não pôde ser importado.")
        else:
            log_box = st.empty()
            prog = st.progress(0)
            resultados = []
            total = len(arquivos)
            sucessos = 0
            erros = 0
            for idx, caminho in enumerate(arquivos):
                hora_envio = datetime.now().isoformat(timespec="seconds")
                try:
                    log_box.write(f"Enviando {caminho.name}...")
                    resposta = ibge_client.enviar_arquivo(
                        caminho,
                        email_envio,
                        st.session_state.get("config_tipo_levantamento", "estatico"),
                        st.session_state.get("config_modelo_antena", CONFIGURACAO_PADRAO["modelo_antena"]),
                        float(st.session_state.get("config_altura_antena", CONFIGURACAO_PADRAO["altura_antena"])),
                    )
                    # Salva a resposta bruta
                    caminho_resposta = ibge_client.salvar_resposta_bruta(resposta, caminho.stem)
                    resultado = {
                        "nome_arquivo": caminho.name,
                        "status": resposta.get("status", "OK"),
                        "link": resposta.get("link"),
                        "hora_envio": hora_envio,
                    }
                    resultados.append(resultado)
                    sucessos += 1
                    log_box.write(f"Enviado: {caminho.name} -> {resultado['status']}")
                    activity_logger.registrar(
                        "ENVIO_PPP",
                        caminho.name,
                        str(resultado["status"]),
                    )
                except Exception as exc:
                    LOGGER.exception("Erro ao enviar %s: %s", caminho, exc)
                    erros += 1
                    resultados.append({"nome_arquivo": caminho.name, "status": "erro", "link": None, "hora_envio": hora_envio, "erro": str(exc)})
                    log_box.error(f"Falha ao enviar {caminho.name}: {exc}")
                    activity_logger.registrar(
                        "ENVIO_PPP",
                        caminho.name,
                        f"ERRO: {exc}",
                    )

                if total:
                    prog.progress(int(((idx + 1) / total) * 100))
                time.sleep(2)

            # Salva histórico de envios
            try:
                st.session_state["historico"] = resultados
                st.session_state["ultimo_envio"] = [
                    {
                        "nome_arquivo": resultado["nome_arquivo"],
                        "status": resultado["status"],
                        "link": resultado.get("link"),
                    }
                    for resultado in resultados
                    if resultado.get("status") == "OK" and resultado.get("link")
                ]
                st.session_state["ultimos_resultados"] = []
                st.session_state["ultima_comparacao"] = []
                if main_orchestrator is not None:
                    caminho_historico = PROJECT_ROOT / "data" / "results_output" / "historico_processamentos.json"
                    main_orchestrator.salvar_historico(resultados, caminho_historico)
            except Exception as exc:
                LOGGER.exception("Erro ao salvar histórico: %s", exc)
                st.error(f"Falha ao salvar histórico: {exc}")

            st.success(f"Envio concluído: {sucessos} sucessos, {erros} erros.")
            if resultados:
                st.dataframe(resultados)

    if st.button("🗑️ Limpar lista", key="limpar_aba2"):
        st.session_state["ultimo_download"] = []
        st.session_state["ultimo_envio"] = []
        st.session_state["ultimos_resultados"] = []
        st.session_state["ultima_comparacao"] = []
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


with tab3:
    st.subheader("📊 Baixar resultados")
    st.markdown(
        f"**Itens desta sessão: {len(st.session_state['ultimos_resultados'])}**"
    )
    col_info, col_recarregar = st.columns([3, 1])
    with col_info:
        st.caption("Próximo passo: compare os relatórios baixados com o BDG.")
    with col_recarregar:
        if st.button("🔄 Recarregar tudo", key="recarregar_aba3"):
            try:
                with st.spinner("Baixando todos os resultados disponíveis..."):
                    envios_disponiveis = _listar_envios_com_resultado()
                    lote_completo = _baixar_resultados_da_sessao(envios_disponiveis)
                arquivos_relatorio = sorted(
                    {
                        Path(arquivo)
                        for resultado in lote_completo
                        if resultado.get("status") == "OK"
                        for arquivo in resultado.get("arquivos_extraidos", [])
                        if Path(arquivo).suffix.lower() == ".txt"
                    }
                )
                st.session_state["ultimos_resultados"] = arquivos_relatorio
                st.session_state["resultados_baixados"] = lote_completo
                st.session_state["ultima_comparacao"] = []
                st.session_state["resultados_recarregados"] = True
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()
            except Exception as exc:
                LOGGER.exception("Falha ao recarregar todos os resultados disponíveis.")
                st.error(f"Não foi possível recarregar todos os resultados: {exc}")

    if st.session_state.pop("resultados_recarregados", False):
        st.success(
            f"{len(st.session_state['ultimos_resultados'])} resultados carregados "
            "de todas as sessões."
        )

    if not st.session_state["ultimo_envio"]:
        st.warning("Envie os arquivos ao PPP primeiro (Aba 2).")
        st.stop()

    st.write("Baixe os ZIPs de resultado do IBGE-PPP e extraia os arquivos.")

    if st.button("📥 Baixar e extrair resultados desta sessão", type="primary"):
        log_box = st.empty()
        progress = st.progress(0)
        try:
            resultados_lote = _baixar_resultados_da_sessao(
                st.session_state["ultimo_envio"]
            )
            st.session_state["resultados_baixados"] = resultados_lote
            total = len(resultados_lote)
            for indice, resultado in enumerate(resultados_lote, start=1):
                nome = resultado.get("nome_arquivo", f"Resultado {indice}")
                if resultado.get("status") == "OK":
                    log_box.write(
                        f"Extraído: {nome} "
                        f"({len(resultado.get('arquivos_extraidos', []))} arquivo(s))"
                    )
                else:
                    LOGGER.error(
                        "Falha no lote de resultados para %s: %s",
                        nome,
                        resultado.get("erro", "erro não especificado"),
                    )
                    log_box.error(
                        f"Falha ao processar {nome}: "
                        f"{resultado.get('erro', 'erro não especificado')}"
                    )
                progress.progress(int(indice / total * 100) if total else 100)

            zip_baixados = sum(
                1 for resultado in resultados_lote if resultado.get("caminho_zip")
            )
            zip_extraidos = sum(
                1 for resultado in resultados_lote if resultado.get("status") == "OK"
            )
            st.success(
                f"Processamento concluído: {zip_baixados} ZIP(s) baixado(s) "
                f"e {zip_extraidos} extraído(s)."
            )
            arquivos_txt = sorted(
                {
                    Path(arquivo)
                    for resultado in resultados_lote
                    if resultado.get("status") == "OK"
                    for arquivo in resultado.get("arquivos_extraidos", [])
                    if Path(arquivo).suffix.lower() == ".txt"
                }
            )
            st.session_state["ultimos_resultados"] = arquivos_txt
            st.session_state["ultima_comparacao"] = []
            st.dataframe(
                [
                    {
                        "nome_arquivo": resultado.get("nome_arquivo"),
                        "pasta_criada": resultado.get("caminho_pasta_extraida"),
                        "status": resultado.get("status"),
                    }
                    for resultado in resultados_lote
                ],
                use_container_width=True,
            )
            if arquivos_txt:
                st.dataframe(
                    [{"nome": caminho.name, "caminho": str(caminho)} for caminho in arquivos_txt]
                )
            else:
                st.info("Nenhum relatório .txt foi extraído nesta sessão.")
        except Exception as exc:
            LOGGER.exception("Erro ao baixar e extrair resultados PPP.")
            st.session_state["ultimos_resultados"] = []
            st.session_state["ultima_comparacao"] = []
            st.error(f"Não foi possível baixar e extrair os resultados: {exc}")

    if st.button("🗑️ Limpar lista", key="limpar_aba3"):
        st.session_state["ultimo_envio"] = []
        st.session_state["ultimos_resultados"] = []
        st.session_state["resultados_baixados"] = []
        st.session_state["ultima_comparacao"] = []
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

with tab4:
    st.subheader("🧮 Comparar com BDG")
    st.markdown(
        f"**Itens desta sessão: {len(st.session_state['ultima_comparacao'])}**"
    )
    col_info, col_recarregar = st.columns([3, 1])
    with col_info:
        st.caption("Próximo passo: visualize a comparação na Aba 5.")
    with col_recarregar:
        recarregar_comparacao = st.button(
            "🔄 Recarregar tudo",
            key="recarregar_aba4",
        )

    if recarregar_comparacao:
        resultados_validos = [
            Path(caminho)
            for caminho in st.session_state.get("ultimos_resultados", [])
            if Path(caminho).is_file() and Path(caminho).suffix.lower() == ".txt"
        ]
        st.session_state["ultimos_resultados"] = resultados_validos
        st.session_state["resultados_sessao_recarregados"] = len(resultados_validos)
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

    if "resultados_sessao_recarregados" in st.session_state:
        total_recarregado = st.session_state.pop("resultados_sessao_recarregados")
        if total_recarregado:
            st.success(f"{total_recarregado} resultados válidos recarregados da sessão.")
        else:
            st.warning(
                "Nenhum resultado na última sessão. Vá para a Aba 3 e baixe os resultados primeiro."
            )

    if st.button("🗑️ Limpar lista", key="limpar_aba4"):
        st.session_state["ultimos_resultados"] = []
        st.session_state["ultima_comparacao"] = []
        st.session_state["comparacoes"] = []
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

    resultados_sessao = st.session_state.get("ultimos_resultados", [])
    if not resultados_sessao:
        st.warning(
            "Nenhum resultado na última sessão. Vá para a Aba 3 e baixe os resultados primeiro."
        )
        st.stop()

    caminho_bdg = DIRETORIO_RESULTADOS / "94052_bdg_resposta_bruta.json"
    if not caminho_bdg.is_file():
        st.warning(
            "A coordenada oficial do BDG não foi encontrada em "
            "data/results_output/94052_bdg_resposta_bruta.json."
        )
        st.stop()

    comparar_sessao = st.button(
        "🧮 Comparar resultados desta sessão",
        type="primary",
    )
    if comparar_sessao:
        log_box = st.empty()
        try:
            resultados = [Path(caminho) for caminho in resultados_sessao]
            log_box.write(f"Comparando {len(resultados)} relatório(s) com o BDG...")
            comparacoes, ignorados = _comparar_relatorios(resultados)
            st.session_state["ultima_comparacao"] = comparacoes
            st.session_state["comparacoes"] = comparacoes
            if comparacoes:
                activity_logger.registrar(
                    "COMPARACAO",
                    "resultados desta sessão",
                    f"{len(comparacoes)} processamentos",
                )
                log_box.write("Tabela e gráficos foram gerados.")
            st.success(
                f"{len(comparacoes)} comparados com sucesso, {ignorados} ignorados."
            )
            if comparacoes:
                st.dataframe(comparacoes, use_container_width=True)
            else:
                st.info("Nenhum arquivo da sessão pôde ser comparado.")
        except Exception as exc:
            LOGGER.exception("Erro ao comparar resultados PPP com o BDG.")
            st.session_state["ultima_comparacao"] = []
            st.error(f"Não foi possível comparar os resultados com o BDG: {exc}")
    elif st.session_state["ultima_comparacao"]:
        st.dataframe(st.session_state["ultima_comparacao"], use_container_width=True)

with tab5:
    st.subheader("📈 Ver resultados")
    st.markdown(
        f"**Itens desta sessão: {len(st.session_state['ultima_comparacao'])}**"
    )
    col_info, col_recarregar = st.columns([3, 1])
    with col_info:
        st.caption("Próximo passo: revise ou exporte a comparação desta sessão.")
    with col_recarregar:
        if st.button("🔄 Recarregar tudo", key="recarregar_aba5"):
            caminho_csv_recarregar = DIRETORIO_RESULTADOS / "comparacao_geral.csv"
            try:
                tabela_completa = pd.read_csv(
                    caminho_csv_recarregar,
                    sep=";",
                    decimal=",",
                )
                st.session_state["ultima_comparacao"] = tabela_completa.to_dict(
                    orient="records"
                )
                st.session_state["comparacoes"] = st.session_state[
                    "ultima_comparacao"
                ]
                st.session_state["resultados_recarregados_aba5"] = True
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()
            except (OSError, pd.errors.ParserError, ValueError) as exc:
                st.error(f"Não foi possível recarregar o CSV completo: {exc}")

    if st.session_state.pop("resultados_recarregados_aba5", False):
        st.success(
            f"{len(st.session_state['ultima_comparacao'])} comparações carregadas do CSV."
        )

    if not st.session_state["ultima_comparacao"]:
        st.warning("Execute a comparação primeiro (Aba 4).")
        st.stop()

    caminho_csv = DIRETORIO_RESULTADOS / "comparacao_geral.csv"
    graficos = [
        DIRETORIO_RESULTADOS / "graficos" / "diferencas_por_processamento.png",
        DIRETORIO_RESULTADOS / "graficos" / "diferencas_por_mes.png",
        DIRETORIO_RESULTADOS / "graficos" / "estatisticas_gerais.png",
    ]

    try:
        tabela = pd.DataFrame(st.session_state["ultima_comparacao"])
        st.dataframe(tabela, use_container_width=True)

        for grafico in graficos:
            if grafico.is_file():
                st.image(str(grafico), caption=grafico.stem.replace("_", " ").title())
            else:
                st.info(
                    f"Gráfico não encontrado: {grafico.name}. "
                    "Execute a comparação na aba anterior primeiro."
                )

        st.subheader("📤 Exportar")
        col_csv, col_excel, col_historico = st.columns(3)
        if caminho_csv.is_file():
            dados_csv = caminho_csv.read_bytes()
        else:
            dados_csv = tabela.to_csv(
                sep=";",
                decimal=",",
                index=False,
            ).encode("utf-8-sig")
        col_csv.download_button(
            "📄 Baixar CSV",
            data=dados_csv,
            file_name=caminho_csv.name,
            mime="text/csv",
            use_container_width=True,
        )
        buffer_excel = BytesIO()
        tabela.to_excel(buffer_excel, index=False, engine="openpyxl")
        col_excel.download_button(
            "📊 Baixar Excel",
            data=buffer_excel.getvalue(),
            file_name="comparacao_geral.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        if CAMINHO_HISTORICO.is_file():
            col_historico.download_button(
                "🗂️ Baixar histórico JSON",
                data=CAMINHO_HISTORICO.read_bytes(),
                file_name=CAMINHO_HISTORICO.name,
                mime="application/json",
                use_container_width=True,
            )
        else:
            col_historico.info("Histórico JSON não encontrado.")
    except Exception as exc:
        LOGGER.exception("Erro ao carregar ou exportar os resultados.")
        st.error(f"Não foi possível carregar ou exportar os resultados: {exc}")

    st.subheader("📜 Log de atividades")
    caminho_log_atividades = (
        Path("logs") / f"atividade_{datetime.now():%Y%m%d}.log"
    )
    if caminho_log_atividades.is_file():
        try:
            linhas_log = caminho_log_atividades.read_text(encoding="utf-8").splitlines()
            st.code("\n".join(linhas_log[-100:]))
        except OSError as exc:
            st.error(f"Não foi possível ler o log de atividades: {exc}")
    else:
        st.info("Nenhuma atividade registrada hoje.")

    if st.button("🗑️ Limpar lista", key="limpar_aba5"):
        st.session_state["ultima_comparacao"] = []
        st.session_state["comparacoes"] = []
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()
