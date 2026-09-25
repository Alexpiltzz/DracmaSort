import os
from pathlib import Path

from code_gen.io import (
    KEY_REPORTS_DIR,
    default_config_path,
    excluded_codes,
    latest_unified_report_path,
    read_unified_pairs,
    read_unified_pool,
)


def _csv(diretorio: Path, nome: str, conteudo: str, mtime: float | None = None) -> Path:
    arquivo = diretorio / nome
    arquivo.write_text(conteudo, encoding="utf-8-sig")
    if mtime is not None:
        os.utime(arquivo, (mtime, mtime))
    return arquivo


def test_latest_unified_report_path_seleciona_mais_recente(tmp_path):
    _csv(tmp_path, "relatorio_envio_unificado_20260101_000000.csv", "Aluno;Status\n", mtime=1000)
    _csv(
        tmp_path,
        "relatorio_envio_unificado_20261231_235959.csv",
        "Aluno;Status\n",
        mtime=2000,
    )
    mais_recente = latest_unified_report_path(tmp_path)
    assert mais_recente is not None
    assert mais_recente.name == "relatorio_envio_unificado_20261231_235959.csv"


def test_latest_unified_report_path_ignora_nao_unificados(tmp_path):
    _csv(tmp_path, "relatorio_envio_20260101_000000.csv", "Aluno;Status\n")
    assert latest_unified_report_path(tmp_path) is None


def test_latest_unified_report_path_sem_arquivos(tmp_path):
    assert latest_unified_report_path(tmp_path) is None


def test_latest_unified_report_path_padrao_usa_cache(tmp_path, monkeypatch):
    from code_gen import io as io_mod

    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    _csv(tmp_path, "relatorio_envio_unificado_20260101_000000.csv", "Aluno;Status\n")
    assert (
        latest_unified_report_path() == tmp_path / "relatorio_envio_unificado_20260101_000000.csv"
    )


def test_latest_unified_report_path_padrao_usa_configurada(tmp_path, monkeypatch):
    import json

    from code_gen import io as io_mod

    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    configurada = tmp_path / "relatorios"
    configurada.mkdir()
    default_config_path().write_text(
        json.dumps({KEY_REPORTS_DIR: str(configurada)}),
        encoding="utf-8",
    )
    _csv(configurada, "relatorio_envio_unificado_20260101_000000.csv", "Aluno;Status\n")
    _csv(tmp_path, "relatorio_envio_unificado_20261231_235959.csv", "Aluno;Status\n", mtime=2000)

    mais_recente = latest_unified_report_path()
    assert mais_recente is not None
    assert mais_recente == configurada / "relatorio_envio_unificado_20260101_000000.csv"


def test_latest_unified_report_path_encontra_na_pasta_base(tmp_path):
    _csv(tmp_path, "relatorio_envio_unificado_20260101_000000.csv", "Aluno;Status\n")
    verificado = latest_unified_report_path(tmp_path)
    assert verificado is not None
    assert verificado.name == "relatorio_envio_unificado_20260101_000000.csv"


def test_latest_unified_report_path_prefere_mais_recente_entre_pastas(tmp_path):
    _csv(tmp_path, "relatorio_envio_unificado_20260101_000000.csv", "Aluno;Status\n", mtime=1000)
    cache = tmp_path / "cache"
    cache.mkdir()
    _csv(cache, "relatorio_envio_unificado_20261231_235959.csv", "Aluno;Status\n", mtime=2000)
    verificado = latest_unified_report_path(tmp_path)
    assert verificado is not None
    assert verificado == cache / "relatorio_envio_unificado_20261231_235959.csv"


HEADER = "Aluno;Nome;E-mail;C\u00f3digos;Status;Data_Hora;Detalhes\n"


def test_read_unified_pool_filtra_status_sucesso(tmp_path):
    arquivo = _csv(
        tmp_path,
        "relatorio_envio_unificado_20260924_110218.csv",
        HEADER
        + "Maria Silva;Resp;m@x.com;1, 2, 3;Sucesso;24/09/2026 10:00;ok\n"
        + "Joao Costa;Resp;j@x.com;10, 11;Falha;24/09/2026 10:01;erro\n"
        + "Ana Souza;Resp;a@x.com;4;Sucesso;24/09/2026 10:02;ok\n",
    )
    nomes, codigos = read_unified_pool(arquivo)
    assert nomes == {"Maria Silva", "Ana Souza"}
    assert codigos == {1, 2, 3, 4}


def test_read_unified_pool_ignora_codigos_invalidos(tmp_path):
    arquivo = _csv(
        tmp_path,
        "relatorio_envio_unificado_20260924_110218.csv",
        HEADER
        + "Maria Silva;Resp;m@x.com;abc, 5, ;Sucesso;24/09/2026 10:00;ok\n"
        + "Maria Silva;Resp;m@x.com;0, 10000;Sucesso;24/09/2026 10:00;ok\n",
    )
    _, codigos = read_unified_pool(arquivo)
    assert codigos == {5}


def test_read_unified_pool_lida_delimitador_ponto_virgula(tmp_path):
    arquivo = _csv(
        tmp_path,
        "relatorio_envio_unificado_20260924_110218.csv",
        "Aluno;Códigos;Status\n" + "Zed Aluno;42;Sucesso\n" + "Ami Aluna;7;Sucesso\n",
    )
    nomes, codigos = read_unified_pool(arquivo)
    assert nomes == {"Zed Aluno", "Ami Aluna"}
    assert codigos == {42, 7}


def test_read_unified_pairs_mapeia_codigo_para_aluno(tmp_path):
    arquivo = _csv(
        tmp_path,
        "relatorio_envio_unificado_20260924_110218.csv",
        HEADER
        + "Maria Silva;Resp;m@x.com;1, 2, 3;Sucesso;24/09/2026 10:00;ok\n"
        + "Joao Costa;Resp;j@x.com;10;Falha;24/09/2026 10:01;erro\n"
        + "Ana Souza;Resp;a@x.com;4;Sucesso;24/09/2026 10:02;ok\n",
    )
    pares = read_unified_pairs(arquivo)
    assert pares == {1: "Maria Silva", 2: "Maria Silva", 3: "Maria Silva", 4: "Ana Souza"}


def test_read_unified_pairs_primeiro_vinculo_vence(tmp_path):
    arquivo = _csv(
        tmp_path,
        "relatorio_envio_unificado_20260924_110218.csv",
        HEADER
        + "Maria Silva;Resp;m@x.com;1;Sucesso;24/09/2026 10:00;ok\n"
        + "Ana Souza;Resp;a@x.com;1;Sucesso;24/09/2026 10:01;ok\n",
    )
    pares = read_unified_pairs(arquivo)
    assert pares == {1: "Maria Silva"}


def test_read_unified_pairs_propaga_varios_codigos_por_linha(tmp_path):
    arquivo = _csv(
        tmp_path,
        "relatorio_envio_unificado_20260924_110218.csv",
        HEADER + "Maria Silva;Resp;m@x.com;2, 5, 9;Sucesso;24/09/2026 10:00;ok\n",
    )
    pares = read_unified_pairs(arquivo)
    assert pares == {2: "Maria Silva", 5: "Maria Silva", 9: "Maria Silva"}


def test_read_unified_pairs_ignora_alunos_e_codigos_invalidos(tmp_path):
    arquivo = _csv(
        tmp_path,
        "relatorio_envio_unificado_20260924_110218.csv",
        HEADER
        + "Maria Silva;Resp;m@x.com;abc, 0, 10000;Sucesso;24/09/2026 10:00;ok\n"
        + ";Resp;m@x.com;7;Sucesso;24/09/2026 10:01;ok\n",
    )
    pares = read_unified_pairs(arquivo)
    assert pares == {}


def test_excluded_codes_aluno_sorteado_exclui_todos_os_codigos():
    pares = {1: "Maria Silva", 2: "Maria Silva", 3: "Maria Silva", 4: "João Costa"}
    excluidos = excluded_codes(pares, set(), {"Maria Silva"})
    assert excluidos == {1, 2, 3}


def test_excluded_codes_mantem_codigo_individual():
    pares = {1: "Maria Silva", 2: "Maria Silva", 3: "João Costa"}
    excluidos = excluded_codes(pares, {3}, {"Maria Silva"})
    assert excluidos == {1, 2, 3}


def test_excluded_codes_ignora_nome_sem_prefixo_do_aluno():
    pares = {1: "Maria Silva"}
    excluidos = excluded_codes(pares, set(), {"Outro Aluno"})
    assert excluidos == set()


def test_default_config_path_aponta_para_raiz(tmp_path, monkeypatch):
    from code_gen import io as io_mod

    raiz = tmp_path / "Giveaways_Tools"
    raiz.mkdir()
    monkeypatch.setattr(io_mod, "app_root", lambda: raiz)
    assert default_config_path() == raiz / "config.json"
