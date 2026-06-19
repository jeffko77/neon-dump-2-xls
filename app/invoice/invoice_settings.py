from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InvoicePayee:
    name: str
    address_line1: str
    city_state_zip: str
    email: str
    title: str = "Girls Lacrosse / Field Hockey Scheduler"


DEFAULT_PAYEE = InvoicePayee(
    name="EMILY LOVERCHECK",
    address_line1="444 Royal Village",
    city_state_zip="Manchester, MO 63011",
    email="elovercheck@parkwayschools.net",
)
