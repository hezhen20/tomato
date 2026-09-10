"""开发模式：源码或样式变化时自动重启应用。"""
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
WATCHED_SUFFIXES = {".py", ".pyw", ".qss"}


def should_watch_file(path: str) -> bool:
    return Path(path).suffix.casefold() in WATCHED_SUFFIXES


def main() -> int:
    try:
        from watchfiles import DefaultFilter, run_process
    except ImportError:
        print(
            "缺少开发依赖 watchfiles，请先运行："
            " python -m pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        return 1

    class AppFileFilter(DefaultFilter):
        def __call__(self, change, path: str) -> bool:
            return should_watch_file(path) and super().__call__(change, path)

    run_process(
        str(PROJECT_ROOT),
        target="main.main",
        target_type="function",
        watch_filter=AppFileFilter(),
        recursive=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
