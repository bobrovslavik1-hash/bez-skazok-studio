"""Что внутри материала: полный текст статьи, текст поста, расшифровка видео.

Студия достаёт это сама сразу после сбора, чтобы сценарист работал с настоящим текстом, а не с заголовком:
- сайт — открываем статью и вынимаем основной текст (без меню, рекламы и комментариев);
- Telegram — весь текст поста приходит прямо в ленте;
- YouTube — пробуем взять субтитры видео. YouTube часто не пускает серверы из дата-центров:
  тогда остаётся описание видео, а расшифровки подключим через посредника (Apify).
"""
import datetime as dt
import logging
import re
import time

import requests
import trafilatura

from . import db, feeds

log = logging.getLogger('studio.content')
MAX_CHARS = 40_000
KIND_LABEL = {'article': 'Полный текст статьи', 'post': 'Текст поста', 'transcript': 'Расшифровка видео',
              'description': 'Описание видео', 'feed': 'Текст из ленты'}
WHAT_WE_TAKE = {
    'rss': 'заголовки и полный текст статей',
    'telegram': 'текст постов, фото и видео',
    'youtube': 'названия и описания видео, расшифровка — если YouTube отдаёт',
}
YT_LANGS = ('ru', 'uk', 'en')
YT_PAUSE_HOURS = 6
_cols_ready = False


def ensure_columns() -> bool:
    """Колонки для текста в k_items (таблица конвейера): добавляются один раз, старые процессы их не замечают."""
    global _cols_ready
    if _cols_ready:
        return True
    if not db.table_exists('k_items'):
        return False
    db.x("""ALTER TABLE k_items ADD COLUMN IF NOT EXISTS content TEXT, ADD COLUMN IF NOT EXISTS content_kind TEXT,
            ADD COLUMN IF NOT EXISTS content_error TEXT, ADD COLUMN IF NOT EXISTS content_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS content_tries SMALLINT NOT NULL DEFAULT 0""")
    _cols_ready = True
    return True


# ---------- YouTube: можно ли брать расшифровки с нашего сервера ----------
def youtube_state() -> dict:
    return db.get_setting('youtube_transcripts', {'status': 'unknown'}) or {'status': 'unknown'}


def _yt_set(status: str, note: str = '') -> None:
    db.set_setting('youtube_transcripts', {'status': status, 'note': note[:300],
                                           'checked_at': dt.datetime.now(dt.timezone.utc).isoformat()})


def _yt_paused() -> bool:
    st = youtube_state()
    if st.get('status') != 'blocked' or not st.get('checked_at'):
        return False
    since = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(st['checked_at'])
    return since.total_seconds() < YT_PAUSE_HOURS * 3600


def video_id(url: str) -> str | None:
    m = re.search(r'(?:[?&]v=|/shorts/|/live/|youtu\.be/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else None


class Blocked(Exception):
    """YouTube не пускает наш сервер за расшифровками."""


def transcript(vid: str) -> str:
    """Субтитры видео (ручные или автоматические) → текст абзацами с отметками времени [мм:сс]."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (AgeRestricted, CouldNotRetrieveTranscript, IpBlocked, NoTranscriptFound,
                                                PoTokenRequired, RequestBlocked, TranscriptsDisabled, VideoUnavailable,
                                                VideoUnplayable)
    try:
        snippets = list(YouTubeTranscriptApi().fetch(vid, languages=YT_LANGS))
    except (RequestBlocked, IpBlocked, PoTokenRequired) as e:
        raise Blocked(type(e).__name__)
    except (TranscriptsDisabled, NoTranscriptFound):
        raise feeds.FeedError('у видео нет субтитров')
    except AgeRestricted:
        raise feeds.FeedError('видео с ограничением по возрасту')
    except (VideoUnavailable, VideoUnplayable):
        raise feeds.FeedError('видео недоступно')
    except CouldNotRetrieveTranscript as e:
        raise feeds.FeedError('не получилось взять субтитры: ' + type(e).__name__)
    except requests.RequestException as e:
        raise feeds.FeedError('нет связи с YouTube: ' + type(e).__name__)
    parts, buf, mark = [], [], None
    for sn in snippets:
        if mark is None:
            mark = sn.start
        buf.append(re.sub(r'\s+', ' ', sn.text).strip())
        if sn.start - mark >= 30:
            parts.append(f'[{int(mark // 60):02d}:{int(mark % 60):02d}] ' + ' '.join(b for b in buf if b))
            buf, mark = [], None
    if buf:
        parts.append(f'[{int((mark or 0) // 60):02d}:{int((mark or 0) % 60):02d}] ' + ' '.join(b for b in buf if b))
    text = '\n'.join(parts).strip()
    if not text:
        raise feeds.FeedError('субтитры пустые')
    return text[:MAX_CHARS]


# ---------- статьи ----------
def article_text(url: str) -> str:
    final, body, _ = feeds.fetch(url, accept='text/html,application/xhtml+xml;q=0.9,*/*;q=0.5')
    text = trafilatura.extract(body, url=final, output_format='txt', include_comments=False, include_tables=True,
                               include_links=False, include_images=False, deduplicate=True)
    text = re.sub(r'\n{3,}', '\n\n', (text or '').strip())
    if len(text) < 200:
        raise feeds.FeedError('на странице не нашлось текста статьи')
    return text[:MAX_CHARS]


# ---------- дозаполнение ----------
def fill(articles: int = 40, videos: int = 10) -> dict:
    """Достать текст для свежих материалов, у которых его ещё нет. Вызывается после каждого сбора."""
    if not ensure_columns():
        return {}
    done = {'articles': 0, 'videos': 0, 'errors': 0, 'youtube': None}
    rows = db.q("""SELECT id, url, source_type FROM k_items
        WHERE source_type = 'rss' AND content IS NULL AND content_tries < 3 AND collected_at > now() - interval '3 days'
        ORDER BY collected_at DESC LIMIT %s""", (articles,))
    for r in rows:
        try:
            text = article_text(r['url'])
            db.x("UPDATE k_items SET content = %s, content_kind = 'article', content_error = NULL, content_at = now(), "
                 "content_tries = content_tries + 1 WHERE id = %s", (text, r['id']))
            done['articles'] += 1
        except feeds.FeedError as e:
            _fail(r['id'], str(e))
            done['errors'] += 1
        except Exception as e:  # одна кривая страница не должна останавливать остальные
            log.exception('статья %s', r['id'])
            _fail(r['id'], 'внутренняя ошибка: ' + type(e).__name__)
            done['errors'] += 1

    if _yt_paused():
        done['youtube'] = 'paused'
        return done
    rows = db.q("""SELECT id, url FROM k_items
        WHERE source_type = 'youtube' AND content_kind IS DISTINCT FROM 'transcript' AND content_tries < 3
          AND collected_at > now() - interval '3 days' ORDER BY collected_at DESC LIMIT %s""", (videos,))
    for r in rows:
        vid = video_id(r['url'])
        if not vid:
            _fail(r['id'], 'не нашёл номер видео в ссылке')
            continue
        try:
            text = transcript(vid)
            db.x("UPDATE k_items SET content = %s, content_kind = 'transcript', content_error = NULL, content_at = now(), "
                 "content_tries = content_tries + 1 WHERE id = %s", (text, r['id']))
            done['videos'] += 1
            if youtube_state().get('status') != 'ok':
                _yt_set('ok', 'расшифровки берутся напрямую с YouTube')
        except Blocked as e:
            _yt_set('blocked', f'YouTube не отдаёт расшифровки нашему серверу ({e}). Нужен посредник — Apify.')
            done['youtube'] = 'blocked'
            log.warning('YouTube не пускает за расшифровками: %s', e)
            break
        except feeds.FeedError as e:
            _fail(r['id'], str(e))
            done['errors'] += 1
        except Exception as e:
            log.exception('видео %s', r['id'])
            _fail(r['id'], 'внутренняя ошибка: ' + type(e).__name__)
            done['errors'] += 1
        time.sleep(1.5)  # не частим: YouTube не любит очереди запросов
    return done


def _fail(item_id: int, err: str) -> None:
    """Не вышло достать текст: пишем причину; уже имеющийся текст (например, описание видео) остаётся."""
    db.x('UPDATE k_items SET content_error = %s, content_tries = content_tries + 1, content_at = now() WHERE id = %s',
         (err[:300], item_id))


def item(item_id: int) -> dict | None:
    """Материал целиком: для окна «что внутри» в Студии и для Claude."""
    if not ensure_columns():
        return None
    r = db.q1("""SELECT k.*, s.name AS src_name, s.site_url AS src_site FROM k_items k
        LEFT JOIN studio_sources s ON s.id = k.source_id WHERE k.id = %s""", (int(item_id),))
    if not r:
        return None
    for k in ('published_at', 'collected_at', 'content_at'):
        if isinstance(r.get(k), (dt.datetime, dt.date)):
            r[k] = r[k].isoformat()
    r['content_label'] = KIND_LABEL.get(r.get('content_kind') or '', '')
    r['content_chars'] = len(r.get('content') or '')
    return r
