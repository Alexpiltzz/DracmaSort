from PyQt6.QtWidgets import QApplication

from gui.animations import ConfettiWidget
from gui.streaming import StreamingWindow


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


_APP: QApplication = _ensure_app()


def test_streaming_window_atualiza_vencedor():
    win = StreamingWindow()
    win.update_winner("JOAO DA SILVA")
    assert win._result_label.text() == "JOAO DA SILVA"


def test_streaming_window_atualiza_titulo():
    win = StreamingWindow()
    win.update_title("SORTEANDO...")
    assert win._title_label.text() == "SORTEANDO..."


def test_streaming_window_atualiza_historico():
    win = StreamingWindow()
    win.update_history("1º sorteado: ANA\n2º sorteado: BIA")
    assert win._history_edit.toPlainText() == "1º sorteado: ANA\n2º sorteado: BIA"


def test_streaming_window_reset_limpa_estado():
    win = StreamingWindow()
    win.update_winner("CAIO")
    win.update_history("1º sorteado: CAIO")
    win.reset()
    assert win._result_label.text() == "Aguardando sorteio..."
    assert win._history_edit.toPlainText() == ""
    assert win._title_label.text() == "VENCEDOR"


def test_streaming_window_fechar_emite_closed_e_oculta():
    win = StreamingWindow()
    closed: list[bool] = []
    win.closed.connect(lambda: closed.append(True))
    win.close()
    assert closed == [True]


def test_streaming_window_aplica_estilo():
    win = StreamingWindow()
    qss = "QFrame#streaming_result_frame { border-radius: 14px; }"
    win.apply_stream_style(qss)
    assert win.styleSheet() == qss


def test_streaming_window_cria_com_minimo_aceitavel():
    win = StreamingWindow()
    assert win.minimumWidth() >= 480
    assert win.minimumHeight() >= 360


def test_streaming_window_nao_tem_botao_fullscreen():
    win = StreamingWindow()
    assert not hasattr(win, "_fullscreen_button")


def test_streaming_window_alterna_tela_cheia():
    win = StreamingWindow()
    win.show()
    assert not win.isFullScreen()
    win.toggle_fullscreen()
    assert win.isFullScreen()
    win.toggle_fullscreen()
    assert not win.isFullScreen()
    win.close()


def test_streaming_window_celebrate_oculta_nao_cria_confetti():
    win = StreamingWindow()
    win.celebrate()
    assert win._result_frame.findChildren(ConfettiWidget) == []


def test_streaming_window_celebrate_visivel_cria_confetti():
    win = StreamingWindow()
    win.show()
    win.celebrate()
    assert win._result_frame.findChildren(ConfettiWidget)
    win.close()


def test_streaming_window_codes_mode_property():
    win = StreamingWindow()
    win.set_codes_mode(True)
    assert win._result_label.property("codes") is True
    win.set_codes_mode(False)
    assert win._result_label.property("codes") is False


def test_confetti_widget_start_aceita_frames_e_escala():
    from PyQt6.QtWidgets import QWidget

    parent = QWidget()
    confetti = ConfettiWidget(parent)
    confetti.start(count=40, frames=20, particle_scale=1.4, speed_scale=0.7)
    assert len(confetti._particles) == 40
    assert confetti._max_frames == 20
    assert all(p["speed"] <= 1.2 for p in confetti._particles), "speed_scale reduz a velocidade"
    assert all(p["size"] >= 7.0 for p in confetti._particles), "particles_scale aumenta o tamanho"
    confetti.close()
    parent.close()


def test_streaming_window_f11_alterna_tela_cheia():
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent

    win = StreamingWindow()
    win.show()
    assert not win.isFullScreen()
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_F11,
        Qt.KeyboardModifier.NoModifier,
    )
    win.keyPressEvent(event)
    assert win.isFullScreen()
    win.toggle_fullscreen()
    win.close()
