"""Envio de e-mails via SMTP do Outlook/Office 365 com caixa compartilhada.

A autenticação usa a conta definida em ``login`` (que possui permissão de
"enviar como" sobre a caixa compartilhada) enquanto o cabeçalho ``From`` usa a
caixa compartilhada de origem. As configurações são lidas de variáveis de
ambiente e, quando presente, de um arquivo ``.env`` na raiz do projeto.
"""

import os
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import markdown as markdown_lib

from .runtime import app_root

_PREFIX = "GIVEAWAY_SMTP_"

_DEFAULT_HOST = "smtp.office365.com"
_DEFAULT_PORT = 587
_DEFAULT_LOGIN = "alex.fritsche@adm.educadventista.org"
_DEFAULT_FROM = "dpcab.anc@adm.educadventista.org"
_DEFAULT_TO = "alexpiltz.fritsche@gmail.com"
_DEFAULT_SUBJECT = "Seus números para o sorteio"


def project_root() -> Path:
    """Raiz do projeto, pasta que contém o ``.env`` e o ``pyproject.toml``."""
    return app_root()


def load_env_file(path: Path | None = None) -> None:
    """Carrega variáveis de um arquivo ``.env`` para o ambiente.

    Valores já presentes no ambiente têm precedência (não são sobrescritos), o
    que permite fornecer a senha por ambiente sem depender do arquivo.
    """
    env_path = path or project_root() / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class SmtpConfig:
    """Configuração de conexão SMTP, lida das variáveis de ambiente."""

    host: str = _DEFAULT_HOST
    port: int = _DEFAULT_PORT
    login: str = _DEFAULT_LOGIN
    password: str = ""
    from_addr: str = _DEFAULT_FROM
    to_addr: str = _DEFAULT_TO

    @classmethod
    def from_env(cls) -> "SmtpConfig":
        """Constrói a configuração a partir do ambiente (após carregar o ``.env``)."""
        return cls(
            host=os.environ.get(f"{_PREFIX}HOST", _DEFAULT_HOST),
            port=int(os.environ.get(f"{_PREFIX}PORT", str(_DEFAULT_PORT))),
            login=os.environ.get(f"{_PREFIX}LOGIN", _DEFAULT_LOGIN),
            password=os.environ.get(f"{_PREFIX}PASS", ""),
            from_addr=os.environ.get(f"{_PREFIX}FROM", _DEFAULT_FROM),
            to_addr=os.environ.get(f"{_PREFIX}TO", _DEFAULT_TO),
        )

    @property
    def configured(self) -> bool:
        """True quando há credencial e destinatário para um envio real."""
        return bool(self.password and self.to_addr)


def markdown_to_html(markdown_text: str) -> str:
    """Converte Markdown em HTML com as extensões usadas na UI."""
    return markdown_lib.markdown(markdown_text, extensions=["extra", "sane_lists"])


def _replace_placeholders(text: str, replacements: dict[str, str]) -> str:
    rendered = text
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def build_custom_message(
    subject: str,
    body: str,
    *,
    nome: str,
    remetente: str,
    destinatario: str,
    codigos: str = "",
) -> MIMEMultipart:
    """Monta uma mensagem editável da UI, convertendo Markdown para HTML."""
    return montar_mensagem_html(
        nome,
        remetente,
        destinatario,
        numeros=codigos,
        subject=subject,
        body=body,
    )


def montar_mensagem_html(
    nome: str,
    from_addr: str,
    to_addr: str,
    numeros: list[str] | str | None = None,
    *,
    subject: str = _DEFAULT_SUBJECT,
    body: str | None = None,
) -> MIMEMultipart:
    """Monta a mensagem de e-mail em HTML.

    Quando ``body`` é informado, ele é tratado como Markdown editável com os
    placeholders ``{nome}``, ``{codigos}``, ``{remetente}`` e
    ``{destinatario}``. Caso contrário, mantém o comportamento padrão do
    fluxo de terminal, usando o texto do sorteio ou a mensagem de teste.
    """
    if isinstance(numeros, list):
        numeros_formatados = ", ".join(numeros)
    elif numeros is None:
        numeros_formatados = ""
    else:
        numeros_formatados = str(numeros)

    replacements = {
        "{nome}": nome,
        "{codigos}": numeros_formatados,
        "{remetente}": from_addr,
        "{destinatario}": to_addr,
    }
    rendered_subject = _replace_placeholders(subject, replacements)

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = rendered_subject

    if body is not None:
        corpo = markdown_to_html(_replace_placeholders(body, replacements))
    elif numeros_formatados:
        corpo = f"""
    <html>
    <body>

        <p>Olá, <strong>{nome}</strong>!</p>

        <p>
        Agradecemos pela realização da matrícula.
        </p>

        <p>
        Você recebeu os seguintes números para participar do nosso sorteio:
        </p>

        <h2>
            {numeros_formatados}
        </h2>

        <p>
        Guarde estes números.
        </p>

        <br>

        <p>
        Atenciosamente,<br>
        <strong>Colégio</strong>
        </p>

    </body>
    </html>
    """
    else:
        corpo = f"""
        <html><body>
            <p>Olá, <strong>{nome}</strong>!</p>
            <p>Este é um e-mail de teste enviado a partir da caixa compartilhada
            <strong>{from_addr}</strong>.</p>
            <p>Se você recebeu esta mensagem, a configuração de envio está funcionando.</p>
        </body></html>
        """

    msg.attach(MIMEText(corpo, "html"))
    return msg


def enviar_email(config: SmtpConfig, msg: MIMEMultipart) -> dict:
    """Envia ``msg`` via SMTP autenticando com a conta de ``config.login``.

    O cabeçalho ``From`` usa a caixa compartilhada e a autenticação usa a conta
    com permissão de "enviar como". Retorna o dict de destinatários rejeitados
    (vazio em caso de sucesso completo).
    """
    servidor = smtplib.SMTP(config.host, config.port)
    try:
        servidor.starttls()
        servidor.login(config.login, config.password)
        return servidor.send_message(msg)
    finally:
        servidor.quit()


load_env_file()
