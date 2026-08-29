import os

import pytest

from delivery.smtp import SmtpConfig, enviar_email, montar_mensagem_html


def test_montar_mensagem_html_conteudo():
    msg = montar_mensagem_html("Ana", "from@ex.com", "to@ex.com", numeros=["0001", "0002"])
    html = msg.get_payload(0).get_payload(decode=True).decode("utf-8")
    assert "Olá, <strong>Ana</strong>!" in html
    assert "participar do nosso sorteio:" in html
    assert "0001, 0002" in html
    assert "Atenciosamente,<br>" in html


config = SmtpConfig.from_env()

run_real_smtp_test = (
    config.configured
    and config.password not in {"", "SUA_SENHA_AQUI"}
    and os.environ.get("GIVEAWAY_SMTP_TEST_REAL") == "1"
)


@pytest.mark.skipif(
    not run_real_smtp_test,
    reason="Defina GIVEAWAY_SMTP_TEST_REAL=1 para o teste real.",
)
def test_login_e_envio_via_caixa_compartilhada():
    msg = montar_mensagem_html("alexpiltz", from_addr=config.from_addr, to_addr=config.to_addr)
    rejeitados = enviar_email(config, msg)
    assert rejeitados == {}
