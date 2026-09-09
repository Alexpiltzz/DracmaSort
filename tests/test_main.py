import builtins

from code_gen import main
from code_gen.core import NotEnoughCodesError


def test_run_processamento_gera_rows(tmp_path, monkeypatch):
    src = tmp_path / "entrada.csv"
    src.write_text(
        "Aluno;Nome;E-mail;Quantidade\nMaria Silva;Maria;maria@ex.com;2\n",
        encoding="utf-8-sig",
    )

    monkeypatch.setattr(main, "default_registry_path", lambda: tmp_path / "codigos.json")
    monkeypatch.setattr(main, "default_student_registry_path", lambda: tmp_path / "alunos.json")
    monkeypatch.setattr(main, "default_output_path", lambda _path: tmp_path / "saida.csv")

    rows = main._run_processamento(src)
    assert rows is not None
    assert len(rows) == 1
    assert rows[0]["Aluno"] == "Maria Silva"
    assert rows[0]["Nome"] == "Maria"
    assert rows[0]["E-mail"] == "maria@ex.com"
    assert len(rows[0]["Códigos"].replace(" ", "").split(",")) == 2


def test_run_processamento_filtra_alunos_ja_rastreados(tmp_path, monkeypatch):
    src = tmp_path / "entrada.csv"
    src.write_text(
        "Aluno;Nome;E-mail;Quantidade\nAna Melo;Ana;ana@ex.com;1\nBia Reis;Bia;bia@ex.com;1\n",
        encoding="utf-8-sig",
    )

    monkeypatch.setattr(main, "default_registry_path", lambda: tmp_path / "codigos.json")
    monkeypatch.setattr(main, "default_student_registry_path", lambda: tmp_path / "alunos.json")
    monkeypatch.setattr(main, "default_output_path", lambda _path: tmp_path / "saida.csv")

    alunos_path = tmp_path / "alunos.json"
    alunos_path.write_text('["ana melo"]', encoding="utf-8")

    rows = main._run_processamento(src)
    assert rows is not None
    assert len(rows) == 1
    assert rows[0]["Aluno"] == "Bia Reis"
    assert "ana melo" in alunos_path.read_text(encoding="utf-8")
    assert "bia reis" in alunos_path.read_text(encoding="utf-8")


def test_run_processamento_planilha_vazia(tmp_path, monkeypatch):
    src = tmp_path / "vazia.csv"
    src.write_text("Aluno;Nome;E-mail;Quantidade\n", encoding="utf-8-sig")
    monkeypatch.setattr(main, "default_registry_path", lambda: tmp_path / "codigos.json")
    assert main._run_processamento(src) is None


def test_run_processamento_erro_leitura(tmp_path):
    src = tmp_path / "errado.txt"
    src.write_text("x", encoding="utf-8")
    assert main._run_processamento(src) is None


def test_run_processamento_sem_codigos(tmp_path, monkeypatch):
    src = tmp_path / "entrada.csv"
    src.write_text(
        "Aluno;Nome;E-mail;Quantidade\nMaria Silva;Maria;maria@ex.com;1\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(main, "default_registry_path", lambda: tmp_path / "codigos.json")
    monkeypatch.setattr(main, "default_student_registry_path", lambda: tmp_path / "alunos.json")

    class Boom(NotEnoughCodesError):
        pass

    def fake_generate(quantities, used_codes, rng=None):
        raise Boom("sem códigos")

    monkeypatch.setattr(main, "generate_codes", fake_generate)
    assert main._run_processamento(src) is None


def test_prompt_credentials(monkeypatch):
    inputs = iter(["novo_login@ex.com", "novo_from@ex.com"])
    monkeypatch.setattr(builtins, "input", lambda _="": next(inputs))
    monkeypatch.setattr(main.getpass, "getpass", lambda _="": "minhasenha")

    cfg = main.SmtpConfig(login="antigo", from_addr="antigo_from", password="")
    nova_cfg = main._prompt_credentials(cfg)
    assert nova_cfg.login == "novo_login@ex.com"
    assert nova_cfg.from_addr == "novo_from@ex.com"
    assert nova_cfg.password == "minhasenha"


def test_run_envio_dry_run_sem_senha(tmp_path, monkeypatch, capsys):
    rows = [{"Nome": "Maria", "E-mail": "maria@ex.com", "Códigos": "0001"}]

    class FakeConfig:
        password = ""
        from_addr = "from@ex.com"

    monkeypatch.setattr(main, "_prompt_credentials", lambda cfg: cfg)
    monkeypatch.setattr(main.SmtpConfig, "from_env", staticmethod(lambda: FakeConfig()))
    monkeypatch.setattr(
        main,
        "montar_mensagem_html",
        lambda *a, **k: type("FakeMsg", (), {"as_string": lambda self="": "mensagem"})(),
    )

    assert main._run_envio(rows, test_mode=False) == 1
    out = capsys.readouterr().out
    assert "dry-run" in out or "Sem senha" in out


def test_run_envio_teste_sem_senha(tmp_path, monkeypatch, capsys):
    rows = [{"Nome": "Maria", "E-mail": "maria@ex.com", "Códigos": "0001"}]

    class FakeConfig:
        password = ""
        from_addr = "from@ex.com"

    monkeypatch.setattr(main, "_prompt_credentials", lambda cfg: cfg)
    monkeypatch.setattr(main.SmtpConfig, "from_env", staticmethod(lambda: FakeConfig()))
    assert main._run_envio(rows, test_mode=True) == 1


def test_run_envio_teste_com_senha_envia_para_to(tmp_path, monkeypatch, capsys):
    rows = [{"Nome": "Maria", "E-mail": "maria@ex.com", "Códigos": "0001"}]

    class FakeConfig:
        password = "senha"
        from_addr = "from@ex.com"
        to_addr = "destino@ex.com"

    chamadas = []
    monkeypatch.setattr(main, "_prompt_credentials", lambda cfg: cfg)
    monkeypatch.setattr(main.SmtpConfig, "from_env", staticmethod(lambda: FakeConfig()))
    monkeypatch.setattr(
        main,
        "montar_mensagem_html",
        lambda nome, from_addr, to_addr, numeros=None: {
            "nome": nome,
            "from": from_addr,
            "to": to_addr,
            "numeros": numeros,
        },
    )
    monkeypatch.setattr(main, "enviar_email", lambda cfg, msg: chamadas.append((cfg, msg)) or {})
    monkeypatch.setattr(builtins, "input", lambda _="": "s")

    assert main._run_envio(rows, test_mode=True) == 0
    assert len(chamadas) == 1
    cfg, msg = chamadas[0]
    assert msg["to"] == "destino@ex.com"
    assert msg["numeros"] is None


def test_run_envio_individual_com_relatorio(tmp_path, monkeypatch, capsys):
    rows = [
        {"Nome": "Maria", "E-mail": "maria@ex.com", "Códigos": "0001"},
        {"Nome": "João", "E-mail": "joao@ex.com", "Códigos": "0002, 0003"},
    ]

    class FakeConfig:
        password = "senha"
        from_addr = "from@ex.com"
        to_addr = "destino@ex.com"

    chamadas = []
    monkeypatch.setattr(main, "_prompt_credentials", lambda cfg: cfg)
    monkeypatch.setattr(main.SmtpConfig, "from_env", staticmethod(lambda: FakeConfig()))
    monkeypatch.setattr(
        main,
        "montar_mensagem_html",
        lambda nome, from_addr, to_addr, numeros=None: {
            "nome": nome,
            "from": from_addr,
            "to": to_addr,
            "numeros": numeros,
        },
    )
    monkeypatch.setattr(main, "enviar_email", lambda cfg, msg: chamadas.append((cfg, msg)) or {})
    monkeypatch.setattr(builtins, "input", lambda _="": "s")
    monkeypatch.setattr(main.time, "sleep", lambda _sec: None)

    input_file = tmp_path / "participantes.csv"
    assert main._run_envio(rows, test_mode=False, input_path=input_file) == 0
    assert len(chamadas) == 2
    assert [msg["to"] for _, msg in chamadas] == ["maria@ex.com", "joao@ex.com"]
    assert [msg["numeros"] for _, msg in chamadas] == ["0001", "0002, 0003"]

    # Verifica geração do relatório
    relatorios = list(tmp_path.glob("relatorio_envio_*.csv"))
    assert len(relatorios) == 1
    conteudo = relatorios[0].read_text(encoding="utf-8-sig")
    assert "maria@ex.com" in conteudo
    assert "joao@ex.com" in conteudo
    assert "Sucesso" in conteudo


def test_run_envio_pausa_lote(tmp_path, monkeypatch):
    rows = [
        {"Nome": f"User {i}", "E-mail": f"user{i}@ex.com", "Códigos": f"{i:04d}"}
        for i in range(1, 52)
    ]

    class FakeConfig:
        password = "senha"
        from_addr = "from@ex.com"
        to_addr = "destino@ex.com"

    sleeps = []
    monkeypatch.setattr(main, "_prompt_credentials", lambda cfg: cfg)
    monkeypatch.setattr(main.SmtpConfig, "from_env", staticmethod(lambda: FakeConfig()))
    monkeypatch.setattr(main, "montar_mensagem_html", lambda *a, **k: {})
    monkeypatch.setattr(main, "enviar_email", lambda cfg, msg: {})
    monkeypatch.setattr(builtins, "input", lambda _="": "s")
    monkeypatch.setattr(main.time, "sleep", lambda sec: sleeps.append(sec))

    assert main._run_envio(rows, test_mode=False) == 0
    assert len(sleeps) == 50
    # O 50º sleep deve corresponder à pausa de lote (>= 300s)
    assert sleeps[49] >= 300.0
