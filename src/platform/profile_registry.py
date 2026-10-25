"""Fixed profile resolvers; research profiles never enter DSM platform lookup."""
from __future__ import annotations

from types import MappingProxyType

from boot_provider import ContractError, Profile


_LEGACY_PROFILES = MappingProxyType({
    "virtualdsm": Profile(
        "virtualdsm", "virtualdsm", "amd64", "virtualdsm-legacy", "q35"),
    "rtd1619b": Profile(
        "rtd1619b", "rtd1619b", "arm64", "rtd1619b-direct", "virt"),
})
_RESEARCH_PROFILES = MappingProxyType({
    "research-arm64-linux-kexec": Profile(
        "research-arm64-linux-kexec", "open-linux", "arm64",
        "arm64-linux-kexec", "virt", "arm64"),
    "research-arm64-dsm-kexec": Profile(
        "research-arm64-dsm-kexec", "rtd1619b", "arm64",
        "arm64-dsm-kexec", "virt", "arm64"),
    "research-x86_64-grub-linux": Profile(
        "research-x86_64-grub-linux", "open-linux", "amd64",
        "x86_64-grub-iso", "q35", "amd64"),
})


def legacy_profile(profile_id: str) -> Profile:
    """Resolve only an existing, production DSM platform profile."""
    try:
        return _LEGACY_PROFILES[profile_id]
    except (KeyError, TypeError) as error:
        raise ContractError("profile is not an existing DSM platform") from error


def legacy_profile_ids() -> tuple[str, ...]:
    """List the only profile IDs that may bind to DSM_PLATFORM."""
    return tuple(_LEGACY_PROFILES)


def research_profile(profile_id: str) -> Profile:
    """Resolve one explicitly named research profile, never a production selector."""
    try:
        return _RESEARCH_PROFILES[profile_id]
    except (KeyError, TypeError) as error:
        raise ContractError("profile is not an internal open-Linux research profile") from error
