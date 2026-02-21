from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


@dataclass(slots=True)
class WatchConfig:
    roots: list[str] = field(default_factory=lambda: ["."])
    extensions: list[str] = field(default_factory=lambda: [".md", ".markdown"])
    debounce_ms: int = 500


@dataclass(slots=True)
class StorageConfig:
    database_path: str = ".markdownkeeper/index.db"


@dataclass(slots=True)
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass(slots=True)
class MetadataConfig:
    required_frontmatter_fields: list[str] = field(default_factory=lambda: ["title"])
    auto_fill_category: bool = True


@dataclass(slots=True)
class AppConfig:
    watch: WatchConfig = field(default_factory=WatchConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    metadata: MetadataConfig = field(default_factory=MetadataConfig)


DEFAULT_CONFIG_PATH = Path("markdownkeeper.toml")


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    watch = raw.get("watch", {})
    storage = raw.get("storage", {})
    api = raw.get("api", {})
    metadata = raw.get("metadata", {})

    return AppConfig(
        watch=WatchConfig(
            roots=list(watch.get("roots", ["."])),
            extensions=list(watch.get("extensions", [".md", ".markdown"])),
            debounce_ms=int(watch.get("debounce_ms", 500)),
        ),
        storage=StorageConfig(
            database_path=str(storage.get("database_path", ".markdownkeeper/index.db"))
        ),
        api=ApiConfig(
            host=str(api.get("host", "127.0.0.1")),
            port=int(api.get("port", 8765)),
        ),
        metadata=MetadataConfig(
            required_frontmatter_fields=list(metadata.get("required_frontmatter_fields", ["title"])),
            auto_fill_category=bool(metadata.get("auto_fill_category", True)),
        ),
    )
