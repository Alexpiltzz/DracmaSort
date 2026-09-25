"""Controlador modular da aba de Sorteio (Cache de pool, Animações e Exportação de Ata)."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from code_gen.core import (
    CodeRegistry,
    StudentRegistry,
    format_code,
    smart_title_case,
)
from code_gen.docx_export import generate_draw_report_docx
from code_gen.io import (
    KEY_ALUNOS_SORTEADOS,
    KEY_CODIGOS_SORTEADOS,
    default_config_path,
    excluded_codes,
    latest_unified_report_path,
    normalize_name,
    read_unified_pairs,
    read_unified_pool,
)
from gui.drawn_codes import register_drawn_numbers, register_drawn_students


class SorteioTabHandler(QObject):
    """Gerencia a aba de Sorteio com caching de I/O em memória."""

    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, window) -> None:
        parent = window if isinstance(window, QObject) else None
        super().__init__(parent)
        self.window = window
        self._cache_path: Path | None = None
        self._cache_mtime: float | None = None
        self._cache_data: tuple[set[str], set[int], dict[int, str]] | None = None

    def invalidate_cache(self) -> None:
        """Invalida o cache em memória do relatório unificado."""
        self._cache_path = None
        self._cache_mtime = None
        self._cache_data = None

    def _read_cached_unified(self) -> tuple[set[str], set[int], dict[int, str]]:
        """Lê os dados do unificado utilizando cache de memória por mtime."""
        unificado = latest_unified_report_path()
        if unificado is None:
            raise OSError(
                "Nenhum relatório unificado (relatorio_envio_unificado_*.csv) "
                "encontrado em cache/ ou na pasta base."
            )
        try:
            mtime = unificado.stat().st_mtime
        except OSError:
            mtime = 0.0

        if (
            self._cache_data is not None
            and self._cache_path == unificado
            and self._cache_mtime == mtime
        ):
            return self._cache_data

        try:
            nomes, codigos = read_unified_pool(unificado)
            pares = read_unified_pairs(unificado)
        except (ValueError, OSError) as exc:
            raise OSError(
                f"Não foi possível ler o relatório unificado {unificado.name}: {exc}"
            ) from exc

        self._cache_path = unificado
        self._cache_mtime = mtime
        self._cache_data = (nomes, codigos, pares)
        return self._cache_data

    def source_pool(self) -> list[str]:
        """Devolve a lista de candidatos (nomes ou códigos) usando o cache."""
        nomes, codigos, pares = self._read_cached_unified()
        drawn_codes = self.drawn_codes()
        drawn_students = self.drawn_students()
        drawn_normalized = {normalize_name(name) for name in drawn_students}

        if self.window._sorteio_source_index == 0:
            return sorted(
                smart_title_case(name)
                for name in nomes
                if normalize_name(name) not in drawn_normalized
            )

        excluded = excluded_codes(pares, drawn_codes, drawn_students)
        if self.window._sorteio_source_index == 1:
            return [format_code(code) for code in sorted(codigos - excluded)]

        return [
            f"{format_code(code)}\n{smart_title_case(aluno)}"
            for code, aluno in sorted(pares.items())
            if code not in excluded and normalize_name(aluno) not in drawn_normalized
        ]

    def drawn_codes(self) -> set[int]:
        try:
            return CodeRegistry(default_config_path(), section=KEY_CODIGOS_SORTEADOS).load()
        except (ValueError, OSError) as exc:
            raise OSError(f"Não foi possível ler codigos_sorteados: {exc}") from exc

    def drawn_students(self) -> set[str]:
        try:
            return StudentRegistry(default_config_path(), section=KEY_ALUNOS_SORTEADOS).load()
        except (ValueError, OSError) as exc:
            raise OSError(f"Não foi possível ler alunos_sorteados: {exc}") from exc

    def register_drawn_codes(self, winners: list[str]) -> None:
        unificado = latest_unified_report_path()
        pares: dict[int, str] = {}
        if unificado is not None:
            try:
                pares = read_unified_pairs(unificado)
            except Exception as exc:  # noqa: BLE001
                self.log_message.emit(f"Não foi possível ler o relatório unificado: {exc}")

        numeros: list[int] = []
        alunos: list[str] = []
        for winner in winners:
            linha = winner.split("\n", 1)
            codigo = linha[0]
            try:
                numero = int(codigo)
            except ValueError:
                continue
            numeros.append(numero)
            nome = linha[1].strip() if len(linha) > 1 else pares.get(numero)
            if nome:
                alunos.append(nome)

        if numeros:
            try:
                register_drawn_numbers(
                    default_config_path(), numeros, section=KEY_CODIGOS_SORTEADOS
                )
            except Exception as exc:  # noqa: BLE001
                self.log_message.emit(f"Não foi possível registrar os códigos sorteados: {exc}")
        if alunos:
            try:
                register_drawn_students(default_config_path(), alunos, section=KEY_ALUNOS_SORTEADOS)
            except Exception as exc:  # noqa: BLE001
                self.log_message.emit(f"Não foi possível registrar os alunos sorteados: {exc}")

        self.invalidate_cache()

    def register_plain_students(self, winners: list[str]) -> None:
        nomes = [name for name in winners if name.strip()]
        if not nomes:
            return
        try:
            register_drawn_students(default_config_path(), nomes, section=KEY_ALUNOS_SORTEADOS)
        except Exception as exc:  # noqa: BLE001
            self.log_message.emit(f"Não foi possível registrar os alunos sorteados: {exc}")

        self.invalidate_cache()

    def export_docx_ata(self) -> None:
        students = self.drawn_students()
        codes = self.drawn_codes()
        if not students and not codes:
            QMessageBox.information(
                self.window,
                "Nenhum sorteado",
                "Não há alunos ou códigos registrados para exportar a ata.",
            )
            return

        unificado = latest_unified_report_path()
        pares: dict[int, str] = {}
        if unificado is not None:
            try:
                pares = read_unified_pairs(unificado)
            except Exception:  # noqa: BLE001
                pares = {}

        records: list[dict[str, str]] = []
        if students:
            for name in sorted(students):
                matched_codes = [
                    format_code(c)
                    for c, aluno in pares.items()
                    if normalize_name(aluno) == normalize_name(name)
                ]
                records.append(
                    {
                        "aluno": name,
                        "email": "-",
                        "codigo": ", ".join(matched_codes) if matched_codes else "-",
                    }
                )
        else:
            for code in sorted(codes):
                aluno = pares.get(code, "-")
                records.append(
                    {
                        "aluno": aluno,
                        "email": "-",
                        "codigo": format_code(code),
                    }
                )

        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"Ata_Sorteio_{timestamp}.docx"
        filename, _ = QFileDialog.getSaveFileName(
            self.window,
            "Salvar Ata Oficial do Sorteio (.docx)",
            default_name,
            "Documentos Word (*.docx)",
        )
        if not filename:
            return

        path = Path(filename)
        try:
            generate_draw_report_docx(path, records)
            QMessageBox.information(
                self.window,
                "Ata gerada com sucesso",
                (
                    f"A Ata Oficial do Sorteio foi salva em:\n{path}\n\n"
                    "Você pode abrir este arquivo no Word para preencher a coluna "
                    "'Prêmio Recebido'."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self.window,
                "Falha ao gerar Ata",
                f"Ocorreu um erro ao gerar o arquivo .docx:\n{exc}",
            )
