import pytest

from code_gen.smtp import SmtpConfig, enviar_email, montar_mensagem_html

# As credenciais são lidas de variáveis de ambiente ou do arquivo .env na raiz
# do projeto (ver src/code_gen/smtp.py). A senha nunca deve ficar commitada.

config = SmtpConfig.from_env()

pytestmark = pytest.mark.skipif(
    not config.configured,
    reason="Defina GIVEAWAY_SMTP_PASS (ou no .env) para executar o teste de envio real.",
)


def test_login_e_envio_via_caixa_compartilhada():
    msg = montar_mensagem_html("alexpiltz", from_addr=config.from_addr, to_addr=config.to_addr)
    rejeitados = enviar_email(config, msg)
    assert rejeitados == {}
