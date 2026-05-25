# Music Playback Tools

The music playback tool is a feature-rich MCP music player that supports online search and playback, local music management, lyrics display, and more.

### Common Use Cases

**Search and Play Online Music:**

- "Play Blue and White Porcelain by Jay Chou"
- "I want to listen to G.E.M.'s songs"
- "Play some light music"
- "Play the latest pop songs"

**Playback Control:**

- "Pause the music"
- "Resume playback"
- "Stop playback"
- "The music is halfway through"

**Local Music Management:**

- "View local music"
- "Play that local song"
- "Search for Jay Chou in local music"

**Playback Status Queries (AI answers based on internal state; no standalone tool yet):**

- "What song is currently playing"
- "How is the playback progress"
- "How much time is left on this song"

**Lyrics Features:**

- "Show lyrics"
- "What are the current lyrics"
- "Are there lyrics available"

**Advanced Features:**

- "Skip to 1 minute 30 seconds"
- "Fast forward to the chorus"
- "Go back to the beginning"

### Usage Tips

1. **Specify Song Information Clearly**: Providing song title, artist name, or album name helps with more accurate search
2. **Network Connection**: Online search and playback require a stable network connection
3. **Local Cache**: Played songs are automatically cached for faster playback next time
4. **Volume Control**: You can request to adjust volume or mute
5. **Lyrics Sync**: Supports real-time lyrics display to enhance the listening experience

The AI assistant will automatically invoke the music playback tool based on your needs, providing you with a smooth music experience.

## Feature Overview

### Online Music Features

- **Smart Search**: Supports searching by song title, artist, album, and more
- **High-Quality Playback**: Supports high-quality audio streaming
- **Lyrics Display**: Real-time synchronized lyrics display
- **Auto-Caching**: Played songs are automatically cached locally

### Local Music Management

- **Local Scanning**: Automatically scans local music files
- **Metadata Extraction**: Automatically extracts song title, artist, album, and other information
- **Format Support**: Supports MP3, M4A, FLAC, WAV, OGG, and other formats
- **Smart Search**: Quickly search within local music

### Playback Control Features

- **Basic Control**: Play, pause, stop
- **Progress Control**: Skip to a specified time position
- **Status Sync**: Synchronizes playback progress via control tool return values and event push
- **Error Handling**: Comprehensive error handling and recovery mechanisms

### User Experience Features

- **UI Integration**: Seamless integration with the application interface
- **Real-Time Feedback**: Real-time display of playback status and lyrics
- **Smart Caching**: Optimizes storage space usage
- **Background Playback**: Supports continuous background playback

## Tool List

### 1. Online Music Tool

#### music_player.search_and_play - Search and Play Online Music

Calls the online music API based on song title, artist, or keywords to download and play the target song. If currently playing, it will stop first before playing the new song.

**Parameters:**

- `song_name` (required): The song title, artist, or keywords to search for

**Use Cases:**

- Play a specific song
- Search for all or latest songs by an artist
- Let the AI recommend or play popular songs

### 2. Playback Control Tools

#### music_player.pause - Pause Playback

Pauses the current song and retains the current position. Suitable for manual pause or when the user actively requests pausing.

**Parameters:**
None

**Use Cases:**

- Pause current playback
- Coordinate with TTS playback for early manual pause
- Scenarios requiring temporary mute

#### music_player.resume - Resume Playback

Continues playback from the paused position. Only triggers after a manual pause to avoid conflict with automatic TTS pause.

**Parameters:**
None

**Use Cases:**

- User says "resume playback" or "continue playing"
- Manual resume required after automatic TTS pause
- Confirming that music has been manually paused

#### music_player.stop - Stop Playback

Ends the current song and resets the playback progress. This is a complete stop operation.

**Parameters:**
None

**Use Cases:**

- User explicitly requests "stop/close the music"
- Need to clear playback state when switching sessions or scenes
- Avoid background continuing playback

#### music_player.seek - Seek Playback Position

Skips to a specified second position in the song. Internally restarts the decoder to ensure playback synchronization.

**Parameters:**

- `position` (required): The seek position (in seconds, integer >= 0)

**Use Cases:**

- Fast forward to a specific time point
- Go back to the beginning or chorus of the song
- Navigate to a specific segment as requested by the user

### 3. Lyrics Tool

#### music_player.get_lyrics - Get Current Song Lyrics

Returns a list of lyrics text with timestamps. If no lyrics are available, a notification message is returned.

**Parameters:**
None

**Use Cases:**

- User wants to view or sing along with lyrics
- Display the currently playing line
- Check if lyrics are available

> Note: The player internally maintains playback progress, pause source, and other states, but MCP currently only exposes control tools and lyrics queries.

### 4. Local Music Tool

#### music_player.get_local_playlist - Get Local Cached Playlist

Scans the local cache directory and returns a list of downloaded songs. Each item in the result is in the format "Song Title - Artist" and can be passed back to `music_player.search_and_play` for playback.

**Parameters:**

- `force_refresh` (optional): Whether to force re-scan the cache directory, default false

**Use Cases:**

- View local cache contents
- Quickly initiate playback based on cached songs
- Debug or verify cache status

## Usage Examples

### Online Music Playback Examples

```python
# Search and play a song
result = await mcp_server.call_tool("music_player.search_and_play", {
    "song_name": "Jay Chou Blue and White Porcelain"
})

# Pause and resume
await mcp_server.call_tool("music_player.pause", {})
await mcp_server.call_tool("music_player.resume", {})

# Stop playback
await mcp_server.call_tool("music_player.stop", {})

# Seek to a specific position (in seconds)
await mcp_server.call_tool("music_player.seek", {
    "position": 90
})
```

### Local Music Management Examples

```python
# Get local music list
playlist = await mcp_server.call_tool("music_player.get_local_playlist", {
    "force_refresh": True
})

# Select a song from the local playlist and play again
if playlist.get("playlist"):
    first_song = playlist["playlist"][0].split(" - ")[0]
    await mcp_server.call_tool("music_player.search_and_play", {
        "song_name": first_song
    })
```

### Lyrics Query Example

```python
lyrics = await mcp_server.call_tool("music_player.get_lyrics", {})
```

> The current MCP interface does not yet expose a standalone status query tool. Playback progress-related questions rely on context and event callbacks maintained by the AI assistant.

## Technical Architecture

### Music Player Core

- **Singleton Pattern**: Provides a globally unique instance via `get_music_player_instance()`, avoiding concurrent creation of multiple players.
- **FFmpeg + AudioCodec**: Uses `MusicDecoder` (FFmpeg) to decode audio, then passes it through the unified `AudioCodec` playback pipeline, ensuring consistent sample rate and channel configuration.
- **Async Task Queue**: Decoded PCM data is passed to the playback loop through an `asyncio.Queue`, avoiding blocking the main thread.
- **Event-Driven Control**: Built-in EventBus subscribes to pause/resume events, allowing AI or system to achieve automatic yielding and recovery through events.

### Audio Processing

- **High-Precision Decoding**: `MusicDecoder` launches the FFmpeg decoder on demand, supporting mainstream formats such as MP3/M4A/FLAC/WAV/OGG.
- **Timeline Maintenance**: Obtains accurate duration via `ffprobe` + lyrics timestamps, and re-initializes the decoder during seeking/resuming.
- **PCM Normalization**: Decoded output is kept as float32 and unified to mono before writing to `AudioCodec`.
- **Lyrics Sync**: A dedicated lyrics task dynamically pushes lyrics events based on the current time, ensuring display synchronization.

### Online Service Integration

- **TuneFree API**: Uniformly accesses online search, playback links, lyrics, and song information via `https://music-dl.sayqz.com/api/`.
- **Multi-Platform Support**: `DEFAULT_SOURCE` can be configured for platforms like kuwo, netease, etc. `SEARCH_LIMIT` controls the number of search results.
- **High Bitrate Playback**: Default `DEFAULT_BR=320k`, can also switch to flac or other higher quality options.
- **Network Robustness**: Requests are wrapped with `asyncio.to_thread` + `requests`, with built-in timeout and error logging.

### Local Music Management

- **Cache Directory**: Automatically creates cache and temporary directories under `get_user_cache_dir()/music`.
- **Periodic Scanning**: Refreshes the cache index at least every 5 minutes; can force a scan via `force_refresh` when needed.
- **Metadata Extraction**: If Mutagen is installed, automatically reads title, artist, album, and duration.
- **Playback Reuse**: Downloaded songs in the cache are served directly from local files for replay, reducing network requests.

## Data Structures

### Search Playback Response

```python
{
    "status": "success",
    "message": "Now playing: Blue and White Porcelain - Jay Chou",
    "song": "Blue and White Porcelain - Jay Chou",
    "duration": "03:57",
    "total_seconds": 237.5
}
```

### Local Playlist Response

```python
{
    "status": "success",
    "message": "Found 12 local songs",
    "playlist": [
        "Blue and White Porcelain - Jay Chou",
        "Light Years Away - G.E.M."
    ],
    "total_count": 12
}
```

### Music Metadata (Internal Use)

```python
{
    "file_id": "song_123",
    "title": "Blue and White Porcelain",
    "artist": "Jay Chou",
    "album": "On the Run",
    "duration": "03:57",
    "file_size": 5242880,
    "format": "mp3"
}
```

### Lyrics Data

```python
{
    "status": "success",
    "lyrics": [
        "[00:12] The blue and white pattern is outlined with varying brush density",
        "[00:18] The peony on the vase is just like your first makeup",
        "[00:24] The sandalwood incense drifts through the window, I know what's on my mind"
    ]
}
```

## Configuration

### Audio Configuration

Audio playback related configuration:

```python
AudioConfig = {
    "OUTPUT_SAMPLE_RATE": 44100,
    "CHANNELS": 2,
    "BUFFER_SIZE": 1024
}
```

### Cache Configuration

Cache directory configuration:

```python
from src.utils.resource_finder import get_user_cache_dir

cache_dir = get_user_cache_dir() / "music"
temp_cache_dir = cache_dir / "temp"
```

### API Configuration

Online music service configuration:

```python
config = {
    "BASE_URL": "https://music-dl.sayqz.com/api/",
    "DEFAULT_SOURCE": "kuwo",
    "DEFAULT_BR": "320k",
    "SEARCH_LIMIT": 20,
    "HEADERS": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive"
    }
}
```

## Supported Audio Formats

### Playback Formats

- **MP3**: The most common audio format
- **M4A**: Apple audio format
- **FLAC**: Lossless audio format
- **WAV**: Uncompressed audio format
- **OGG**: Open-source audio format

### Metadata Support

- **ID3 v1/v2**: MP3 metadata standard
- **MP4**: M4A file metadata
- **Vorbis**: OGG file metadata
- **FLAC**: FLAC file metadata

## Best Practices

### 1. Search Optimization

- Use specific song titles and artist names
- Avoid overly vague keywords
- Include album names to increase accuracy

### 2. Cache Management

- Periodically clean up unnecessary cache files
- Monitor cache directory size
- Use forced refresh to get the latest music list

### 3. Network Optimization

- Ensure a stable network connection
- Prioritize local music when the network is poor
- Set appropriate timeout values

### 4. User Experience

- Provide clear playback status feedback
- Support fast-response control operations
- Gracefully handle playback errors

## Troubleshooting

### Common Issues

1. **Cannot Search for Songs**: Check network connection and API availability
2. **Playback Failed**: Check audio device and file format
3. **Lyrics Not Displaying**: Check lyrics service and song ID
4. **Local Music Not Showing**: Check file permissions and format support

### Debugging Methods

1. View log output for detailed error information
2. Test network connection and API response
3. Verify audio file integrity
4. Check cache directory permissions

### Performance Optimization

1. Set reasonable caching policies
2. Optimize network request frequency
3. Use async operations to avoid blocking
4. Periodically clean up temporary files

With the music playback tool, you can enjoy a rich music experience including online search, local playback, lyrics display, and more.
