"""Pydantic models for spec pipeline node outputs."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BrandDirection(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    concept: str
    boldness: Literal["low", "medium", "high"] = "high"
    visual_adjectives: list[str] = []
    risk_level: Optional[Literal["conservative", "moderate", "experimental"]] = None
    rationale: Optional[str] = None


class Tone(BaseModel):
    voice: str
    formality: str
    humor: str = ""


class BrandMessages(BaseModel):
    primary: str
    secondary: str
    trust: str


class BrandProfile(BaseModel):
    model_config = ConfigDict(extra="allow")
    directions: Optional[list[BrandDirection]] = None
    chosen_direction: BrandDirection
    tone: Tone
    hero_headlines: list[str] = []
    image_keywords: list[str] = []
    messages: BrandMessages
    seo_keywords: Optional[list[str]] = None

    @model_validator(mode="before")
    @classmethod
    def unwrap_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for key in ("brand_profile", "brand", "profile", "shared_elements"):
            nested = data.pop(key, None) if key != "brand_profile" else data.get(key)
            if isinstance(nested, dict):
                for k, v in nested.items():
                    data.setdefault(k, v)
                if key == "brand_profile" and all(
                    k in data for k in ("tone", "hero_headlines", "messages")
                ):
                    data.pop("brand_profile", None)
        if "creative_directions" in data and "directions" not in data:
            data["directions"] = data.pop("creative_directions")
        if "chosen_direction" not in data and "directions" in data:
            dirs = data["directions"]
            if dirs:
                ranked = sorted(dirs, key=lambda d: (
                    {"high": 3, "medium": 2, "low": 1}.get(
                        d.get("boldness", "low") if isinstance(d, dict) else "low", 0
                    ),
                    {"experimental": 3, "moderate": 2, "conservative": 1}.get(
                        d.get("risk_level", "conservative") if isinstance(d, dict) else "conservative", 0
                    ),
                ), reverse=True)
                data["chosen_direction"] = ranked[0]
        return data


class ColorToken(BaseModel):
    hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    usage: str


class Palette(BaseModel):
    model_config = ConfigDict(extra="allow")
    primary: ColorToken
    secondary: ColorToken
    accent: ColorToken
    background: ColorToken
    surface: ColorToken
    text: ColorToken
    muted: ColorToken


class Motion(BaseModel):
    model_config = ConfigDict(extra="allow")
    level: Literal["none", "subtle", "medium", "max"]
    duration_fast: str
    duration_normal: str
    duration_slow: Optional[str] = None
    easing: str


class DesignTokens(BaseModel):
    model_config = ConfigDict(extra="allow")
    palette: Palette
    spacing: dict[str, str]
    grid: dict[str, Any]
    radius: dict[str, str] = {}
    shadow: Optional[dict[str, str]] = None
    motion: Motion
    bold_design_move: str
    bold_design_move_implementation: Optional[str] = None


class FontSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    family: str
    weights: list[int]
    usage: str
    variable: Optional[bool] = None


class TypeScaleEntry(BaseModel):
    model_config = ConfigDict(extra="allow")
    size: str
    weight: int
    tracking: str
    line_height: float | int
    font: Optional[str] = None
    transform: Optional[str] = None


class TypographySpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    primary: FontSpec
    secondary: FontSpec
    scale: dict[str, TypeScaleEntry]
    max_line_length: str = "65ch"
    font_import_urls: list[str] = []
    tailwind_mapping: dict[str, str] = {}


class BackgroundLayer(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: Literal["photo", "3d", "svg", "gradient", "video", "none"] = "none"
    hint: str = ""
    z_index: int = -1


class LayoutSection(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    role: str
    grid: str
    elements: list[Any]
    height: Optional[str] = None
    content_side: Optional[str] = None
    image_ratio: Optional[str] = None
    spacing_before: Optional[str] = None
    spacing_after: Optional[str] = None
    sticky: bool = False
    bold_move_applied: bool = False
    animation_hint: Optional[str] = None
    background_layer: Optional[BackgroundLayer | dict] = None


class AntiTemplateCheck(BaseModel):
    model_config = ConfigDict(extra="allow")
    pattern_hash: Optional[str] = None
    similarity_to_known: Optional[float] = None
    mutation_applied: Optional[str] = None


class LayoutSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    page: str
    emotional_arc: list[str]
    sections: list[LayoutSection]
    focal_hierarchy: list[str]
    ascii_wireframe: str = ""
    layers: list[str] = Field(default_factory=lambda: ["background", "content"])
    anti_template_check: Optional[AntiTemplateCheck] = None

    @model_validator(mode="before")
    @classmethod
    def unwrap_nesting(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "layout_spec" in data and "sections" not in data:
            inner = data["layout_spec"]
            if isinstance(inner, dict):
                return inner
        return data


class SectionBackground(BaseModel):
    model_config = ConfigDict(extra="allow")
    section_id: str
    background_type: Literal["photo", "3d", "svg", "gradient", "video"]
    config: dict[str, Any] = {}
    z_index: int = -1
    layer: str = "background"


class BackgroundDependencies(BaseModel):
    model_config = ConfigDict(extra="allow")
    needs_three_js: bool = False
    needs_d3: bool = False
    needs_react: bool = False


class BackgroundSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    backgrounds: list[SectionBackground]
    dependencies: BackgroundDependencies = Field(default_factory=BackgroundDependencies)

    @model_validator(mode="before")
    @classmethod
    def unwrap_nesting(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "background_spec" in data and "backgrounds" not in data:
            return data["background_spec"]
        return data


class AssetImage(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    role: str
    source: str
    url: Optional[str] = None
    alt: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    srcset: list[dict[str, Any]] = []
    photographer: Optional[str] = None
    license: Optional[str] = None
    local_path: Optional[str] = None
    crop: Optional[Any] = None


class AssetIcon(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    source: str
    svg: str
    role: Optional[str] = None
    category: Optional[str] = None


class AssetManifest(BaseModel):
    model_config = ConfigDict(extra="allow")
    images: list[AssetImage] = []
    icons: list[AssetIcon] = []


class SvgIllustratorOutput(BaseModel):
    icons: list[AssetIcon]


class SectionAnimation(BaseModel):
    model_config = ConfigDict(extra="allow")
    section_id: str
    entrance: dict[str, Any]
    children_stagger: Optional[dict[str, Any]] = None
    hover: Optional[list[dict[str, Any]]] = None
    parallax: Optional[dict[str, Any]] = None
    scroll_progress: Optional[dict[str, Any]] = None


class AnimationGlobal(BaseModel):
    model_config = ConfigDict(extra="allow")
    reduced_motion_strategy: str = "prefers-reduced-motion media query"
    observer_config: dict[str, Any] = Field(
        default_factory=lambda: {"threshold": 0.15, "root_margin": "0px 0px -50px 0px"}
    )


class AnimationSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    sections: list[SectionAnimation]
    global_config: AnimationGlobal = Field(default_factory=AnimationGlobal, alias="global")

    @model_validator(mode="before")
    @classmethod
    def unwrap_nesting(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "animation_spec" in data and "sections" not in data:
            return data["animation_spec"]
        return data
