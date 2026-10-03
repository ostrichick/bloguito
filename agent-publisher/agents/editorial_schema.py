"""Model-independent article and review response schemas."""
from typing import Literal
from pydantic import BaseModel, Field
from agents.editorial import policy_profile


class Evidence(BaseModel):
    source_id: str
    quote: str


class SumCalculation(BaseModel):
    operation: Literal['sum']
    unit: Literal['원']
    operands: list[int]
    result: int


class IllustrativeInputCalculation(BaseModel):
    operation: Literal['illustrative_input']
    age: int
    monthly_salary: int
    employment_months: int


class DaysToMonthsCalculation(BaseModel):
    operation: Literal['days_to_months']
    days: int
    months: int


class PensionProjectionHorizon(BaseModel):
    years_after_normal: int
    cumulative_result: int


class PensionProjectionCalculation(BaseModel):
    operation: Literal['pension_projection']
    unit: Literal['원']
    base_monthly: int
    direction: Literal['decrease', 'none', 'increase']
    change_percent: int
    start_offset_years: int
    monthly_result: int
    horizons: list[PensionProjectionHorizon]


class MonthlyFromTotalDaysCalculation(BaseModel):
    operation: Literal['monthly_from_total_days']
    total: int
    days: int
    monthly: int


class AddDurationCalculation(BaseModel):
    operation: Literal['add_duration']
    unit: Literal['분']
    start: str
    duration: int
    result: str


DerivedCalculation = (
    SumCalculation
    | IllustrativeInputCalculation
    | DaysToMonthsCalculation
    | PensionProjectionCalculation
    | MonthlyFromTotalDaysCalculation
    | AddDurationCalculation
)


class Paragraph(BaseModel):
    text: str
    evidence: list[Evidence]
    answers: list[str] = Field(default_factory=list)
    emphasis: list[str] = Field(default_factory=list, description=(
        'Optional reviewed phrases already present verbatim in text; renderer only adds emphasis.'
    ))
    calculations: list[DerivedCalculation] = Field(default_factory=list, description=(
        'Optional deterministic calculations; the validator still enforces operation-specific evidence rules.'
    ))


class InformationTableRow(BaseModel):
    cells: list[str]
    evidence: list[Evidence]
    answers: list[str] = Field(default_factory=list)
    calculations: list[DerivedCalculation] = Field(default_factory=list)


class InformationTable(BaseModel):
    caption: str
    headers: list[str]
    rows: list[InformationTableRow]
    mobile_cards: bool = Field(default=False, description=(
        'For event/comparison overviews, render one card per row on narrow screens.'
    ))


class SectionFact(BaseModel):
    label: str
    value: str
    evidence: list[Evidence]
    answers: list[str] = Field(default_factory=list)
    calculations: list[DerivedCalculation] = Field(default_factory=list)


class SectionImage(BaseModel):
    url: str
    alt: str
    caption: str
    source_id: str
    rights: str | None = Field(default=None, description=(
        'Optional reviewed reuse basis such as site_owned, open_license, permission_granted or source_attributed. '
        'For open-license or permission-based images, rights_url should identify the reuse terms.'
    ))
    rights_url: str | None = None
    year: int | None = Field(default=None, description=(
        'Optional actual image/photo year when the year is editorially relevant and reviewed.'
    ))


class SectionLocation(BaseModel):
    venue: str
    address: str = Field(description=(
        'Verified street/lot address when the official source provides one. Use an empty string rather than inventing an address.'
    ))
    query: str
    evidence: list[Evidence]


class EventSectionLocation(SectionLocation):
    latitude: float | None = Field(default=None, description=(
        'Event-post v1 only: verified Kakao Map marker latitude for this event venue.'
    ))
    longitude: float | None = Field(default=None, description=(
        'Event-post v1 only: verified Kakao Map marker longitude for this event venue.'
    ))


class OfficialSectionLink(BaseModel):
    label: str
    url: str


class BaseSection(BaseModel):
    heading: str
    paragraphs: list[Paragraph]
    table: InformationTable | None = None
    facts: list[SectionFact] = Field(default_factory=list)
    image: SectionImage | None = None
    location: SectionLocation | None = None
    actions: list[str] = Field(default_factory=list, description=(
        'Optional reviewed action URLs to render inside this section. Each URL must '
        'exactly match an official source action; scoped actions are omitted from the global CTA.'
    ))
    official_links: list[OfficialSectionLink] = Field(default_factory=list, description=(
        'Informational links to an official source used by this section. '
        'These are not booking/apply/purchase actions.'
    ))
    kind: str | None = Field(default=None, description=(
        'Select overview, eligibility, comparison, procedure, exceptions, schedule or general. '
        'Only procedure is a numbered STEP. Use overview for a short at-a-glance table before links.'
    ))


class EventSection(BaseSection):
    location: EventSectionLocation | None = None
    event_name: str | None = Field(default=None, description=(
        'Event-post v1 only: exact temporal_source.event_entries[].name for one detailed event section. '
        'Leave empty on overview/comparison/FAQ-oriented sections.'
    ))


class FAQ(BaseModel):
    question_id: str = Field(description='Use an existing reader_questions ID such as q1, not a new FAQ ID. Also include it in answer.answers.')
    question: str
    answer: Paragraph


class RelatedPost(BaseModel):
    post_id: int
    label: str
    url: str


class LeadImage(BaseModel):
    url: str
    alt: str
    width: int
    height: int


class ReaderTool(BaseModel):
    kind: Literal['minimum_wage_monthly']
    title: str
    formula_version: Literal['moel_weekly_holiday_v1']
    hourly_wage_default: int
    weekly_hours_default: float
    weekly_holiday_default: bool
    evidence: list[Evidence]


class OfficialNavigation(BaseModel):
    label: str
    url: str
    note: str


class GeneralPlan(BaseModel):
    title: str
    lead: Paragraph
    sections: list[BaseSection]
    faq: list[FAQ] = Field(default_factory=list)
    lead_image: LeadImage | None = None
    official_navigation: list[OfficialNavigation] = Field(default_factory=list, description=(
        'Optional reviewed official-site/menu navigation; never a direct action CTA.'
    ))
    related_posts: list[RelatedPost] = Field(default_factory=list, description=(
        'Optional, at most two already-published articles on the same site, '
        'with verified https://lifeinfo24.org/?p=ID URLs; never official CTA or evidence.'
    ))
    reader_tools: list[ReaderTool] = Field(default_factory=list, description=(
        'Optional reviewed reader utility. Tool type and formula are allowlisted; arbitrary model JS is never rendered.'
    ))


class EventPlan(GeneralPlan):
    sections: list[EventSection]


class Plan(EventPlan):
    """Backward-compatible parser for stored reviewed plans.

    New model generation uses GeneralPlan or EventPlan based on policy_profile().
    Keeping the legacy superset parser avoids rewriting stored bundles merely to
    adopt the narrower generation schemas.
    """


def writer_plan_schema(bundle):
    """Return the narrow response schema for a newly generated plan."""
    return EventPlan if policy_profile(bundle) == 'event' else GeneralPlan


class Checks(BaseModel):
    source_support: bool
    conditions_preserved: bool
    question_answered: bool
    useful_lifetime: bool
    no_reader_deflection: bool
    no_unsupported_claims: bool


class Review(BaseModel):
    checks: Checks
    issues: list[str]


class DeltaChecks(BaseModel):
    meaning_preserved: bool
    evidence_still_supports: bool
    conditions_preserved: bool
    no_new_claims: bool
    reader_task_preserved: bool


class DeltaReview(BaseModel):
    checks: DeltaChecks
    issues: list[str]

