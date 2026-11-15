from __future__ import annotations

from pyforge.scene import Scene, SceneManager


class RecordingScene(Scene):
    def __init__(self, name: str, log: list[str]) -> None:
        super().__init__()
        self.name = name
        self.log = log

    def on_enter(self) -> None:
        self.log.append(f"enter:{self.name}")

    def on_exit(self) -> None:
        self.log.append(f"exit:{self.name}")

    def on_pause(self) -> None:
        self.log.append(f"pause:{self.name}")

    def on_resume(self) -> None:
        self.log.append(f"resume:{self.name}")


def make_manager() -> SceneManager:
    # The SceneManager only needs an object to hand to scenes as ``app``.
    return SceneManager(app=object())  # type: ignore[arg-type]


def test_push_pop_lifecycle() -> None:
    log: list[str] = []
    mgr = make_manager()
    mgr.push(RecordingScene("menu", log))
    mgr.push(RecordingScene("game", log))
    mgr.pop()
    assert log == ["enter:menu", "pause:menu", "enter:game", "exit:game", "resume:menu"]
    assert mgr.stack_size == 1


def test_replace_keeps_below() -> None:
    log: list[str] = []
    mgr = make_manager()
    mgr.push(RecordingScene("menu", log))
    mgr.push(RecordingScene("a", log))
    mgr.replace(RecordingScene("b", log))
    assert "exit:a" in log and "enter:b" in log
    assert mgr.stack_size == 2  # menu + b


def test_draw_depth_respects_transparency() -> None:
    mgr = make_manager()
    base = Scene()
    overlay = Scene()
    overlay.transparent = True
    mgr.push(base)
    mgr.push(overlay)
    # Both should be in the active draw slice because overlay is transparent.
    assert mgr._draw_depth() == 2
    opaque = Scene()
    mgr.push(opaque)
    assert mgr._draw_depth() == 1


def test_update_depth_respects_update_below() -> None:
    mgr = make_manager()
    base = Scene()
    pause = Scene()
    pause.update_below = False
    mgr.push(base)
    mgr.push(pause)
    assert mgr._update_depth() == 1  # base is frozen under the pause menu
