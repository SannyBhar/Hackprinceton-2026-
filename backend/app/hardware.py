"""One private measured profile, shared by firmware builds and host preflight."""
import hashlib
import json
import os
from pathlib import Path
from pydantic import BaseModel, Field, StrictBool, StrictInt, model_validator

ROOT = Path(__file__).resolve().parents[2]


class HardwareProfile(BaseModel):
    cellCm: StrictInt = 22
    supplyVolts: StrictInt = 6
    motorRatingVerified: StrictBool = False
    wiringVerified: StrictBool = False
    polarity: list[StrictInt | None] = Field(default_factory=lambda:[None]*4, min_length=4,max_length=4)
    msPerCell: StrictInt | None = Field(default=None, ge=1, le=8000)
    msPer90: StrictInt | None = Field(default=None, ge=1, le=8000)
    driveDuty: StrictInt | None = Field(default=None, ge=1, le=200)
    turnDuty: StrictInt | None = Field(default=None, ge=1, le=200)
    acknowledged: StrictBool = False

    @model_validator(mode='after')
    def validate_polarity(self):
        if any(p not in (-1,1,None) for p in self.polarity):
            raise ValueError('polarity must be -1, 1, or unmeasured (null), in LF/RF/LR/RR order')
        if self.cellCm != 22 or self.supplyVolts != 6:
            raise ValueError('this hardware profile requires the verified 22 cm / 6 V configuration')
        return self

    @property
    def calibrated(self):
        return (self.motorRatingVerified and self.wiringVerified and self.acknowledged and
                all(p in (-1,1) for p in self.polarity) and
                all(v is not None for v in (self.msPerCell,self.msPer90,self.driveDuty,self.turnDuty)))

    @property
    def profile_id(self):
        return hashlib.sha256(json.dumps(self.model_dump(),sort_keys=True).encode()).hexdigest()[:16]


def load_profile():
    path = Path(os.environ.get('GRASSROOT_HARDWARE_PROFILE',ROOT/'hardware.local.json'))
    return HardwareProfile.model_validate_json(path.read_text())
