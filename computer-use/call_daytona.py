from __future__ import annotations
import asyncio
import logging
from typing import Any
from agents import AsyncComputer, Button, Environment

logger = logging.getLogger(__name__)

_DEFAULT_WIDTH, _DEFAULT_HEIGHT = 1024, 768
# CUA emits DOM KeyboardEvent.key-style names (for example "ArrowDown"); Daytona
# uses robotgo key names internally. Lowercase, then translate the few that
# differ. Keys not in the table pass through unchanged.
_CUA_KEY_TO_DAYTONA: dict[str, str] = {
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
    "arrowup": "up",
    "option": "alt",
    "super": "cmd",
    "win": "cmd",
}
def _normalize_key(key: str) -> str:
    if len(key) > 1:
        key = _CUA_KEY_TO_DAYTONA.get(key.lower(), key.lower())
    return key
class DaytonaAsyncComputer(AsyncComputer):
    """AsyncComputer implementation backed by a Daytona sandbox desktop."""
    def __init__(
        self,
        sandbox: Any,
        *,
        width: int = _DEFAULT_WIDTH,
        height: int = _DEFAULT_HEIGHT,
    ) -> None:
        self._sandbox = sandbox
        self._width = width
        self._height = height
    async def __aenter__(self) -> DaytonaAsyncComputer:
        await self._sandbox.computer_use.start()
        # Give Xvfb, the window manager, and the VNC server a moment to come up.
        await asyncio.sleep(2)
        return self
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            await self._sandbox.computer_use.stop()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Failed to stop computer-use processes", exc_info=True)
    @property
    def environment(self) -> Environment:
        # CUA's Environment enum is {"windows", "mac", "ubuntu", "browser"} — there is
        # no generic "linux", so "ubuntu" is the right value for any Linux desktop
        # (the snapshot here is Debian) since it selects Linux-style UI conventions.
        return "ubuntu"
    @property
    def dimensions(self) -> tuple[int, int]:
        return (self._width, self._height)
    async def screenshot(self) -> str:
        response = await self._sandbox.computer_use.screenshot.take_full_screen()
        return response.screenshot or ""
    async def click(self, x: int, y: int, button: Button) -> None:
        if button not in ("left", "right"):
            logger.warning("Daytona does not support %s clicks; ignoring.", button)
            return
        await self._sandbox.computer_use.mouse.click(x, y, button)
    async def double_click(self, x: int, y: int) -> None:
        await self._sandbox.computer_use.mouse.click(x, y, "left", True)
    async def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        if scroll_y != 0:
            direction = "down" if scroll_y > 0 else "up"
            amount = max(1, abs(scroll_y) // 100)
            await self._sandbox.computer_use.mouse.scroll(x, y, direction, amount)
        if scroll_x != 0:
            logger.warning(
                "Daytona does not support horizontal scrolling; ignoring scroll_x=%d.",
                scroll_x,
            )
    async def type(self, text: str) -> None:
        await self._sandbox.computer_use.keyboard.type(text)
    async def wait(self) -> None:
        await asyncio.sleep(1)
    async def move(self, x: int, y: int) -> None:
        await self._sandbox.computer_use.mouse.move(x, y)
    async def keypress(self, keys: list[str]) -> None:
        if not keys:
            return
        if len(keys) == 1:
            await self._sandbox.computer_use.keyboard.press(_normalize_key(keys[0]))
        else:
            # Multiple keys: treat the last as the primary key, the rest as modifiers.
            *modifiers, key = keys
            await self._sandbox.computer_use.keyboard.press(
                _normalize_key(key), [_normalize_key(m) for m in modifiers]
            )
    async def drag(self, path: list[tuple[int, int]]) -> None:
        if len(path) < 2:
            return
        # Daytona drag takes start -> end; chain segments for multi-point paths.
        for i in range(len(path) - 1):
            sx, sy = path[i]
            ex, ey = path[i + 1]
            await self._sandbox.computer_use.mouse.drag(sx, sy, ex, ey)