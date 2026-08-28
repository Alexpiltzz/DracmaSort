import pytest

from code_gen.smtp import SmtpConfig, enviar_email, montar_mensagem_html

# As credenciais são lidas de variáveis de ambiente ou do arquivo .env na raiz
# do projeto (ver src/code_gen/smtp.py). A senha nunca deve ficar commitada.

def test_montar_mensagem_html_conteudo():
    msg = montar_mensagem_html("Ana", "from@ex.com", "to@ex.com", numeros=["0001", "0002"])
    html = msg.get_payload(0).get_payload(decode=True).decode("utf-8")
    assert "Olá, <strong>Ana</strong>!" in html
    assert "participar do nosso sorteio:" in html
    assert "0001, 0002" in html
    assert "Atenciosamente,<br>" in html



config = SmtpConfig.from_env()


@pytest.mark.skipif(
    not config.configured,
    reason="Defina GIVEAWAY_SMTP_PASS (ou no .env) para executar o teste de envio real.",
)
def test_login_e_envio_via_caixa_compartilhada():
    msg = montar_mensagem_html("alexpiltz", from_addr=config.from_addr, to_addr=config.to_addr)
    rejeitados = enviar_email(config, msg)
    assert rejeitados == {}

