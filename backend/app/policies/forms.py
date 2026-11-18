"""Policies the demo ships with: the three FEMA Standard Flood Insurance Policy forms, as
published in the Code of Federal Regulations (US government work, public domain).

govinfo.gov serves each appendix as an official PDF; fema.gov blocks automated downloads.
"""

from __future__ import annotations

from dataclasses import dataclass

GOVINFO = "https://www.govinfo.gov/content/pkg/CFR-2025-title44-vol1/pdf/CFR-2025-title44-vol1-part61-{app}.pdf"


@dataclass(frozen=True)
class FormSpec:
    id: str
    appendix: str  # "A(1)"
    file: str  # "appA1"
    title: str
    form: str
    edition: str = "44 CFR Part 61, 2025 edition"
    licence: str = "public-domain"

    @property
    def url(self) -> str:
        return GOVINFO.format(app=self.file)


FORMS = (
    FormSpec(
        "sfip-dwelling",
        "A(1)",
        "appA1",
        "Standard Flood Insurance Policy — Dwelling Form",
        "Dwelling (homes, 1–4 units)",
    ),
    FormSpec(
        "sfip-general-property",
        "A(2)",
        "appA2",
        "Standard Flood Insurance Policy — General Property Form",
        "General Property (commercial and non-residential buildings)",
    ),
    FormSpec(
        "sfip-rcbap",
        "A(3)",
        "appA3",
        "Standard Flood Insurance Policy — Residential Condominium Building Association Policy",
        "RCBAP (condominium associations)",
    ),
)
