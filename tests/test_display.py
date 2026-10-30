"""The resizable window: opening size, letterbox and mouse mapping."""
import pygame
import pytest

from pygame_rpg.gui.display import Display, fit_scale, letterbox


@pytest.fixture
def display():
    pygame.init()
    yield Display()
    pygame.quit()


def test_fit_scale_fills_most_of_the_desktop():
    assert fit_scale((1920, 1080)) == 1.5      # 1200 x 900
    assert fit_scale((2560, 1440)) == 2.0
    assert fit_scale((1280, 720)) == 1.0       # never smaller than 1x
    assert fit_scale((800, 600)) == 1.0


def test_letterbox_keeps_the_aspect_and_centres():
    assert letterbox((1600, 1200)) == pygame.Rect(0, 0, 1600, 1200)
    assert letterbox((1920, 1080)) == pygame.Rect(240, 0, 1440, 1080)
    assert letterbox((800, 1000)) == pygame.Rect(0, 200, 800, 600)


def test_mouse_events_map_to_the_canvas(display):
    display.window = pygame.display.set_mode((1920, 1080), pygame.RESIZABLE)
    display._layout()
    ev = display.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, pos=(240 + 720, 540), button=1))
    assert ev.pos == (400, 300) and ev.button == 1
    ev = display.handle_event(pygame.event.Event(
        pygame.MOUSEMOTION, pos=(0, 0), rel=(18, 18), buttons=(0, 0, 0)))
    assert ev.pos == (0, 0)                    # black bar clamps to the edge
    assert ev.rel == (10, 10)


def test_resize_and_present(display):
    assert display.handle_event(pygame.event.Event(
        pygame.VIDEORESIZE, size=(1000, 500), w=1000, h=500)) is None
    assert display.window_size == (1000, 500)
    key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
    assert display.handle_event(key) is key
    display.canvas.fill((255, 0, 0))
    display.present()
    w, h = display.window.get_size()
    assert display.window.get_at((w // 2, h // 2))[:3] == (255, 0, 0)
