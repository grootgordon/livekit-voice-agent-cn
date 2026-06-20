"""LiveKit 传输层切换(Cloud ⇄ 本地)解析器。

与 agent-web / agent-node 的 resolver 逻辑一致:从本文件向上查找仓库根的
`.livekit.env`,根据 LIVEKIT_PROFILE(cloud|local)把选中的 URL/KEY/SECRET
写入 os.environ 的标准变量(LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET)。
LiveKit Agents 会自动读取这三个环境变量连接 server。
"""

from __future__ import annotations

import os
from pathlib import Path

_PROFILE_FILE = ".livekit.env"


def _parse_env_file(path: Path) -> dict[str, str]:
    cfg: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, _, raw = s.partition("=")
        key = key.strip()
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            cfg[key] = value
    return cfg


def _find_profile_file(start: Path) -> Path | None:
    cur = start.resolve()
    for parent in [cur, *cur.parents]:
        candidate = parent / _PROFILE_FILE
        if candidate.is_file():
            return candidate
    return None


def resolve_livekit_profile() -> str:
    """按 LIVEKIT_PROFILE 设定 LIVEKIT_URL/KEY/SECRET。返回当前 profile。"""
    env_path = _find_profile_file(Path(__file__).parent)
    if env_path is None:
        print(
            "⚠️  未找到根 .livekit.env — 沿用环境变量里的 LIVEKIT_URL/API_KEY/API_SECRET。"
        )
        return os.environ.get("LIVEKIT_PROFILE", "(unset)")

    cfg = _parse_env_file(env_path)
    profile = (cfg.get("LIVEKIT_PROFILE") or os.environ.get("LIVEKIT_PROFILE") or "cloud").lower()
    suffix = "LOCAL" if profile == "local" else "CLOUD"

    url = cfg.get(f"LIVEKIT_URL_{suffix}") or os.environ.get("LIVEKIT_URL")
    key = cfg.get(f"LIVEKIT_API_KEY_{suffix}") or os.environ.get("LIVEKIT_API_KEY")
    secret = cfg.get(f"LIVEKIT_API_SECRET_{suffix}") or os.environ.get("LIVEKIT_API_SECRET")

    if url:
        os.environ["LIVEKIT_URL"] = url
    if key:
        os.environ["LIVEKIT_API_KEY"] = key
    if secret:
        os.environ["LIVEKIT_API_SECRET"] = secret
    os.environ["LIVEKIT_PROFILE"] = profile

    print(f"🛰  LiveKit transport = {profile.upper()}  ({url or '(no url)'})  [{env_path}]")
    return profile


if __name__ == "__main__":
    resolve_livekit_profile()
