"""A small retained-mode UI layer for menus and HUDs.

Widgets live in screen space and are organised in a tree under a :class:`UIRoot`.
``anchor`` computes a screen rectangle relative to the viewport so layouts adapt
to window resizing.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from .input import InputManager
from .math import Rect, Vec2
from .render import Color, Layer, Renderer

__all__ = ["Button", "Label", "Panel", "UIRoot", "Widget", "anchor"]


def anchor(
    viewport: Vec2,
    width: float,
    height: float,
    *,
    align: str = "center",
    offset: Vec2 | None = None,
) -> Rect:
    """Build a screen rect of ``width``x``height`` anchored within ``viewport``.

    ``align`` is one of: center, top, bottom, left, right, topleft, topright,
    bottomleft, bottomright.
    """
    off = offset or Vec2.zero()
    ax = {"left": 0.0, "right": 1.0}.get(_h(align), 0.5)
    ay = {"top": 0.0, "bottom": 1.0}.get(_v(align), 0.5)
    x = (viewport.x - width) * ax + off.x
    y = (viewport.y - height) * ay + off.y
    return Rect(x, y, width, height)


def _h(align: str) -> str:
    if "left" in align:
        return "left"
    if "right" in align:
        return "right"
    return "center"


def _v(align: str) -> str:
    if "top" in align:
        return "top"
    if "bottom" in align:
        return "bottom"
    return "center"


class Widget:
    """Base UI element with a screen-space rect."""

    def __init__(self, rect: Rect) -> None:
        self.rect = rect
        self.visible = True

    def update(self, inp: InputManager) -> None:
        pass

    def draw(self, renderer: Renderer) -> None:
        pass


class Label(Widget):
    def __init__(
        self,
        text: str,
        font: pygame.font.Font,
        position: Vec2,
        *,
        color: Color = (235, 235, 245),
        align: str = "topleft",
    ) -> None:
        super().__init__(Rect(position.x, position.y, 0.0, 0.0))
        self.text = text
        self.font = font
        self.color = color
        self.align = align

    def draw(self, renderer: Renderer) -> None:
        if not self.visible:
            return
        renderer.draw_text(
            self.font,
            self.text,
            Vec2(self.rect.x, self.rect.y),
            self.color,
            anchor=self.align,
            layer=Layer.UI,
            screen_space=True,
        )


class Button(Widget):
    def __init__(
        self,
        text: str,
        font: pygame.font.Font,
        rect: Rect,
        on_click: Callable[[], None],
        *,
        color: Color = (54, 60, 84),
        hover_color: Color = (74, 84, 120),
        press_color: Color = (40, 44, 64),
        text_color: Color = (235, 235, 245),
    ) -> None:
        super().__init__(rect)
        self.text = text
        self.font = font
        self.on_click = on_click
        self.color = color
        self.hover_color = hover_color
        self.press_color = press_color
        self.text_color = text_color
        self._hovered = False
        self._pressed = False

    def update(self, inp: InputManager) -> None:
        if not self.visible:
            return
        self._hovered = self.rect.contains_point(inp.mouse_position)
        if self._hovered and inp.mouse_pressed(0):
            self._pressed = True
        if inp.mouse_released(0):
            if self._pressed and self._hovered:
                self.on_click()
            self._pressed = False

    def draw(self, renderer: Renderer) -> None:
        if not self.visible:
            return
        if self._pressed:
            fill = self.press_color
        elif self._hovered:
            fill = self.hover_color
        else:
            fill = self.color
        renderer.draw_rect(self.rect, fill, layer=Layer.UI, screen_space=True)
        renderer.draw_rect(self.rect, (20, 22, 32), width=2, layer=Layer.UI, z=1, screen_space=True)
        renderer.draw_text(
            self.font,
            self.text,
            self.rect.center,
            self.text_color,
            anchor="center",
            layer=Layer.UI,
            z=2,
            screen_space=True,
        )


class Panel(Widget):
    """A container with a background that lays out and forwards to children."""

    def __init__(
        self,
        rect: Rect,
        *,
        color: Color = (28, 30, 44, 220),
        border_color: Color | None = (90, 96, 130),
    ) -> None:
        super().__init__(rect)
        self.color = color
        self.border_color = border_color
        self.children: list[Widget] = []

    def add(self, widget: Widget) -> Widget:
        self.children.append(widget)
        return widget

    def update(self, inp: InputManager) -> None:
        if not self.visible:
            return
        for child in self.children:
            child.update(inp)

    def draw(self, renderer: Renderer) -> None:
        if not self.visible:
            return
        renderer.draw_rect(self.rect, self.color, layer=Layer.UI, z=-1, screen_space=True)
        if self.border_color is not None:
            renderer.draw_rect(
                self.rect, self.border_color, width=2, layer=Layer.UI, z=0, screen_space=True
            )
        for child in self.children:
            child.draw(renderer)


class UIRoot(Widget):
    """Top-level widget collection; pump from a scene's update/draw."""

    def __init__(self) -> None:
        super().__init__(Rect(0, 0, 0, 0))
        self.children: list[Widget] = []

    def add(self, widget: Widget) -> Widget:
        self.children.append(widget)
        return widget

    def clear(self) -> None:
        self.children.clear()

    def update(self, inp: InputManager) -> None:
        for child in self.children:
            child.update(inp)

    def draw(self, renderer: Renderer) -> None:
        for child in self.children:
            child.draw(renderer)
