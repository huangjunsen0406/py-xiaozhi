"""Application cleanup delegates playback lifetime to the player's owner."""

import pytest

from src.bootstrap.container import ServiceContainer
from src.bootstrap.plugin_wiring import register_cleanup_resources


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_fails", [False, True])
async def test_music_owner_stops_once_and_detaches_even_on_failure(stop_fails):
    class Player:
        stop_calls = 0
        detached = False

        async def stop(self):
            self.stop_calls += 1
            if stop_fails:
                raise RuntimeError("injected music stop failure")

        async def detach(self):
            try:
                await self.stop()
            finally:
                self.detached = True

    container = ServiceContainer()
    player = Player()
    container.music_player = player
    register_cleanup_resources(container)
    await container.shutdown()
    assert player.stop_calls == 1
    assert player.detached
    assert container.music_player is None
    assert not container.resource_pool._resources
    await container.shutdown()
    assert player.stop_calls == 1
