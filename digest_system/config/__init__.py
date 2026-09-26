"""Configuration: digest frontmatter, runtime components, style profiles and budgets."""

from __future__ import annotations

from .budgets import STYLE_BUDGET, StyleBudget, budget_for, budget_prose
from .digests import ResolvedDigest, frontmatter_value, read_frontmatter, resolve_digest
from .profiles import (
    CANONICAL_STYLES,
    DEFAULT_STYLE_PROFILE_BY_STYLE,
    STYLE_PROFILES,
    StyleProfile,
    default_style_profile_id,
    describe_style_profile,
    preflight_style_profile,
    profiles_for_style,
    resolve_style_profile,
    style_profile_for,
    style_profile_ids,
    validate_style_profile,
)
from .runtime import (
    PIPELINE_V1,
    PIPELINE_V2,
    SUPPORTED_PIPELINES,
    load_runtime_config,
    resolve_adapter_timeout,
    resolve_python,
    resolve_wops_root,
    spawn_capture,
)

__all__ = [
    "STYLE_BUDGET",
    "StyleBudget",
    "budget_for",
    "budget_prose",
    "ResolvedDigest",
    "frontmatter_value",
    "read_frontmatter",
    "resolve_digest",
    "CANONICAL_STYLES",
    "DEFAULT_STYLE_PROFILE_BY_STYLE",
    "STYLE_PROFILES",
    "StyleProfile",
    "default_style_profile_id",
    "describe_style_profile",
    "preflight_style_profile",
    "profiles_for_style",
    "resolve_style_profile",
    "style_profile_for",
    "style_profile_ids",
    "validate_style_profile",
    "PIPELINE_V1",
    "PIPELINE_V2",
    "SUPPORTED_PIPELINES",
    "load_runtime_config",
    "resolve_adapter_timeout",
    "resolve_python",
    "resolve_wops_root",
    "spawn_capture",
]