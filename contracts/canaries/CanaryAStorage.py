# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class CanaryAStorage(gl.Contract):
    """Deterministic validator-health canary: no web, model, or value transfer."""

    value: u256

    def __init__(self):
        self.value = u256(0)

    @gl.public.write
    def increment(self) -> u256:
        self.value += u256(1)
        return self.value

    @gl.public.view
    def get_value(self) -> u256:
        return self.value
