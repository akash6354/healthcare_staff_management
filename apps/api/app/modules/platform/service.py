"""Platform (Oglos staff) operations. Uses the BYPASSRLS role only to create the tenant row; everything
inside the new hospital is written through a normal tenant session so RLS is exercised.

Phase 1 exposes this through the CLI (`python -m app.modules.platform.cli`) and the seed. The
platform-admin web console and its separate auth come in a later phase (docs/open-questions.md).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import Actor, record
from app.core.db import platform_session, tenant_session
from app.core.ids import uuid7
from app.modules.org.models import (
    AreaType,
    Hospital,
    HospitalModule,
    HospitalSettings,
    Module,
    RiskLevel,
)
from app.modules.org.schemas import HospitalSettingsV1

PLATFORM = Actor(None, "platform_admin")

# Template pack: default area types (decision G16-style defaults; hospitals can edit them).
DEFAULT_AREA_TYPES: list[tuple[str, dict[str, str], RiskLevel, dict[str, bool]]] = [
    ("icu", {"en": "ICU", "kn": "ಐಸಿಯು", "hi": "आईसीयू"}, RiskLevel.high, {"before_photo": True}),
    ("ot", {"en": "Operation theatre", "kn": "ಶಸ್ತ್ರಚಿಕಿತ್ಸಾ ಕೊಠಡಿ", "hi": "ऑपरेशन थिएटर"}, RiskLevel.high, {"before_photo": True}),
    ("ward", {"en": "Ward", "kn": "ವಾರ್ಡ್", "hi": "वार्ड"}, RiskLevel.medium, {}),
    ("bed", {"en": "Bed", "kn": "ಹಾಸಿಗೆ", "hi": "बिस्तर"}, RiskLevel.medium, {}),
    ("washroom", {"en": "Washroom", "kn": "ಶೌಚಾಲಯ", "hi": "शौचालय"}, RiskLevel.high, {}),
    ("emergency", {"en": "Emergency", "kn": "ತುರ್ತು ವಿಭಾಗ", "hi": "आपातकालीन"}, RiskLevel.high, {}),
    ("opd", {"en": "OPD", "kn": "ಒಪಿಡಿ", "hi": "ओपीडी"}, RiskLevel.medium, {}),
    ("lab", {"en": "Laboratory", "kn": "ಪ್ರಯೋಗಾಲಯ", "hi": "प्रयोगशाला"}, RiskLevel.medium, {}),
    ("corridor", {"en": "Corridor", "kn": "ಕಾರಿಡಾರ್", "hi": "गलियारा"}, RiskLevel.low, {}),
    ("lobby", {"en": "Lobby", "kn": "ಲಾಬಿ", "hi": "लॉबी"}, RiskLevel.low, {}),
    ("lift_lobby", {"en": "Lift lobby", "kn": "ಲಿಫ್ಟ್ ಲಾಬಿ", "hi": "लिफ्ट लॉबी"}, RiskLevel.low, {}),
    ("kitchen", {"en": "Kitchen", "kn": "ಅಡುಗೆಮನೆ", "hi": "रसोई"}, RiskLevel.medium, {}),
    ("store", {"en": "Store", "kn": "ಉಗ್ರಾಣ", "hi": "भंडार"}, RiskLevel.low, {}),
    ("bmw_store", {"en": "Bio-medical waste store", "kn": "ಜೈವಿಕ-ವೈದ್ಯಕೀಯ ತ್ಯಾಜ್ಯ ಸಂಗ್ರಹ", "hi": "जैव-चिकित्सा अपशिष्ट भंडार"}, RiskLevel.high, {}),
    ("pharmacy_front", {"en": "Pharmacy counter", "kn": "ಔಷಧಾಲಯ ಕೌಂಟರ್", "hi": "फार्मेसी काउंटर"}, RiskLevel.low, {}),
    ("nursing_station", {"en": "Nursing station", "kn": "ನರ್ಸಿಂಗ್ ಸ್ಟೇಷನ್", "hi": "नर्सिंग स्टेशन"}, RiskLevel.medium, {}),
]  # fmt: skip


@dataclass(frozen=True)
class NewHospital:
    id: uuid.UUID
    code: str


async def create_hospital(
    *, code: str, name: str, city: str, modules: list[Module] | None = None
) -> NewHospital:
    hid = uuid7()
    code = code.strip().upper()
    async with platform_session() as ps:
        ps.add(Hospital(id=hid, code=code, name=name, city=city))
    async with tenant_session(hid) as s:
        await _apply_template_pack(s, hid, modules or list(Module))
    return NewHospital(hid, code)


async def _apply_template_pack(s: AsyncSession, hid: uuid.UUID, modules: list[Module]) -> None:
    s.add(
        HospitalSettings(
            hospital_id=hid, schema_version=1, settings=HospitalSettingsV1().model_dump(mode="json")
        )
    )
    for m in Module:
        s.add(HospitalModule(hospital_id=hid, module=m, enabled=m in modules))
    for key, names, risk, rules in DEFAULT_AREA_TYPES:
        s.add(
            AreaType(
                hospital_id=hid, key=key, name_i18n=names, default_risk=risk, evidence_rules=rules
            )
        )
    await s.flush()
    await record(
        s, hospital_id=hid, actor=PLATFORM, entity_type="hospital", entity_id=hid,
        action="hospital.created", payload={"modules": sorted(m.value for m in modules)},
    )  # fmt: skip
