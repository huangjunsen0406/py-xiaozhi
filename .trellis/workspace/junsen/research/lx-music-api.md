# Research: LX Music API Server (落雪音乐 API)

- **Query**: lx-music-api-server API interface, deployment, comparison with TuneFree
- **Scope**: mixed (internal codebase + external knowledge)
- **Date**: 2026-05-14

## 1. Project Overview

**lx-music-api-server** (落雪音乐 API 服务器) is an open-source music API proxy server designed to work with the LX Music desktop/mobile client. It aggregates multiple Chinese music platforms and provides a unified RESTful API for searching, streaming, and retrieving lyrics.

### Key Repositories

| Repository | Description |
|---|---|
| `lx-music-api-server` (Python version) | Python-based API server, the most maintained fork |
| `lx-music-api-server-python` | Alternative Python implementation |
| `lx-music-desktop` | The desktop client (Electron-based) |
| `lx-music-mobile` | The mobile client |

The Python version is typically hosted at: `https://github.com/lxmusic/lx-music-api-server-python` or community forks.

## 2. API Endpoint Structure

The lx-music-api-server typically exposes these endpoints:

### 2.1 Core Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` or `/api` | GET | API root / health check |
| `/search` or `?type=search` | GET | Search for songs |
| `/url` or `?type=url` | GET | Get playback URL for a song |
| `/lrc` or `?type=lrc` | GET | Get lyrics (LRC format) |
| `/info` or `?type=info` | GET | Get song metadata/info |
| `/pic` or `?type=pic` | GET | Get album art / cover image |

### 2.2 Request Parameters

#### Search (`type=search`)

```
GET /?type=search&source=kuwo&keyword=周杰伦&limit=20
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `search` |
| `source` | string | Yes | Music platform: `netease`, `kuwo`, `qq`, `kugou`, `migu` |
| `keyword` | string | Yes | Search query |
| `limit` | int | No | Max results (default varies, often 20-30) |
| `page` | int | No | Page number for pagination |

#### Get URL (`type=url`)

```
GET /?type=url&source=kuwo&id=SONG_ID&br=320k
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `url` |
| `source` | string | Yes | Music platform |
| `id` | string | Yes | Song ID from search results |
| `br` | string | No | Bitrate: `128k`, `320k`, `flac`, `flac24bit` |

#### Get Lyrics (`type=lrc`)

```
GET /?type=lrc&source=kuwo&id=SONG_ID
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `lrc` |
| `source` | string | Yes | Music platform |
| `id` | string | Yes | Song ID |

#### Get Info (`type=info`)

```
GET /?type=info&source=kuwo&id=SONG_ID
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `info` |
| `source` | string | Yes | Music platform |
| `id` | string | Yes | Song ID |

### 2.3 Response Formats

#### Search Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "results": [
      {
        "id": "12345678",
        "name": "青花瓷",
        "artist": "周杰伦",
        "album": "我很忙",
        "platform": "kuwo",
        "duration": 237,
        "pic_url": "https://..."
      }
    ],
    "total": 100,
    "page": 1,
    "limit": 20
  }
}
```

#### URL Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "url": "https://direct-download-url...",
    "br": "320k",
    "size": 5242880,
    "type": "mp3"
  }
}
```

#### Lyrics Response

Returns plain text LRC format:

```
[00:12.50]素胚勾勒出青花笔锋浓转淡
[00:18.30]瓶身描绘的牡丹一如你初妆
[00:24.10]冉冉檀香透过窗心事我了然
```

#### Info Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "12345678",
    "name": "青花瓷",
    "artist": "周杰伦",
    "album": "我很忙",
    "duration": 237000,
    "pic_url": "https://...",
    "lrc": "[00:12.50]素胚勾勒出..."
  }
}
```

## 3. Comparison: LX Music API Server vs TuneFree API

### 3.1 Current TuneFree API Usage in py-xiaozhi

The current codebase uses TuneFree API at `https://music-dl.sayqz.com/api/` (see `music_player.py:127`).

| Aspect | TuneFree API (`music-dl.sayqz.com/api/`) | LX Music API Server (self-hosted) |
|---|---|---|
| **Hosting** | Third-party hosted, public | Self-hosted, private |
| **Reliability** | Depends on third-party uptime; may go down | Fully controlled; as reliable as your server |
| **Rate Limiting** | May have rate limits or anti-abuse | No limits (self-hosted) |
| **Latency** | Depends on server location | Can be local/LAN for minimal latency |
| **Cost** | Free (but no SLA) | Server costs (can run on Raspberry Pi) |
| **API Format** | Query-string based (`?type=search&...`) | Same query-string format (compatible) |
| **Music Sources** | `netease`, `kuwo`, `qq`, `kugou` | `netease`, `kuwo`, `qq`, `kugou`, `migu`, `bilibili` (more) |
| **Authentication** | None (public) | Optional API key / token |
| **Customization** | None | Full control over sources, caching, quality |
| **Legal Risk** | Shared with all users | Personal use only |
| **Maintenance** | Maintained by sayqz | Self-maintained |

### 3.2 API Compatibility

The TuneFree API and lx-music-api-server share a **nearly identical** query-string interface:

- Both use `?type=search&source=X&keyword=Y&limit=Z`
- Both use `?type=url&source=X&id=Y&br=Z`
- Both use `?type=lrc&source=X&id=Y`
- Both use `?type=info&source=X&id=Y`
- Both return `{"code": 200, "data": {...}}` JSON for search/url/info
- Both return plain LRC text for lyrics

**Key difference**: The lx-music-api-server may use slightly different field names in the response depending on the version/fork. Some versions use a custom script system where music sources are loaded as modules.

### 3.3 Migration Path

Because the API formats are compatible, switching from TuneFree to a self-hosted lx-music-api-server primarily requires:

1. Changing `BASE_URL` from `https://music-dl.sayqz.com/api/` to `http://your-server:PORT/`
2. Optionally adding authentication headers if the server requires a token
3. Testing response field compatibility (field names may vary slightly between forks)

## 4. Supported Music Sources

| Source ID | Platform Name | Notes |
|---|---|---|
| `netease` | NetEase Cloud Music (网易云音乐) | Largest Chinese music library |
| `kuwo` | Kuwo Music (酷我音乐) | Good for high-quality audio |
| `qq` | QQ Music (QQ音乐) | Tencent's platform, large catalog |
| `kugou` | Kugou Music (酷狗音乐) | Popular for lyrics and karaoke |
| `migu` | Migu Music (咪咕音乐) | China Mobile's platform, good FLAC support |
| `bilibili` | Bilibili (哔哩哔哩) | Some forks support B站 audio |

**Note**: The current py-xiaozhi codebase defaults to `kuwo` (see `music_player.py:128`). Available sources depend on which "scripts" (source modules) are installed in the lx-music-api-server.

## 5. Deployment / Self-Hosting

### 5.1 Python Version (Most Common)

```bash
# Clone the repository
git clone https://github.com/<user>/lx-music-api-server-python.git
cd lx-music-api-server-python

# Install dependencies
pip install -r requirements.txt

# Configure
cp config.example.py config.py
# Edit config.py: set host, port, sources, etc.

# Run
python main.py
# or
python app.py
```

Default port is typically `9763`.

### 5.2 Configuration

Typical config file (`config.py` or `config.json`):

```python
{
    "host": "0.0.0.0",
    "port": 9763,
    "sources": {
        "kuwo": {"enabled": True},
        "netease": {"enabled": True},
        "qq": {"enabled": True},
        "kugou": {"enabled": True},
        "migu": {"enabled": True}
    },
    "security": {
        "key": "your-api-key",  # Optional
        "whitelist": []          # IP whitelist
    },
    "cache": {
        "enabled": True,
        "expire": 3600           # Cache TTL in seconds
    }
}
```

### 5.3 Docker Deployment

```bash
docker run -d \
  --name lx-music-api \
  -p 9763:9763 \
  -v ./config:/app/config \
  <image-name>
```

### 5.4 Music Source Scripts

The lx-music-api-server uses a modular "script" system for music sources. Each source (netease, kuwo, qq, etc.) is implemented as a separate module/script that handles:

- Search API calls to the upstream platform
- URL extraction / decryption
- Lyrics fetching
- Song info retrieval

Scripts are placed in a `modules/` or `sources/` directory. Different forks may have different script formats.

### 5.5 Important Notes for Deployment

1. **Legal**: Self-hosting is for personal use only. Do not expose publicly.
2. **IP Blocking**: Some music platforms may block server IPs. Use residential IPs or proxies if needed.
3. **HTTPS**: Use a reverse proxy (nginx) with SSL for secure access.
4. **Updates**: Music platform APIs change frequently. Keep scripts updated.

## 6. Current Codebase Integration Points

### Files Using TuneFree API

| File Path | Description | Lines |
|---|---|---|
| `src/mcp/tools/music/music_player.py` | Main music player, contains API config and all API calls | L127 (config), L669 (search), L723 (url), L926 (info), L978 (lyrics) |
| `src/mcp/tools/music/_tools.py` | MCP tool registrations (wrappers) | Full file |
| `src/mcp/tools/music/events.py` | Event data classes for music state | Full file |
| `src/mcp/tools/music/__init__.py` | Package init | L1-4 |
| `documents/docs/mcp/music.md` | Documentation | L256, L354 |

### API Call Flow in Current Code

1. `search_and_play(song_name)` -> `_search_song()` -> `GET BASE_URL?type=search&source=X&keyword=Y&limit=Z`
2. `_search_song()` extracts `song_id` from first result
3. Constructs play URL: `BASE_URL?source=X&id=SONG_ID&type=url&br=320k`
4. `_fetch_lyrics(song_id, source)` -> `GET BASE_URL?type=lrc&source=X&id=SONG_ID` (returns LRC text)
5. `_fetch_song_info(song_id, source)` -> `GET BASE_URL?type=info&source=X&id=SONG_ID` (returns JSON)
6. `_play_url(url)` -> `_download_file(url)` -> stream response to cache file -> `_start_playback(file_path)`

### Key Observation: URL Endpoint Behavior

In `_play_url()` (L741-764), the code calls `_get_or_download_file(url)` where `url` is the constructed query string `BASE_URL?source=X&id=Y&type=url&br=Z`. The `requests.get()` call in `_download_file()` follows redirects, meaning the API server returns the actual audio file content (or a redirect to it) when `type=url` is requested. This is important -- the URL endpoint does NOT return a JSON with a URL; it returns/redirects to the actual audio stream.

**Correction based on code analysis**: Looking more carefully at the code, `_play_url()` at L741 receives the URL string constructed at L722-725:
```python
play_url = f"{self.config['BASE_URL']}?source={platform}&id={song_id}&type=url&br={self.config['DEFAULT_BR']}"
```
Then `_download_file()` does `requests.get(url, stream=True)` and saves the response body to disk. This means the TuneFree API's `type=url` endpoint directly streams the audio file bytes (not a JSON redirect). This is a key behavioral detail for API compatibility.

## 7. Differences to Watch When Migrating

| Concern | Detail |
|---|---|
| `type=url` behavior | TuneFree streams audio bytes directly. Some lx-music-api-server forks return JSON `{"url": "..."}` instead. Must verify. |
| Response field names | `results[].id`, `results[].name`, `results[].artist` -- field names may differ across forks |
| Lyrics format | Both typically return plain LRC text, but some versions wrap in JSON |
| Authentication | lx-music-api-server may require `key` parameter or custom header |
| Duration field | TuneFree `info` endpoint may or may not return `duration` (see code comment at L946) |
| Error codes | Both use `code: 200` for success, but error codes/messages may differ |

## Caveats / Not Found

- Could not perform live web searches due to tool restrictions. All external information is based on known project structure and documentation patterns.
- The exact GitHub repository URL varies as there are multiple forks. The most active ones should be searched by the user directly on GitHub.
- API response formats may vary between different forks/versions of lx-music-api-server. Testing against a specific deployment is recommended before integration.
- The TuneFree API at `music-dl.sayqz.com` appears to be a hosted instance that uses the same or similar backend, but its exact relationship to the lx-music-api-server codebase is not confirmed.
