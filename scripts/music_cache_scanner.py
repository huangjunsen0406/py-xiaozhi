#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音乐缓存扫描器 扫描cache/music目录中的音乐文件，提取元数据，生成本地歌单.

依赖安装: pip install mutagen
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3NoHeaderError
except ImportError:
    print("错误: 需要安装 mutagen 库")
    print("请运行: pip install mutagen")
    sys.exit(1)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


class MusicMetadata:
    """
    音乐元数据类.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.filename = file_path.name
        self.file_id = file_path.stem  # 文件名去掉扩展名，即歌曲ID
        self.file_size = file_path.stat().st_size
        self.creation_time = datetime.fromtimestamp(file_path.stat().st_ctime)
        self.modification_time = datetime.fromtimestamp(file_path.stat().st_mtime)

        # 从文件提取的元数据
        self.title = None
        self.artist = None
        self.album = None
        self.genre = None
        self.year = None
        self.duration = None  # 秒数
        self.bitrate = None
        self.sample_rate = None

        # 文件哈希（用于去重）
        self.file_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """
        计算文件MD5哈希值（仅前1MB避免大文件计算过慢）
        """
        try:
            hash_md5 = hashlib.md5()
            with open(self.file_path, "rb") as f:
                # 只读取前1MB计算哈希
                chunk = f.read(1024 * 1024)
                hash_md5.update(chunk)
            return hash_md5.hexdigest()[:16]  # 取前16位
        except Exception:
            return "unknown"

    def extract_metadata(self) -> bool:
        """
        提取音乐文件元数据.
        """
        try:
            audio_file = MutagenFile(self.file_path)
            if audio_file is None:
                return False

            # 基本信息
            if hasattr(audio_file, "info"):
                self.duration = getattr(audio_file.info, "length", None)
                self.bitrate = getattr(audio_file.info, "bitrate", None)
                self.sample_rate = getattr(audio_file.info, "sample_rate", None)

            # ID3标签信息
            tags = audio_file.tags if audio_file.tags else {}

            # 标题
            self.title = self._get_tag_value(tags, ["TIT2", "TITLE", "\xa9nam"])

            # 艺术家
            self.artist = self._get_tag_value(tags, ["TPE1", "ARTIST", "\xa9ART"])

            # 专辑
            self.album = self._get_tag_value(tags, ["TALB", "ALBUM", "\xa9alb"])

            # 流派
            self.genre = self._get_tag_value(tags, ["TCON", "GENRE", "\xa9gen"])

            # 年份
            year_raw = self._get_tag_value(tags, ["TDRC", "DATE", "YEAR", "\xa9day"])
            if year_raw:
                # 提取年份数字
                year_str = str(year_raw)
                if year_str.isdigit():
                    self.year = int(year_str)
                else:
                    # 尝试从日期字符串中提取年份
                    import re

                    year_match = re.search(r"(\d{4})", year_str)
                    if year_match:
                        self.year = int(year_match.group(1))

            return True

        except ID3NoHeaderError:
            # 没有ID3标签，不是错误
            return True
        except Exception as e:
            print(f"提取元数据失败 {self.filename}: {e}")
            return False

    def _get_tag_value(self, tags: dict, tag_names: List[str]) -> Optional[str]:
        """
        从多个可能的标签名中获取值.
        """
        for tag_name in tag_names:
            if tag_name in tags:
                value = tags[tag_name]
                if isinstance(value, list) and value:
                    return str(value[0])
                elif value:
                    return str(value)
        return None

    def format_duration(self) -> str:
        """
        格式化播放时长.
        """
        if self.duration is None:
            return "未知"

        minutes = int(self.duration) // 60
        seconds = int(self.duration) % 60
        return f"{minutes:02d}:{seconds:02d}"

    def format_file_size(self) -> str:
        """
        格式化文件大小.
        """
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def to_dict(self) -> Dict:
        """
        转换为字典格式.
        """
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "genre": self.genre,
            "year": self.year,
            "duration": self.duration,
            "duration_formatted": self.format_duration(),
            "bitrate": self.bitrate,
            "sample_rate": self.sample_rate,
            "file_size": self.file_size,
            "file_size_formatted": self.format_file_size(),
            "file_hash": self.file_hash,
            "creation_time": self.creation_time.isoformat(),
            "modification_time": self.modification_time.isoformat(),
        }


class MusicCacheScanner:
    """
    音乐缓存扫描器.
    """

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or PROJECT_ROOT / "cache" / "music"
        self.playlist: List[MusicMetadata] = []
        self.scan_stats = {
            "total_files": 0,
            "success_count": 0,
            "error_count": 0,
            "total_duration": 0,
            "total_size": 0,
        }

    def scan_cache(self) -> bool:
        """
        扫描缓存目录.
        """
        print(f"🎵 开始扫描音乐缓存目录: {self.cache_dir}")

        if not self.cache_dir.exists():
            print(f"❌ 缓存目录不存在: {self.cache_dir}")
            return False

        # 查找所有音乐文件
        music_files = []
        for pattern in ["*.mp3", "*.m4a", "*.flac", "*.wav", "*.ogg"]:
            music_files.extend(self.cache_dir.glob(pattern))

        if not music_files:
            print("📁 缓存目录中没有找到音乐文件")
            return False

        self.scan_stats["total_files"] = len(music_files)
        print(f"📊 找到 {len(music_files)} 个音乐文件")

        # 扫描每个文件
        for i, file_path in enumerate(music_files, 1):
            print(f"🔍 [{i}/{len(music_files)}] 扫描: {file_path.name}")

            try:
                metadata = MusicMetadata(file_path)

                if metadata.extract_metadata():
                    self.playlist.append(metadata)
                    self.scan_stats["success_count"] += 1

                    # 累计统计
                    if metadata.duration:
                        self.scan_stats["total_duration"] += metadata.duration
                    self.scan_stats["total_size"] += metadata.file_size

                    # 显示基本信息
                    display_title = metadata.title or "未知标题"
                    display_artist = metadata.artist or "未知艺术家"
                    print(
                        f"   ✅ {display_title} - {display_artist} ({metadata.format_duration()})"
                    )
                else:
                    self.scan_stats["error_count"] += 1
                    print("   ❌ 元数据提取失败")

            except Exception as e:
                self.scan_stats["error_count"] += 1
                print(f"   ❌ 处理失败: {e}")

        return True

    def remove_duplicates(self):
        """
        移除重复的音乐文件（基于哈希值）
        """
        seen_hashes = set()
        unique_playlist = []
        duplicates = []

        for metadata in self.playlist:
            if metadata.file_hash in seen_hashes:
                duplicates.append(metadata)
            else:
                seen_hashes.add(metadata.file_hash)
                unique_playlist.append(metadata)

        if duplicates:
            print(f"🔄 发现 {len(duplicates)} 个重复文件:")
            for dup in duplicates:
                print(f"   - {dup.filename}")

        self.playlist = unique_playlist

    def sort_playlist(self, sort_by: str = "artist"):
        """
        排序歌单.
        """
        sort_functions = {
            "artist": lambda x: (
                x.artist or "Unknown",
                x.album or "Unknown",
                x.title or "Unknown",
            ),
            "title": lambda x: x.title or "Unknown",
            "album": lambda x: (x.album or "Unknown", x.artist or "Unknown"),
            "duration": lambda x: x.duration or 0,
            "file_size": lambda x: x.file_size,
            "creation_time": lambda x: x.creation_time,
        }

        if sort_by in sort_functions:
            self.playlist.sort(key=sort_functions[sort_by])
            print(f"📋 歌单已按 {sort_by} 排序")

    def print_statistics(self):
        """
        打印扫描统计信息.
        """
        stats = self.scan_stats
        print("\n📊 扫描统计:")
        print(f"   总文件数: {stats['total_files']}")
        print(f"   成功处理: {stats['success_count']}")
        print(f"   处理失败: {stats['error_count']}")
        print(f"   成功率: {stats['success_count']/stats['total_files']*100:.1f}%")

        # 总时长
        total_hours = stats["total_duration"] // 3600
        total_minutes = (stats["total_duration"] % 3600) // 60
        print(f"   总播放时长: {total_hours}小时{total_minutes}分钟")

        # 总大小
        total_size_mb = stats["total_size"] / (1024 * 1024)
        print(f"   总文件大小: {total_size_mb:.1f} MB")

        # 平均信息
        if stats["success_count"] > 0:
            avg_duration = stats["total_duration"] / stats["success_count"]
            avg_size = stats["total_size"] / stats["success_count"]
            print(f"   平均时长: {int(avg_duration//60)}:{int(avg_duration%60):02d}")
            print(f"   平均大小: {avg_size/(1024*1024):.1f} MB")

    def print_playlist(self, limit: int = None):
        """
        打印歌单.
        """
        print(f"\n🎵 本地音乐歌单 (共 {len(self.playlist)} 首)")
        print("=" * 80)

        for i, metadata in enumerate(
            self.playlist[:limit] if limit else self.playlist, 1
        ):
            title = metadata.title or "未知标题"
            artist = metadata.artist or "未知艺术家"
            album = metadata.album or "未知专辑"
            duration = metadata.format_duration()

            print(f"{i:3d}. {title}")
            print(f"     艺术家: {artist}")
            print(f"     专辑: {album}")
            print(f"     时长: {duration} | 文件ID: {metadata.file_id}")
            print()

        if limit and len(self.playlist) > limit:
            print(f"... 还有 {len(self.playlist) - limit} 首歌曲")

    def export_playlist(self, output_file: Path = None, format: str = "json"):
        """
        导出歌单.
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = PROJECT_ROOT / f"local_playlist_{timestamp}.{format}"

        try:
            if format == "json":
                playlist_data = {
                    "metadata": {
                        "generated_at": datetime.now().isoformat(),
                        "cache_directory": str(self.cache_dir),
                        "total_songs": len(self.playlist),
                        "statistics": self.scan_stats,
                    },
                    "playlist": [metadata.to_dict() for metadata in self.playlist],
                }

                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(playlist_data, f, ensure_ascii=False, indent=2)

            elif format == "m3u":
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    for metadata in self.playlist:
                        title = metadata.title or metadata.filename
                        artist = metadata.artist or "Unknown Artist"
                        duration = int(metadata.duration) if metadata.duration else -1

                        f.write(f"#EXTINF:{duration},{artist} - {title}\n")
                        f.write(f"{metadata.file_path}\n")

            print(f"📄 歌单已导出到: {output_file}")
            return output_file

        except Exception as e:
            print(f"❌ 导出失败: {e}")
            return None

    def search_songs(self, query: str) -> List[MusicMetadata]:
        """
        搜索歌曲.
        """
        query = query.lower()
        results = []

        for metadata in self.playlist:
            # 在标题、艺术家、专辑中搜索
            searchable_text = " ".join(
                filter(
                    None,
                    [
                        metadata.title,
                        metadata.artist,
                        metadata.album,
                        metadata.filename,
                    ],
                )
            ).lower()

            if query in searchable_text:
                results.append(metadata)

        return results

    def get_artists(self) -> Dict[str, List[MusicMetadata]]:
        """
        按艺术家分组.
        """
        artists = {}
        for metadata in self.playlist:
            artist = metadata.artist or "未知艺术家"
            if artist not in artists:
                artists[artist] = []
            artists[artist].append(metadata)
        return artists

    def get_albums(self) -> Dict[str, List[MusicMetadata]]:
        """
        按专辑分组.
        """
        albums = {}
        for metadata in self.playlist:
            album_key = (
                f"{metadata.album or '未知专辑'} - {metadata.artist or '未知艺术家'}"
            )
            if album_key not in albums:
                albums[album_key] = []
            albums[album_key].append(metadata)
        return albums


def main():
    """
    主函数.
    """
    print("🎵 音乐缓存扫描器")
    print("=" * 50)

    # 创建扫描器
    scanner = MusicCacheScanner()

    # 扫描缓存
    if not scanner.scan_cache():
        return

    # 移除重复文件
    scanner.remove_duplicates()

    # 排序歌单
    scanner.sort_playlist("artist")

    # 显示统计信息
    scanner.print_statistics()

    # 显示歌单（限制前20首）
    scanner.print_playlist(limit=20)

    # 交互菜单
    while True:
        print("\n" + "=" * 50)
        print("选择操作:")
        print("1. 显示完整歌单")
        print("2. 按艺术家分组显示")
        print("3. 按专辑分组显示")
        print("4. 搜索歌曲")
        print("5. 导出歌单 (JSON)")
        print("6. 导出歌单 (M3U)")
        print("7. 重新排序")
        print("0. 退出")

        choice = input("\n请选择 (0-7): ").strip()

        if choice == "0":
            break
        elif choice == "1":
            scanner.print_playlist()
        elif choice == "2":
            artists = scanner.get_artists()
            for artist, songs in artists.items():
                print(f"\n🎤 {artist} ({len(songs)} 首)")
                for song in songs:
                    title = song.title or song.filename
                    print(f"   - {title} ({song.format_duration()})")
        elif choice == "3":
            albums = scanner.get_albums()
            for album, songs in albums.items():
                print(f"\n💿 {album} ({len(songs)} 首)")
                for song in songs:
                    title = song.title or song.filename
                    print(f"   - {title} ({song.format_duration()})")
        elif choice == "4":
            query = input("请输入搜索关键词: ").strip()
            if query:
                results = scanner.search_songs(query)
                if results:
                    print(f"\n🔍 找到 {len(results)} 首歌曲:")
                    for i, song in enumerate(results, 1):
                        title = song.title or song.filename
                        artist = song.artist or "未知艺术家"
                        print(f"   {i}. {title} - {artist} ({song.format_duration()})")
                else:
                    print("🔍 没有找到匹配的歌曲")
        elif choice == "5":
            scanner.export_playlist(format="json")
        elif choice == "6":
            scanner.export_playlist(format="m3u")
        elif choice == "7":
            print("排序选项:")
            print("1. 按艺术家")
            print("2. 按标题")
            print("3. 按专辑")
            print("4. 按时长")
            print("5. 按文件大小")
            print("6. 按创建时间")

            sort_choice = input("请选择排序方式 (1-6): ").strip()
            sort_map = {
                "1": "artist",
                "2": "title",
                "3": "album",
                "4": "duration",
                "5": "file_size",
                "6": "creation_time",
            }

            if sort_choice in sort_map:
                scanner.sort_playlist(sort_map[sort_choice])
                print("✅ 排序完成")
        else:
            print("❌ 无效选择")

    print("\n👋 再见!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，退出程序")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback

        traceback.print_exc()
