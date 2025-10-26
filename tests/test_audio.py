import numpy as np
from pathlib import Path

from audio.catalog import EventCatalog
from audio.recipes import RecipeLibrary
from audio.renderer import Renderer
from audio.sfx import SFX


ASSETS = Path("assets")


def test_catalog_variant_rotation():
    catalog = EventCatalog(ASSETS / "sfx_catalog.json")
    spec = catalog.get_spec("hit")
    assert spec.bus == "sfx"
    order = [catalog.next_variant("hit") for _ in range(4)]
    assert order[:3] == ["hit_a", "hit_b", "hit_c"]
    assert order[3] == "hit_a"


def test_recipe_inheritance_layers():
    library = RecipeLibrary(ASSETS / "sfx_recipes.json")
    recipe = library.get("hit_b")
    assert len(recipe.layers) == 2
    assert recipe.layers[0].lp_hz == 3600.0


def test_renderer_output_shape():
    library = RecipeLibrary(ASSETS / "sfx_recipes.json")
    renderer = Renderer(library)
    buffer = renderer.render("ui_click")
    assert buffer.ndim == 2 and buffer.shape[1] == 2
    assert np.max(np.abs(buffer)) <= 1.0


def test_sfx_cooldown_respected():
    sfx = SFX(enable_audio=False, config_path=str(ASSETS))
    assert sfx.play("hit")
    assert not sfx.play("hit")  # cooldown prevents immediate replay
    sfx.update(0.2)
    assert sfx.play("hit")
