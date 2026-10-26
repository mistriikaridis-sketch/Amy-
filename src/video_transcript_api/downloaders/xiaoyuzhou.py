import json
import os
import re
import time
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .base import BaseDownloader
from .models import VideoMetadata, DownloadInfo
from ..errors import InvalidURLError
from ..utils.logging import setup_logger

logger = setup_logger("xiaoyuzhou_downloader")

_EPISODE_RE = re.compile(r"/episode/([a-f0-9]+)", re.IGNORECASE)
_PODCAST_RE = re.compile(r"/podcast/([a-f0-9]+)", re.IGNORECASE)
_AUDIO_URL_RE = re.compile(
    r"https://[^\"'\\s>]+\.(?:m4a|mp3|aac|ogg|wav)(?:\?[^\"'\\s>]*)?",
    re.IGNORECASE,
)
_PAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".aac"}


class XiaoyuzhouDownloader(BaseDownloader):
    """Xiaoyuzhou (小宇宙) podcast episode downloader."""

    def __init__(self):
        super().__init__()
        self._cached_video_info: dict[str, dict] = {}
        self._page_cache: dict[str, str] = {}

    def can_handle(self, url):
        return "xiaoyuzhoufm.com" in (url or "")

    def _extract_episode_id(self, url):
        """Return episode id; podcast show pages resolve to latest episode."""
        match = _EPISODE_RE.search(url or "")
        if match:
            episode_id = match.group(1)
            logger.info(f"从URL中提取到小宇宙播客剧集ID: {episode_id}")
            return episode_id

        podcast_match = _PODCAST_RE.search(url or "")
        if podcast_match:
            pid = podcast_match.group(1)
            logger.info(f"检测到小宇宙节目页 pid={pid}，尝试解析最新单集")
            episode_id = self._resolve_podcast_latest_eid(url, pid)
            logger.info(f"节目页已解析为最新单集 eid={episode_id}")
            return episode_id

        logger.error(f"无法从URL中提取小宇宙播客剧集ID: {url}")
        raise InvalidURLError(
            "小宇宙请使用单集链接（https://www.xiaoyuzhoufm.com/episode/…）；"
            f"无法识别的链接: {url}"
        )

    def extract_video_id(self, url):
        return self._extract_episode_id(url)

    def _fetch_page_html(self, url: str, max_retries: int = 3) -> str:
        if url in self._page_cache:
            return self._page_cache[url]

        last_error: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"访问小宇宙页面 (attempt {attempt}/{max_retries}): {url}")
                response = requests.get(
                    url,
                    headers=_PAGE_HEADERS,
                    timeout=(10, 30),
                )
                response.raise_for_status()
                response.encoding = response.apparent_encoding or "utf-8"
                html = response.text
                if not html or len(html) < 200:
                    raise ValueError("empty or truncated Xiaoyuzhou page")
                self._page_cache[url] = html
                return html
            except Exception as exc:
                last_error = exc
                logger.warning(f"小宇宙页面抓取失败 attempt={attempt}: {exc}")
                if attempt < max_retries:
                    time.sleep(min(2 ** (attempt - 1), 4))

        raise InvalidURLError(
            f"无法打开小宇宙页面（网络或站点异常）: {url} ({last_error})"
        )

    def _parse_next_data(self, html: str) -> Optional[dict]:
        soup = BeautifulSoup(html, "html.parser")
        node = soup.find("script", id="__NEXT_DATA__")
        if not node or not node.string:
            return None
        try:
            return json.loads(node.string)
        except Exception as exc:
            logger.warning(f"解析 __NEXT_DATA__ 失败: {exc}")
            return None

    def _resolve_podcast_latest_eid(self, url: str, pid: str) -> str:
        html = self._fetch_page_html(url)
        next_data = self._parse_next_data(html)
        episode = self._latest_episode_from_next(next_data, pid)
        if episode and episode.get("eid"):
            # Prefetch episode payload into cache via episode URL shape
            eid = str(episode["eid"])
            episode_url = f"https://www.xiaoyuzhoufm.com/episode/{eid}"
            # Build and cache video info immediately to avoid a second round-trip
            info = self._info_from_episode_payload(episode, eid)
            if info.get("download_url"):
                self._cached_video_info[eid] = info
            return eid

        # Fallback: first /episode/ link on the page
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            m = _EPISODE_RE.search(anchor["href"])
            if m:
                return m.group(1)

        raise InvalidURLError(
            "小宇宙节目页未找到可转录的单集，请打开节目内某一期，"
            f"复制带 /episode/ 的链接后再提交: {url}"
        )

    @staticmethod
    def _latest_episode_from_next(next_data: Optional[dict], pid: str) -> Optional[dict]:
        if not isinstance(next_data, dict):
            return None
        podcast = (
            next_data.get("props", {})
            .get("pageProps", {})
            .get("podcast")
        )
        if not isinstance(podcast, dict):
            return None
        episodes = podcast.get("episodes") or []
        if not isinstance(episodes, list) or not episodes:
            return None
        # Prefer matching pid when present; otherwise first item (newest)
        for ep in episodes:
            if isinstance(ep, dict) and str(ep.get("pid") or "") == pid:
                return ep
        first = episodes[0]
        return first if isinstance(first, dict) else None

    def _info_from_episode_payload(self, episode: dict, eid: str) -> dict:
        title = (episode.get("title") or episode.get("name") or f"xiaoyuzhou_{eid}").strip()
        podcast = episode.get("podcast") if isinstance(episode.get("podcast"), dict) else {}
        author = (
            (podcast.get("title") or podcast.get("author") or episode.get("author") or "未知作者")
        )
        if isinstance(author, dict):
            author = author.get("name") or "未知作者"
        author = str(author).strip() or "未知作者"
        description = str(episode.get("description") or episode.get("shownotes") or "").strip()

        audio_url = self._audio_from_episode_payload(episode)
        audio_ext = self._detect_audio_ext(audio_url) if audio_url else ".m4a"
        filename = f"xiaoyuzhou_{eid}_{int(time.time())}{audio_ext}"
        return {
            "video_id": eid,
            "video_title": title,
            "author": author,
            "description": description,
            "download_url": audio_url,
            "filename": filename,
            "platform": "xiaoyuzhou",
        }

    @staticmethod
    def _audio_from_episode_payload(episode: dict) -> Optional[str]:
        media = episode.get("media") if isinstance(episode.get("media"), dict) else {}
        source = media.get("source") if isinstance(media.get("source"), dict) else {}
        for candidate in (
            source.get("url"),
            media.get("url"),
            (episode.get("enclosure") or {}).get("url")
            if isinstance(episode.get("enclosure"), dict)
            else None,
            episode.get("mediaUrl"),
            episode.get("audioUrl"),
        ):
            if isinstance(candidate, str) and candidate.startswith("http"):
                return candidate
        return None

    def get_video_info(self, url):
        try:
            episode_id = self._extract_episode_id(url)
            if episode_id in self._cached_video_info:
                logger.debug(f"[实例缓存命中] 使用缓存的视频信息: {episode_id}")
                cached = self._cached_video_info[episode_id]
                if cached.get("download_url"):
                    return cached

            # If the input was a podcast URL, resolution may have already cached info.
            episode_url = (
                url
                if _EPISODE_RE.search(url or "")
                else f"https://www.xiaoyuzhoufm.com/episode/{episode_id}"
            )
            html = self._fetch_page_html(episode_url)
            info = self._parse_episode_html(html, episode_id, episode_url)
            if not info.get("download_url"):
                raise InvalidURLError(
                    f"无法从页面中提取音频下载地址: {episode_url}"
                )
            self._cached_video_info[episode_id] = info
            logger.info(f"成功获取小宇宙播客信息: ID={episode_id}")
            return info
        except InvalidURLError:
            raise
        except Exception as e:
            logger.exception(f"获取小宇宙播客信息异常: {str(e)}")
            raise InvalidURLError(f"无法获取小宇宙下载信息: {url} ({e})") from e

    def _parse_episode_html(self, html: str, episode_id: str, url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        video_title, author = self._parse_title_author(soup, episode_id)
        description = self._parse_description(soup)
        audio_url = self._extract_audio_url(soup, html, episode_id)
        audio_ext = self._detect_audio_ext(audio_url) if audio_url else ".m4a"
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", video_title)
        filename = f"xiaoyuzhou_{episode_id}_{int(time.time())}{audio_ext}"
        return {
            "video_id": episode_id,
            "video_title": video_title or safe_title,
            "author": author,
            "description": description,
            "download_url": audio_url,
            "filename": filename,
            "platform": "xiaoyuzhou",
        }

    def _parse_title_author(self, soup: BeautifulSoup, episode_id: str) -> tuple[str, str]:
        video_title = None
        author = "未知作者"
        title_tag = soup.find("title")
        if title_tag:
            full_title = title_tag.get_text().strip()
            logger.info(f"完整标题: {full_title}")
            xiaoyuzhou_index = full_title.rfind("| 小宇宙")
            if xiaoyuzhou_index != -1:
                before = full_title[:xiaoyuzhou_index].strip()
                last_dash = before.rfind(" - ")
                if last_dash != -1:
                    video_title = before[:last_dash].strip()
                    author = before[last_dash + 3 :].strip() or author
                else:
                    video_title = before
            else:
                og_title = soup.find("meta", {"property": "og:title"})
                if og_title:
                    video_title = (og_title.get("content") or "").strip()
                if not video_title:
                    video_title = re.sub(r"\s*-\s*.*小宇宙.*$", "", full_title).strip()

        if not video_title:
            video_title = f"xiaoyuzhou_{episode_id}"
            logger.warning(f"未找到播客标题，使用ID作为标题: {video_title}")
        return video_title, author

    def _parse_description(self, soup: BeautifulSoup) -> str:
        script_tag = soup.find(
            "script", {"name": "schema:podcast-show", "type": "application/ld+json"}
        )
        if script_tag and script_tag.string:
            try:
                schema_data = json.loads(script_tag.string)
                description = (schema_data.get("description") or "").strip()
                if description:
                    return description
            except Exception as exc:
                logger.warning(f"解析schema:podcast-show失败: {exc}")

        for attrs in ({"name": "description"}, {"property": "og:description"}):
            meta = soup.find("meta", attrs)
            if meta and meta.get("content"):
                return meta.get("content", "").strip()
        return ""

    def _extract_audio_url(self, soup: BeautifulSoup, html: str, episode_id: str) -> Optional[str]:
        og_audio = soup.find("meta", {"property": "og:audio"})
        if og_audio and og_audio.get("content"):
            logger.info(f"从 og:audio 提取音频: {og_audio.get('content')[:80]}...")
            return og_audio.get("content")

        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except Exception:
                continue
            url = self._audio_from_ldjson(data)
            if url:
                logger.info(f"从 ld+json 提取音频: {url[:80]}...")
                return url

        next_data = self._parse_next_data(html)
        if next_data:
            episode = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("episode")
            )
            if isinstance(episode, dict):
                url = self._audio_from_episode_payload(episode)
                if url:
                    logger.info(f"从 __NEXT_DATA__.episode 提取音频: {url[:80]}...")
                    return url
            # Some payloads nest episode under podcast.episodes
            podcast = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("podcast")
            )
            if isinstance(podcast, dict):
                for ep in podcast.get("episodes") or []:
                    if isinstance(ep, dict) and str(ep.get("eid")) == episode_id:
                        url = self._audio_from_episode_payload(ep)
                        if url:
                            logger.info(
                                f"从 __NEXT_DATA__.podcast.episodes 提取音频: {url[:80]}..."
                            )
                            return url

        matches = _AUDIO_URL_RE.findall(html)
        # Prefer media.xyzcdn.net hosts
        for url in matches:
            host = urlparse(url).netloc
            if "xyzcdn" in host or "xiaoyuzhou" in host:
                logger.info(f"从页面正则提取音频: {url[:80]}...")
                return url
        if matches:
            logger.info(f"从页面正则提取音频(通用): {matches[0][:80]}...")
            return matches[0]

        logger.error(f"无法从页面中提取音频下载地址: episode={episode_id}")
        return None

    def _audio_from_ldjson(self, data: Any) -> Optional[str]:
        if isinstance(data, list):
            for item in data:
                url = self._audio_from_ldjson(item)
                if url:
                    return url
            return None
        if not isinstance(data, dict):
            return None

        associated = data.get("associatedMedia")
        if isinstance(associated, dict):
            content = associated.get("contentUrl") or associated.get("url")
            if isinstance(content, str) and content.startswith("http"):
                return content
        elif isinstance(associated, list):
            for item in associated:
                if isinstance(item, dict):
                    content = item.get("contentUrl") or item.get("url")
                    if isinstance(content, str) and content.startswith("http"):
                        return content

        for key in ("contentUrl", "audio", "url"):
            val = data.get(key)
            if isinstance(val, str) and val.startswith("http") and re.search(
                r"\.(m4a|mp3|aac|ogg|wav)(\?|$)", val, re.I
            ):
                return val
        return None

    @staticmethod
    def _detect_audio_ext(audio_url: str) -> str:
        audio_ext = ".m4a"
        audio_path = (audio_url or "").split("?")[0]
        if "." in audio_path.split("/")[-1]:
            detected = os.path.splitext(audio_path.split("/")[-1])[1].lower()
            if detected in _AUDIO_EXTS:
                audio_ext = detected
                logger.info(f"从音频URL检测到扩展名: {audio_ext}")
        return audio_ext

    def get_subtitle(self, url):
        return None

    def _fetch_metadata(self, url: str, video_id: str) -> VideoMetadata:
        info = self.get_video_info(url)
        return VideoMetadata(
            video_id=info.get("video_id", video_id),
            platform=info.get("platform", "xiaoyuzhou"),
            title=info.get("video_title", ""),
            author=info.get("author", ""),
            description=info.get("description", ""),
        )

    def _fetch_download_info(self, url: str, video_id: str) -> DownloadInfo:
        info = self.get_video_info(url)
        filename = info.get("filename")
        file_ext = None
        if filename and "." in filename:
            file_ext = filename.rsplit(".", 1)[-1]
        download_url = info.get("download_url")
        if not download_url:
            raise InvalidURLError(f"无法获取小宇宙音频地址: {url}")
        return DownloadInfo(
            download_url=download_url,
            file_ext=file_ext,
            filename=filename,
        )
