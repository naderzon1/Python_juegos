import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.core.config import GameConfig  # noqa: E402
from game.progression.profile import PlayerProfile  # noqa: E402


@pytest.fixture(scope="session")
def config():
    return GameConfig()


@pytest.fixture
def profile(config):
    return PlayerProfile.new(config, "Prueba")
