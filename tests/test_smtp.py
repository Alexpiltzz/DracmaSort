import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest

# ==========================================
# CONFIGURAÇÕES
# ==========================================
# As credenciais NÃO devem ficar no código. Defina estas variáveis
# de ambiente antes de executar o teste. Exemplo (PowerShell):
#
#   $env:GIVEAWAY_SMTP_LOGIN  = "alex.fritsche@adm.educadventista.org"
#   $env:GIVEAWAY_SMTP_PASS    = "SUA_SENHA"
#   $env:GIVIVEAWAY_SMTP_FROM  = "dpcab.anc@adm.educadventista.org"
#
# O login usa a conta do remetente (que tem permissão de "enviar como")
# sobre a caixa compartilhada definida em SMTP_FROM.

SMTP_HOST = os.environ.get("GIVEAWAY_SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.environ.get("GIVEAWAY_SMTP_PORT", "587"))

LOGIN = os.environ.get("GIVEAWAY_SMTP_LOGIN", "alex.fritsche@adm.educadventista.org")
PASSWORD = os.environ.get("GIVEAWAY_SMTP_PASS")
EMAIL_REMETENTE = os.environ.get("GIVEAWAY_SMTP_FROM", "dpcab.anc@adm.educadventista.org")
EMAIL_DESTINO = os.environ.get("GIVEAWAY_SMTP_TO", "alexpiltz.fritsche@gmail.com")

pytestmark = pytest.mark.skipif(
    not PASSWORD,
    reason="Defina GIVEAWAY_SMTP_PASS para executar o teste de envio real.",
)


def _montar_mensagem(nome="Teste"):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = EMAIL_DESTINO
    msg["Subject"] = "[Teste] Configuração de envio de e-mail"

    corpo = f"""
    <html>
    <body>
        <p>Olá, <strong>{nome}</strong>!</p>
        <p>Este é um e-mail de teste enviado a partir da caixa compartilhada
        <strong>{EMAIL_REMETENTE}</strong>.</p>
        <p>Se você recebeu esta mensagem, a configuração de envio está funcionando.</p>
    </body>
    </html>
    """

    msg.attach(MIMEText(corpo, "html"))
    return msg


def test_login_e_envio_via_caixa_compartilhada():
    msg = _montar_mensagem("alexpiltz")

    servidor = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    try:
        servidor.starttls()
        servidor.login(LOGIN, PASSWORD)
        enviados = servidor.send_message(msg)
        assert enviados == {}
    finally:
        servidor.quit()
