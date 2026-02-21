#!/usr/bin/env python3
"""log-viewer.py - neko-pm ログビューアー TUI

output/logs/*.md ファイルをリアルタイムで監視・表示する。
3スレッド構成: メイン（rich.Live描画）/ キーボード / watchdog Observer
"""

import os
import re
import sys
import time
import queue
import select
import termios
import threading
import tty
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ===== 設定 =====

PROJECT_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = PROJECT_DIR / "output" / "logs"
EXCLUDE_FILES = {"chat-app.log", ".gitkeep"}
REFRESH_PER_SECOND = 2
NOTIFICATION_DURATION = 3.0

# ===== エージェント設定 =====

AGENT_STYLES: dict[str, tuple[str, str]] = {
    "kitten":              ("🐱", "bright_white"),
    "kitten-frontend":     ("🎨", "bright_cyan"),
    "kitten-backend":      ("⚙️",  "bright_green"),
    "kitten-infra":        ("🏗️", "bright_yellow"),
    "kitten-mobile":       ("📱", "bright_magenta"),
    "kitten-slides":       ("📊", "bright_blue"),
    "kitten-codex-bridge": ("🔬", "bright_red"),
    "kitten-gemini-bridge":("🦊", "orange3"),
}
DEFAULT_AGENT_STYLE = ("🐾", "white")

# フィルタ循環リスト
AGENT_FILTER_LIST = ["ALL"] + list(AGENT_STYLES.keys())

# ===== ファイル名パターン =====

# 完全形: YYYY-MM-DD_HHMM_{agent}_{task}.md
RE_FULL = re.compile(r'^(\d{4}-\d{2}-\d{2})_(\d{4})_(.+?)_(.+)\.md$')
# 日付のみ: YYYY-MM-DD_{agent}_{task}.md
RE_DATE = re.compile(r'^(\d{4}-\d{2}-\d{2})_(.+?)_(.+)\.md$')


# ===== データクラス =====

@dataclass
class LogEntry:
    """ログファイルのメタデータ"""
    path: Path
    date: str
    time_str: str      # "--:--" if no time
    agent: str
    task: str
    icon: str
    style: str
    mtime: float = 0.0

    @property
    def sort_key(self) -> tuple:
        return (self.date, self.time_str)


@dataclass
class AppState:
    """アプリケーション状態（lock で保護する）"""
    view: str = "list"           # "list" | "detail" | "help"
    entries: list = field(default_factory=list)
    filtered_entries: list = field(default_factory=list)
    cursor: int = 0
    scroll_offset: int = 0
    filter_agent: str = "ALL"
    search_query: str = ""
    search_mode: bool = False
    search_input: str = ""
    selected_entry: Optional[LogEntry] = None
    detail_scroll: int = 0
    detail_content: str = ""
    tail_mode: bool = False
    notification: Optional[str] = None
    notification_time: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)
    should_quit: bool = False


# ===== パーサー =====

def parse_filename(filename: str) -> Optional[LogEntry]:
    """ファイル名を解析して LogEntry を返す（マッチしない場合 None）"""
    if filename in EXCLUDE_FILES:
        return None
    if not filename.endswith(".md"):
        return None

    path = LOG_DIR / filename

    m = RE_FULL.match(filename)
    if m:
        date, hhmm, agent, task = m.groups()
        time_display = f"{hhmm[:2]}:{hhmm[2:]}"
        icon, style = AGENT_STYLES.get(agent, DEFAULT_AGENT_STYLE)
        entry = LogEntry(path=path, date=date, time_str=time_display,
                         agent=agent, task=task, icon=icon, style=style)
        try:
            entry.mtime = path.stat().st_mtime
        except OSError:
            pass
        return entry

    m = RE_DATE.match(filename)
    if m:
        date, agent, task = m.groups()
        icon, style = AGENT_STYLES.get(agent, DEFAULT_AGENT_STYLE)
        entry = LogEntry(path=path, date=date, time_str="--:--",
                         agent=agent, task=task, icon=icon, style=style)
        try:
            entry.mtime = path.stat().st_mtime
        except OSError:
            pass
        return entry

    return None


def load_logs() -> list[LogEntry]:
    """ログディレクトリをスキャンして全エントリを返す（日付・時刻降順）"""
    entries: list[LogEntry] = []
    if not LOG_DIR.exists():
        return entries

    for f in LOG_DIR.iterdir():
        if f.name in EXCLUDE_FILES:
            continue
        entry = parse_filename(f.name)
        if entry:
            entries.append(entry)

    entries.sort(key=lambda e: e.sort_key, reverse=True)
    return entries


def apply_filter(state: AppState) -> list[LogEntry]:
    """フィルタと検索クエリを適用してエントリリストを返す"""
    result = list(state.entries)

    if state.filter_agent != "ALL":
        result = [e for e in result if e.agent == state.filter_agent]

    if state.search_query:
        q = state.search_query.lower()
        result = [
            e for e in result
            if q in e.task.lower() or q in e.agent.lower() or q in e.date
        ]

    return result


def read_file_content(path: Path) -> str:
    """ファイル内容を UTF-8 で読み込む"""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"*エラー: ファイルを読み込めませんでした: {exc}*"


# ===== キーボードリーダー（スレッド） =====

class KeyboardReader(threading.Thread):
    """tty.setraw + select.select でキー入力を非同期読み取り"""

    def __init__(self, event_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(daemon=True, name="KeyboardReader")
        self.event_queue = event_queue
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            try:
                rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            except (ValueError, OSError):
                break

            if not rlist:
                continue

            try:
                key = sys.stdin.read(1)
                if not key:  # EOF
                    break
            except OSError:
                break

            if key == "\x1b":
                # ESC または矢印キーシーケンスの判定
                try:
                    r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r2:
                        ch2 = sys.stdin.read(1)
                        if ch2 == "[":
                            r3, _, _ = select.select([sys.stdin], [], [], 0.05)
                            if r3:
                                arrow = sys.stdin.read(1)
                                key = {"A": "UP", "B": "DOWN",
                                       "C": "RIGHT", "D": "LEFT"}.get(arrow, "ESC")
                            else:
                                key = "ESC"
                        else:
                            key = "ESC"
                    else:
                        key = "ESC"
                except OSError:
                    key = "ESC"

            self.event_queue.put(("key", key))


# ===== watchdog ハンドラ =====

class LogDirHandler(FileSystemEventHandler):
    """ログディレクトリの変更を監視してキューに通知"""

    def __init__(self, event_queue: queue.Queue):
        super().__init__()
        self.event_queue = event_queue

    def _is_target(self, path_str: str) -> bool:
        p = Path(path_str)
        return p.suffix == ".md" and p.name not in EXCLUDE_FILES

    def on_created(self, event):
        if not event.is_directory and self._is_target(event.src_path):
            self.event_queue.put(("file_created", Path(event.src_path).name))

    def on_modified(self, event):
        if not event.is_directory and self._is_target(event.src_path):
            self.event_queue.put(("file_modified", Path(event.src_path).name))


# ===== レンダリング =====

def _agent_text(entry: LogEntry, width: int = 14) -> Text:
    """色付きエージェントラベルを返す"""
    label = f"{entry.icon} {entry.agent}"
    if len(label) > width:
        label = label[:width - 1] + "…"
    else:
        label = label.ljust(width)
    return Text(label, style=entry.style)


def render_list_view(state: AppState, width: int, height: int) -> Panel:
    """リストビューパネルを構築"""
    entries = state.filtered_entries
    n = len(entries)

    # 表示可能行数（パネルボーダー・ヘッダー行・フッター行を差し引く）
    list_height = max(1, height - 7)

    # スクロールオフセット調整（状態を更新しても lock 内なので安全）
    if n > 0:
        if state.cursor >= state.scroll_offset + list_height:
            state.scroll_offset = state.cursor - list_height + 1
        elif state.cursor < state.scroll_offset:
            state.scroll_offset = state.cursor
        state.scroll_offset = max(0, min(state.scroll_offset, max(0, n - list_height)))

    # 通知バナー確認
    notif_text = ""
    if state.notification:
        if time.time() - state.notification_time < NOTIFICATION_DURATION:
            notif_text = f"  🔔 {state.notification}"
        else:
            state.notification = None

    # ヘッダー行
    filter_label = state.filter_agent
    header = Text()
    header.append(f"📋 {n} files", style="bold")
    header.append(f"  filter: ", style="dim")
    header.append(filter_label, style="bright_yellow" if filter_label != "ALL" else "dim")
    if state.search_query:
        header.append(f'  search: "{state.search_query}"', style="cyan")
    if notif_text:
        header.append(notif_text, style="bold bright_yellow")

    # テーブル
    table = Table(box=None, show_header=False, padding=(0, 0), expand=True)
    table.add_column("agent", width=16)
    table.add_column("date",  width=18)
    table.add_column("task",  ratio=1)

    visible = entries[state.scroll_offset: state.scroll_offset + list_height]

    for i, entry in enumerate(visible):
        idx = i + state.scroll_offset
        is_selected = (idx == state.cursor)

        agent_t = _agent_text(entry, 14)
        date_t  = Text(f"{entry.date} {entry.time_str}", style="dim")

        max_task = max(10, width - 42)
        task_label = entry.task if len(entry.task) <= max_task else entry.task[:max_task - 1] + "…"
        task_t = Text(task_label)

        if is_selected:
            prefix = Text("> ", style="bold bright_yellow")
            for t in (agent_t, date_t, task_t):
                t.stylize("bold reverse")
        else:
            prefix = Text("  ")

        table.add_row(agent_t, date_t, Text.assemble(prefix, task_t))

    # フッター（検索モード中は入力バー）
    if state.search_mode:
        footer_str = f"[bright_yellow]🔍 /{state.search_input}█  Enter:確定  Esc:キャンセル[/]"
    else:
        footer_str = "[dim]j/k:移動  Enter:開く  f:フィルタ  /:検索  r:再読み込み  q:終了  ?:ヘルプ[/]"

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_row(header)
    grid.add_row(table)

    return Panel(
        grid,
        title="[bold]🐱 neko-pm Log Viewer[/]",
        subtitle=Text.from_markup(footer_str),
        title_align="left",
        subtitle_align="left",
        border_style="bright_blue",
    )


def render_detail_view(state: AppState, width: int, height: int) -> Panel:
    """詳細ビューパネルを構築"""
    entry = state.selected_entry
    if not entry:
        return Panel("[dim]No file selected[/]", title="Detail View")

    lines = state.detail_content.split("\n")
    total_lines = len(lines)
    view_height = max(1, height - 7)

    # tail mode: 末尾にスクロール
    if state.tail_mode:
        state.detail_scroll = max(0, total_lines - view_height)
    else:
        state.detail_scroll = max(0, min(state.detail_scroll, max(0, total_lines - view_height)))

    # スクロールパーセント
    if total_lines <= view_height:
        pct = 100
    else:
        pct = int(state.detail_scroll / max(1, total_lines - view_height) * 100)

    visible_content = "\n".join(lines[state.detail_scroll: state.detail_scroll + view_height])

    icon, style_name = AGENT_STYLES.get(entry.agent, DEFAULT_AGENT_STYLE)
    tail_badge = "[bold bright_green]tail:ON[/]" if state.tail_mode else "[dim]tail:OFF[/]"

    # ヘッダー行
    header = Text()
    header.append("← q/Esc で戻る  ", style="dim")
    header.append(f"{icon} {entry.agent}  ", style=style_name)
    header.append(f"{entry.date} {entry.time_str}", style="dim")

    try:
        body = Markdown(visible_content)
    except Exception:
        body = Text(visible_content)

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_row(header)
    grid.add_row(body)

    footer_str = "[dim]j/k:スクロール  g/G:先頭/末尾  d/u:半ページ  t:tail切替  r:再読込  q/Esc:戻る[/]"

    return Panel(
        grid,
        title=f"[bold]🐱 Log Viewer[/] — [bold]{entry.task}[/] — {tail_badge} — {pct}%",
        subtitle=Text.from_markup(footer_str),
        title_align="left",
        subtitle_align="left",
        border_style="bright_green",
    )


def render_help_view() -> Panel:
    """ヘルプビューパネルを構築"""
    help_md = """\
## キーバインド

### リストビュー
| キー | 動作 |
|------|------|
| `j` / `↓` | カーソル下 |
| `k` / `↑` | カーソル上 |
| `g` | 先頭に移動 |
| `G` | 末尾に移動 |
| `Enter` | 詳細を開く |
| `f` | エージェントフィルタ循環 |
| `/` | 検索モード |
| `r` | 再読み込み |
| `q` | 終了 |
| `?` | ヘルプ切替 |

### 詳細ビュー
| キー | 動作 |
|------|------|
| `j` / `↓` | スクロール下 |
| `k` / `↑` | スクロール上 |
| `g` | 先頭 |
| `G` | 末尾 |
| `d` | 半ページ下 |
| `u` | 半ページ上 |
| `t` | tail mode 切替 |
| `r` | ファイル再読み込み |
| `q` / `Esc` | リストに戻る |

### フィルタ循環順
`ALL → kitten → kitten-frontend → kitten-backend → kitten-infra →`
`kitten-mobile → kitten-slides → kitten-codex-bridge → kitten-gemini-bridge → ALL`
"""
    return Panel(
        Markdown(help_md),
        title="[bold]🐱 Log Viewer — ヘルプ[/]",
        subtitle="[dim]? / q で戻る[/]",
        title_align="left",
        subtitle_align="left",
        border_style="bright_magenta",
    )


def make_renderable(state: AppState, console: Console):
    """現在のビュー状態に応じてレンダラブルを返す"""
    width, height = console.size
    if state.view == "help":
        return render_help_view()
    elif state.view == "detail":
        return render_detail_view(state, width, height)
    else:
        return render_list_view(state, width, height)


# ===== キー処理 =====

def _open_detail(state: AppState, entry: LogEntry):
    """詳細ビューを開く"""
    state.selected_entry = entry
    state.view = "detail"
    state.detail_scroll = 0
    state.tail_mode = False
    state.detail_content = read_file_content(entry.path)


def handle_list_key(key: str, state: AppState):
    n = len(state.filtered_entries)

    # 検索モード中
    if state.search_mode:
        if key in ("\r", "\n"):
            state.search_query = state.search_input
            state.search_mode = False
            state.filtered_entries = apply_filter(state)
            state.cursor = 0
            state.scroll_offset = 0
        elif key == "ESC":
            state.search_mode = False
            state.search_input = ""
        elif key in ("\x7f", "\x08"):          # Backspace
            state.search_input = state.search_input[:-1]
        elif len(key) == 1 and key.isprintable():
            state.search_input += key
        return

    if key in ("j", "DOWN"):
        if state.cursor < n - 1:
            state.cursor += 1
    elif key in ("k", "UP"):
        if state.cursor > 0:
            state.cursor -= 1
    elif key == "g":
        state.cursor = 0
        state.scroll_offset = 0
    elif key == "G":
        state.cursor = max(0, n - 1)
    elif key in ("\r", "\n"):
        if 0 <= state.cursor < n:
            _open_detail(state, state.filtered_entries[state.cursor])
    elif key == "f":
        idx = AGENT_FILTER_LIST.index(state.filter_agent) if state.filter_agent in AGENT_FILTER_LIST else 0
        state.filter_agent = AGENT_FILTER_LIST[(idx + 1) % len(AGENT_FILTER_LIST)]
        state.filtered_entries = apply_filter(state)
        state.cursor = 0
        state.scroll_offset = 0
    elif key == "/":
        state.search_mode = True
        state.search_input = ""
    elif key == "r":
        state.entries = load_logs()
        state.filtered_entries = apply_filter(state)
    elif key == "?":
        state.view = "help"
    elif key in ("q", "Q", "\x03"):
        state.should_quit = True


def handle_detail_key(key: str, state: AppState, console: Console):
    _, height = console.size
    view_height = max(1, height - 7)
    total_lines = len(state.detail_content.split("\n"))

    if key in ("q", "Q", "ESC"):
        state.view = "list"
        state.tail_mode = False
    elif key in ("j", "DOWN"):
        state.detail_scroll += 1
        state.tail_mode = False
    elif key in ("k", "UP"):
        state.detail_scroll = max(0, state.detail_scroll - 1)
        state.tail_mode = False
    elif key == "g":
        state.detail_scroll = 0
        state.tail_mode = False
    elif key == "G":
        state.detail_scroll = max(0, total_lines - view_height)
    elif key == "d":
        state.detail_scroll += max(1, view_height // 2)
        state.tail_mode = False
    elif key == "u":
        state.detail_scroll = max(0, state.detail_scroll - max(1, view_height // 2))
        state.tail_mode = False
    elif key == "t":
        state.tail_mode = not state.tail_mode
    elif key == "r":
        if state.selected_entry:
            state.detail_content = read_file_content(state.selected_entry.path)
    elif key == "?":
        state.view = "help"
    elif key in ("\x03",):
        state.should_quit = True


def handle_help_key(key: str, state: AppState):
    if key in ("q", "Q", "?", "ESC"):
        state.view = "list"
    elif key in ("\x03",):
        state.should_quit = True


# ===== イベント処理 =====

def process_events(event_queue: queue.Queue, state: AppState, console: Console):
    """キューからイベントを取り出して状態を更新する（lock 内で呼ぶこと）"""
    try:
        while True:
            event_type, event_data = event_queue.get_nowait()

            if event_type == "key":
                key = event_data
                if state.view == "list":
                    handle_list_key(key, state)
                elif state.view == "detail":
                    handle_detail_key(key, state, console)
                elif state.view == "help":
                    handle_help_key(key, state)

            elif event_type == "file_created":
                entry = parse_filename(event_data)
                if entry:
                    # 重複チェック
                    existing = {e.path.name for e in state.entries}
                    if entry.path.name not in existing:
                        state.entries.append(entry)
                        state.entries.sort(key=lambda e: e.sort_key, reverse=True)
                        state.filtered_entries = apply_filter(state)
                    state.notification = f"新ファイル: {event_data}"
                    state.notification_time = time.time()

            elif event_type == "file_modified":
                # 詳細表示中のファイルが更新されたら内容を再読み込み
                if (state.selected_entry
                        and state.selected_entry.path.name == event_data
                        and state.view == "detail"):
                    state.detail_content = read_file_content(state.selected_entry.path)

    except queue.Empty:
        pass


# ===== メイン =====

def main():
    # ターミナル設定保存
    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
    except termios.error:
        old_settings = None

    console = Console()
    event_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    # 初期ロード
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    state = AppState()
    state.entries = load_logs()
    state.filtered_entries = apply_filter(state)

    # watchdog 起動
    observer = Observer()
    observer.schedule(LogDirHandler(event_queue), str(LOG_DIR), recursive=False)
    observer.start()

    # raw mode 設定（キーボードリーダーのため）
    if old_settings is not None:
        try:
            tty.setraw(fd)
        except termios.error:
            pass

    # キーボードリーダー起動
    kb_reader = KeyboardReader(event_queue, stop_event)
    kb_reader.start()

    try:
        with Live(
            make_renderable(state, console),
            console=console,
            refresh_per_second=REFRESH_PER_SECOND,
            screen=True,
            vertical_overflow="crop",
        ) as live:
            while True:
                dirty = False
                with state.lock:
                    qsize = event_queue.qsize()
                    process_events(event_queue, state, console)
                    if state.should_quit:
                        break
                    dirty = qsize > 0 or (
                        state.notification is not None
                        and time.time() - state.notification_time < NOTIFICATION_DURATION
                    )
                    if dirty:
                        renderable = make_renderable(state, console)

                if dirty:
                    live.update(renderable)
                time.sleep(0.25)

    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        stop_event.set()
        observer.stop()
        observer.join(timeout=5)
        # ターミナル設定復元
        if old_settings is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except termios.error:
                pass


if __name__ == "__main__":
    main()
