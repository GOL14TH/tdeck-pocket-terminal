from __future__ import annotations
import os, yaml
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field

class HostProfile(BaseModel):
    id: str
    name: str
    hostname: str | None = None
    local_ip: str | None = None
    tailscale_gateway: str | None = None
    terminal_target: str | None = None
    ai_url: str = "http://127.0.0.1:11434"
    ai_model: str = "gemma3"
    ai_provider: Literal["ollama", "openai-compatible"] = "ollama"
    ai_api_key_env: str | None = None
    vnc_host: str | None = None
    vnc_port: int = 5900
    vnc_password: str | None = None

class Settings(BaseModel):
    token: str = Field(min_length=16)
    bind_host: str = "0.0.0.0"
    bind_port: int = 8787
    tls_cert: str | None = None
    tls_key: str | None = None
    hosts: list[HostProfile] = Field(default_factory=list)
    command_allowlist: dict[str, list[str]] = Field(default_factory=dict)
    raw_shell_enabled: bool = False
    state_db: str = "/var/lib/tdeck-companion/state.sqlite3"
    simulation: bool = False
    mesh_serial: str | None = None
    mesh_tcp: str | None = None
    mesh_key: str | None = Field(default=None, min_length=32)
    mesh_allowed_nodes: list[int] = Field(default_factory=list)

    def host(self, host_id: str) -> HostProfile:
        for h in self.hosts:
            if h.id == host_id:
                return h
        raise KeyError(host_id)

def load_settings(path: str | None = None) -> Settings:
    p = Path(
        path or os.getenv("TDECK_COMPANION_CONFIG", "/etc/tdeck-companion/config.yaml")
    )
    data = yaml.safe_load(p.read_text()) if p.exists() else {}
    data["token"] = os.getenv("TDECK_COMPANION_TOKEN", data.get("token", ""))
    if not data["token"] or data["token"].startswith(("REPLACE-", "change-me")):
        raise ValueError("Configure a random companion token before starting")
    return Settings.model_validate(data)
