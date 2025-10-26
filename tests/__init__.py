import sys
import types

if "pygame" not in sys.modules:
    pygame_stub = types.ModuleType("pygame")

    class _DummyChannel:
        def __init__(self, index: int):
            self.index = index
            self._busy = False
            self._volume = (0.0, 0.0)

        def get_busy(self):
            return self._busy

        def set_volume(self, left, right):
            self._volume = (left, right)

        def play(self, sound, loops=0):
            self._busy = loops == -1

        def stop(self):
            self._busy = False

    class _DummySound:
        def __init__(self, data):
            self.data = data

    pygame_stub.Surface = lambda *args, **kwargs: None
    pygame_stub.SRCALPHA = 0
    pygame_stub.draw = types.SimpleNamespace(
        circle=lambda *args, **kwargs: None,
        polygon=lambda *args, **kwargs: None,
        arc=lambda *args, **kwargs: None,
        ellipse=lambda *args, **kwargs: None,
        rect=lambda *args, **kwargs: None,
    )
    pygame_stub.time = types.SimpleNamespace(get_ticks=lambda: 0)
    pygame_stub.font = types.SimpleNamespace(
        SysFont=lambda *args, **kwargs: types.SimpleNamespace(
            render=lambda *a, **k: types.SimpleNamespace(
                get_width=lambda: 0,
                get_height=lambda: 0,
                get_rect=lambda: types.SimpleNamespace()
            )
        )
    )
    pygame_stub.mouse = types.SimpleNamespace(
        get_pos=lambda: (0, 0),
        get_pressed=lambda: (False, False, False),
    )
    pygame_stub.display = types.SimpleNamespace(
        Info=lambda: types.SimpleNamespace(current_w=1920, current_h=1080),
        set_mode=lambda *args, **kwargs: None,
    )
    pygame_stub.event = types.SimpleNamespace(get=lambda: [])
    pygame_stub.mixer = types.SimpleNamespace(
        init=lambda **kwargs: None,
        get_init=lambda: False,
        set_num_channels=lambda n: None,
        Channel=lambda index: _DummyChannel(index),
    )
    pygame_stub.sndarray = types.SimpleNamespace(make_sound=lambda data: _DummySound(data))

    sys.modules["pygame"] = pygame_stub
