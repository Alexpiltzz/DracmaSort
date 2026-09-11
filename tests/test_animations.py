import random

from PyQt6.QtCore import QCoreApplication

from gui.animations import SorteioRevealAnimator


def _ensure_app() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


_ensure_app()


def test_animator_revela_vencedor_no_fim():
    animator = SorteioRevealAnimator()
    pool = ["ana melo", "bia lima", "caio souza"]
    ticks: list[str] = []
    finals: list[str] = []
    animator.tick.connect(ticks.append)
    animator.finished.connect(finals.append)
    animator.start(pool, "bia lima", rng=random.Random(1))
    for _ in range(SorteioRevealAnimator.STEPS):
        animator._on_tick()
    assert finals == ["bia lima"]
    assert ticks, "deveria ha items intermediarios antes da revelacao"
    assert set(ticks) <= set(pool), "items intermediarios devem vir do pool"


def test_animator_nao_mutua_pool_original():
    animator = SorteioRevealAnimator()
    pool = ["ana melo", "bia lima", "caio souza"]
    animator.start(pool, "caio souza", rng=random.Random(2))
    for _ in range(SorteioRevealAnimator.STEPS):
        animator._on_tick()
    assert len(pool) == 3


def test_animator_intervalos_crescem():
    animator = SorteioRevealAnimator()
    intervals = [animator._interval_for(i) for i in range(SorteioRevealAnimator.STEPS)]
    assert intervals == sorted(intervals)
    assert intervals[-1] > intervals[0]


def test_animator_stop_cancela_e_nao_emite_finished():
    animator = SorteioRevealAnimator()
    finals: list[str] = []
    animator.finished.connect(finals.append)
    animator.start(["ana melo", "bia lima"], "ana melo")
    animator.stop()
    for _ in range(SorteioRevealAnimator.STEPS):
        animator._on_tick()
    assert finals == []
