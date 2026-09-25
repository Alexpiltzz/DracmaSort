"""Testes unitários para os controladores de abas da GUI."""

from __future__ import annotations

from pathlib import Path

from gui.tabs.sorteio_tab import SorteioTabHandler


def test_sorteio_tab_handler_cache(tmp_path: Path, monkeypatch):
    from code_gen import io as io_mod

    # Criar relatório unificado fictício
    relatorio = tmp_path / "relatorio_envio_unificado_20260925_120000.csv"
    relatorio.write_text(
        "Aluno;Nome;E-mail;Códigos;Status;Data_Hora;Detalhes\n"
        "Maria Silva;Resp;m@x.com;0001, 0002;Sucesso;25/09/2026 12:00;ok\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)

    from PyQt6.QtCore import QObject

    class DummyWindow(QObject):
        _sorteio_source_index = 0

    window = DummyWindow()
    handler = SorteioTabHandler(window)

    # Primeira leitura deve popular o cache
    pool1 = handler.source_pool()
    assert pool1 == ["Maria Silva"]
    assert handler._cache_data is not None

    # Alterar window index para 1 (Códigos) sem modificar o arquivo deve reusar o cache
    window._sorteio_source_index = 1
    pool2 = handler.source_pool()
    assert pool2 == ["0001", "0002"]

    # Invalidar o cache força re-leitura
    handler.invalidate_cache()
    assert handler._cache_data is None
