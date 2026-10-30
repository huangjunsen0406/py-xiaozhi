"""Cancellation-safe waiting shared by the music resource owners."""

import asyncio


async def await_cleanup(future):
    """Finish owned cleanup despite repeated cancellation, then propagate it."""
    cancelled = False
    while not future.done():
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError:
            cancelled = True
    result = future.result()
    if cancelled:
        raise asyncio.CancelledError
    return result
