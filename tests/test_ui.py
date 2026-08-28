from code_gen.smtp import SmtpConfig
from code_gen.ui import EmailWorker, build_custom_message, _status_for_email


def test_build_custom_message_substitui_placeholders():
    message = build_custom_message(
        "Olá {nome}",
        "Código: <strong>{codigos}</strong>",
        nome="Maria",
        remetente="escola@example.com",
        destinatario="maria@example.com",
        codigos="0001",
    )

    assert message["Subject"] == "Olá Maria"
    body = message.get_payload()[0].get_payload(decode=True).decode()
    assert "0001" in body
    assert "{codigos}" not in body


def test_email_worker_simulacao_gera_relatorio_sem_enviar():
    rows = [{"Nome": "Maria", "E-mail": "maria@example.com", "Códigos": "0001, 0002"}]
    worker = EmailWorker(rows, SmtpConfig(), simulate=True)
    reports = []
    summaries = []

    worker.row_finished.connect(lambda _index, report: reports.append(report))
    worker.finished.connect(lambda _reports, _completed, summary: summaries.append(summary))
    worker.run()

    assert reports[0]["Status"] == "Simulado"
    assert reports[0]["E-mail"] == "maria@example.com"
    assert "Nenhuma mensagem foi enviada" in summaries[0]


def test_status_for_email_valida_e_invalida():
    assert _status_for_email("maria@example.com") == ("Aguardando envio", "Aguardando envio")
    assert _status_for_email("maria@exemplo") == (
        "Aguardando envio | E-mail inválido",
        "E-mail inválido",
    )
