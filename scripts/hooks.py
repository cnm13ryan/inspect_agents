import json
import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("mkdocs")


def _filter_search_index(obj: Dict[str, Any]) -> Dict[str, Any]:
    docs: List[Dict[str, Any]] = obj.get("docs", [])
    before = len(docs)
    filtered = [d for d in docs if not str(d.get("location", "")).startswith("backlog/")]
    removed = before - len(filtered)
    if removed:
        log.info("search: excluded %d backlog pages from index", removed)
    obj["docs"] = filtered
    return obj


def on_post_build(config, **_: object) -> None:  # type: ignore[no-redef]
    site_dir = Path(config["site_dir"])  # type: ignore[index]
    # MkDocs (Material) writes to search/search_index.json by default
    candidates = [
        site_dir / "search" / "search_index.json",
        site_dir / "search_index.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data = _filter_search_index(data)
                path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                return
            except Exception as exc:  # pragma: no cover — defensive logging only
                log.warning("search: failed to post-process %s: %s", path, exc)
                return
    log.info("search: no search_index.json found; skipping backlog exclusion")

