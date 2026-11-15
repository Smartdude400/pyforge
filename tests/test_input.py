from __future__ import annotations

from pyforge.input import InputManager, KeyBind

# Raw key codes (avoid initialising pygame video just for constants).
K_SPACE = 32
K_A = 97
K_D = 100


def make_manager() -> InputManager:
    mgr = InputManager()
    mgr._keys = [False] * 128  # inject a fake keyboard snapshot
    return mgr


def press(mgr: InputManager, *keys: int) -> None:
    snapshot = [False] * 128
    for key in keys:
        snapshot[key] = True
    mgr._keys = snapshot


def test_digital_action_resolves() -> None:
    mgr = make_manager()
    mgr.bind_action("jump", KeyBind(K_SPACE))
    assert mgr.value("jump") == 0.0
    press(mgr, K_SPACE)
    assert mgr.value("jump") == 1.0


def test_axis_combines_opposing_keys() -> None:
    mgr = make_manager()
    mgr.bind_axis("move_x", KeyBind(K_D, 1.0), KeyBind(K_A, -1.0))
    press(mgr, K_D)
    assert mgr.axis("move_x") == 1.0
    press(mgr, K_A)
    assert mgr.axis("move_x") == -1.0
    press(mgr, K_A, K_D)
    assert mgr.axis("move_x") == 0.0


def test_edge_states() -> None:
    mgr = make_manager()
    mgr.bind_action("jump", KeyBind(K_SPACE))

    mgr._set_active({"jump"})
    assert mgr.just_pressed("jump") and mgr.held("jump")
    assert not mgr.just_released("jump")

    mgr._set_active({"jump"})
    assert not mgr.just_pressed("jump") and mgr.held("jump")

    mgr._set_active(set())
    assert mgr.just_released("jump") and not mgr.held("jump")


def test_bindings_round_trip() -> None:
    mgr = make_manager()
    mgr.bind_action("jump", KeyBind(K_SPACE))
    mgr.bind_axis("move_x", KeyBind(K_D, 1.0), KeyBind(K_A, -1.0))
    data = mgr.export_bindings()

    restored = make_manager()
    restored.import_bindings(data)
    press(restored, K_D)
    assert restored.axis("move_x") == 1.0
    press(restored, K_SPACE)
    assert restored.value("jump") == 1.0
