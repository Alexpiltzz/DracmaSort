"""Serviço de envio em lote compartilhado entre terminal e interface gráfica.

Centraliza o loop de envio com intervalos anti-spam, pausas por lote,
interrupção cooperativa e geração de relatório. É usado pelo fluxo de
terminal (``code_gen.main``) e pelo worker da interface (``gui.ui``),
evitando a duplicação dessa lógica.
"""

from __future__ import annotations

import random
import time as time_module
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart

from .smtp import SmtpConfig

DELAY_PER_EMAIL_MIN = 7.0
DELAY_PER_EMAIL_MAX = 10.0
BATCH_SIZE = 50
BATCH_PAUSE_MIN = 300.0
BATCH_PAUSE_MAX = 600.0

MessageBuilder = Callable[[dict[str, str]], MIMEMultipart]
Deliver = Callable[[SmtpConfig, MIMEMultipart], dict]


@dataclass(frozen=True)
class SendResult:
    """Resultado consolidado de um lote de envio."""

    reports: list[dict[str, str]]
    interrupted: bool
    summary: str

    @property
    def failures(self) -> int:
        return sum(row["Status"] in {"Falha", "Rejeitado"} for row in self.reports)


def _cooperative_wait(
    seconds: float,
    sleep_fn: Callable[[float], None],
    should_stop: Callable[[], bool] | None,
) -> bool:
    """Aguarda permitindo que o chamador interrompa o lote durante a pausa."""
    remaining = seconds
    while remaining > 0:
        if should_stop is not None and should_stop():
            return False
        interval = min(0.25, remaining)
        sleep_fn(interval)
        remaining -= interval
    return True


def send_all(
    config: SmtpConfig,
    rows: list[dict[str, str]],
    *,
    simulate: bool,
    make_message: MessageBuilder,
    deliver: Deliver,
    sleep_fn: Callable[[float], None] = time_module.sleep,
    should_stop: Callable[[], bool] | None = None,
    on_row: Callable[[int, dict[str, str]], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    on_message: Callable[[str], None] | None = None,
) -> SendResult:
    """Envia (ou simula) os e-mails de cada linha respeitando o rate limit.

    ``make_message`` constrói a mensagem a partir da linha; ``deliver`` executa
    o envio real e devolve o dict de destinatários rejeitados. ``on_row``,
    ``on_progress`` e ``on_message`` são callbacks opcionais de progresso.
    """
    report_rows: list[dict[str, str]] = []
    total = len(rows)
    interrupted = False

    for index, row in enumerate(rows, start=1):
        if should_stop is not None and should_stop():
            interrupted = True
            break

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        email_valid = bool(row.get("email_valido", True))

        if not email_valid:
            status = "Simulado" if simulate else "Falha"
            details = "E-mail inválido."
        elif simulate:
            status = "Simulado"
            details = "Nenhum e-mail enviado (modo de simulação)."
        else:
            try:
                rejected = deliver(config, make_message(row))
                if rejected:
                    status = "Rejeitado"
                    details = f"Rejeitados: {rejected}"
                else:
                    status = "Sucesso"
                    details = "Enviado com sucesso"
            except Exception as exc:  # noqa: BLE001 - uma falha não interrompe o lote
                status = "Falha"
                details = str(exc)

        report = {
            "Nome": row["Nome"],
            "E-mail": row["E-mail"],
            "Códigos": row["Códigos"],
            "Status": status,
            "Data_Hora": now,
            "Detalhes": details,
        }
        report_rows.append(report)
        if on_row is not None:
            on_row(index - 1, report)
        if on_progress is not None:
            on_progress(index, total)

        if not simulate and index < total:
            if index % BATCH_SIZE == 0:
                seconds = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
                if on_message is not None:
                    on_message(
                        f"Pausa de segurança após {index} e-mails: {seconds / 60:.1f} minutos."
                    )
            else:
                seconds = random.uniform(DELAY_PER_EMAIL_MIN, DELAY_PER_EMAIL_MAX)

            if should_stop is None:
                sleep_fn(seconds)
            elif not _cooperative_wait(seconds, sleep_fn, should_stop):
                interrupted = True
                break

    failures = sum(row["Status"] in {"Falha", "Rejeitado"} for row in report_rows)
    if interrupted:
        summary = f"Envio interrompido: {len(report_rows)} de {total} e-mails processados."
    elif failures:
        summary = f"Envio concluído com {failures} falha(s) em {total} e-mails."
    elif simulate:
        summary = f"Simulação concluída para {total} e-mail(s). Nenhuma mensagem foi enviada."
    else:
        summary = f"{total} e-mail(s) enviados com sucesso."

    return SendResult(report_rows, interrupted, summary)
