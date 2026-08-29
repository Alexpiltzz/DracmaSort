"""Helpers compartilhados de seleção de arquivo para os fluxos de terminal."""

from __future__ import annotations

from pathlib import Path


def pick_file_dialog() -> Path | None:
    """Abre o seletor nativo do Windows e devolve o arquivo escolhido."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Selecione a planilha com nomes e e-mails",
        filetypes=[("Planilhas", "*.xlsx *.csv"), ("Todos os arquivos", "*.*")],
    )
    root.destroy()
    return Path(path) if path else None


def resolve_input_path(flag: str | None) -> Path | None:
    """Resolve o caminho da planilha: flag, seletor visual ou prompt manual."""
    if flag:
        path = Path(flag)
        if not path.is_file():
            print(f"Arquivo não encontrado: {path}")
            return None
        return path
    picked = pick_file_dialog()
    if picked is not None:
        return picked
    fallback = input("Caminho da planilha (.xlsx ou .csv): ").strip()
    if fallback and Path(fallback).is_file():
        return Path(fallback)
    return None
