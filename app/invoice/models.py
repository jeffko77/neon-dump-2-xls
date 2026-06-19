from __future__ import annotations

from pydantic import BaseModel, Field


class SchoolBase(BaseModel):
    school_name: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    field_location: str | None = None
    subsite: str | None = None
    varsity_game_time: str | None = None
    jv_game_time: str | None = None
    rank: int | None = None
    parkway_district: bool = False


class SchoolCreate(SchoolBase):
    sports: list[str] = Field(default_factory=list)


class SchoolUpdate(SchoolBase):
    school_name: str | None = None
    sports: list[str] | None = None


class School(SchoolBase):
    id: int
    sports: list[str] = Field(default_factory=list)


class InvoiceBase(BaseModel):
    school_id: int
    season_year: int
    sport: str
    base_amount: float = 110.0
    revision_amount: float = 0.0
    dual_sport_fee: float = 0.0
    ranking_services: float = 0.0
    c_team_scheduling: float = 0.0
    fh_ranking_services: float = 0.0
    address_note: str | None = None
    collection_status: str | None = None
    notes: str | None = None


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(BaseModel):
    school_id: int | None = None
    season_year: int | None = None
    sport: str | None = None
    base_amount: float | None = None
    revision_amount: float | None = None
    dual_sport_fee: float | None = None
    ranking_services: float | None = None
    c_team_scheduling: float | None = None
    fh_ranking_services: float | None = None
    address_note: str | None = None
    collection_status: str | None = None
    notes: str | None = None


class Invoice(InvoiceBase):
    id: int
    created_at: str
    school_name: str | None = None
    total_amount: float = 0.0
    amount_paid: float = 0.0
    balance_due: float = 0.0


class PaymentBase(BaseModel):
    invoice_id: int
    amount_paid: float | None = None
    date_paid: str | None = None
    payment_method: str | None = None
    notes: str | None = None


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    invoice_id: int | None = None
    amount_paid: float | None = None
    date_paid: str | None = None
    payment_method: str | None = None
    notes: str | None = None


class Payment(PaymentBase):
    id: int
    school_name: str | None = None
    season_year: int | None = None
    sport: str | None = None


class GameBase(BaseModel):
    game_date: str
    game_time: str | None = None
    level: str | None = None
    home_school_id: int | None = None
    away_school_id: int | None = None
    field_location: str | None = None
    season_year: int | None = None
    sport: str = "Lacrosse"


class GameCreate(GameBase):
    pass


class GameUpdate(BaseModel):
    game_date: str | None = None
    game_time: str | None = None
    level: str | None = None
    home_school_id: int | None = None
    away_school_id: int | None = None
    field_location: str | None = None
    season_year: int | None = None
    sport: str | None = None


class Game(GameBase):
    id: int
    home_school_name: str | None = None
    away_school_name: str | None = None


def invoice_total(
    *,
    base_amount: float,
    revision_amount: float,
    dual_sport_fee: float,
    ranking_services: float,
    c_team_scheduling: float,
    fh_ranking_services: float,
) -> float:
    return round(
        base_amount
        + revision_amount
        + dual_sport_fee
        + ranking_services
        + c_team_scheduling
        + fh_ranking_services,
        2,
    )
