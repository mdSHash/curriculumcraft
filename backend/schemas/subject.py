"""Subject taxonomy Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TopicSectionDefault(BaseModel):
    """A default weekly-assessment topic section for a subject."""

    title_ar: str = ""
    title_en: str = ""
    count: int = 4
    marks_per_question: int = 2


class SubjectListItem(BaseModel):
    """Lightweight subject summary for list/picker views."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    label_en: str
    label_ar: str
    book_count: int = 0


class SubjectResponse(BaseModel):
    """Full subject record."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    label_en: str
    label_ar: str
    moe_catalog_labels: list[str] = []
    content_traits: dict = {}
    default_topic_sections: list[TopicSectionDefault] = []
    letterhead_lines_ar: list[str] = []
    letterhead_lines_en: list[str] = []
    created_at: Optional[datetime] = None


class SubjectConfig(BaseModel):
    """Frontend-facing subset of subject config used by the wizard.

    Fed to React via GET /api/subjects/{key}/config so the wizard can
    decide which content boxes to render, which RTL/LTR direction to use,
    which default topic sections to pre-fill, etc.
    """

    key: str
    label_en: str
    label_ar: str
    has_math_rendering: bool = False
    has_formula_boxes: bool = False
    has_code_blocks: bool = False
    has_quotations: bool = False
    has_diagrams: bool = False
    primary_direction: str = "rtl"   # rtl | ltr
    primary_script: str = "arabic"   # arabic | latin | cjk
    is_second_language: bool = False
    default_topic_sections: list[TopicSectionDefault] = []
