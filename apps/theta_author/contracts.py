"""Provisional authoring contract. Independent of any model/vendor SDK."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

STYLES = ('republicano', 'barroco', 'clasico', 'madera', 'moderno')
Style = Literal['republicano', 'barroco', 'clasico', 'madera', 'moderno']
Mode = Literal['fixed', 'suggested', 'unknown']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Decision(Strict):
    value: float | str | None = None
    mode: Mode = 'unknown'


class Cut(Strict):
    kind: Literal['setback', 'bite']
    front_id: str
    depth_m: float = Field(gt=0, le=50)
    width_m: float | None = Field(default=None, gt=0, le=100)
    end: Literal['start', 'end'] = 'start'

    @model_validator(mode='after')
    def bite_width(self):
        if self.kind == 'bite' and self.width_m is None:
            raise ValueError('Una mordida requiere ancho en este contrato provisional')
        return self


class Massing(Strict):
    corner: bool = False
    delegate_complex: bool = False
    cuts: list[Cut] = Field(default_factory=list, max_length=30)


class Form(Strict):
    geometry_revision: str
    height: Decision = Field(default_factory=Decision)
    floors: Decision = Field(default_factory=Decision)
    style: Decision = Field(default_factory=Decision)
    height_reference: Literal['main_body', 'roof', 'parapet', 'other'] = 'main_body'
    massing: Massing = Field(default_factory=Massing)
    massing_mode: Mode = 'fixed'
    photo_ids: list[str] = Field(default_factory=list, max_length=200)
    notes: str = Field(default='', max_length=10000)
    floor_height_m: float | None = Field(default=None, ge=2, le=6)
    first_floor_different: bool = False
    first_floor_height_m: float | None = Field(default=None, ge=2, le=8)

    @model_validator(mode='after')
    def decisions(self):
        for name in ('height', 'floors', 'style'):
            d = getattr(self, name)
            if d.mode != 'unknown' and d.value is None:
                raise ValueError(f'{name}: falta un valor')
            if d.mode == 'unknown' and d.value is not None:
                raise ValueError(f'{name}: desconocido debe tener valor null')
        if self.height.value is not None and (not isinstance(self.height.value, (float, int)) or not 1 <= self.height.value <= 150):
            raise ValueError('Altura fuera de rango: 1–150 m')
        if self.floors.value is not None and (not isinstance(self.floors.value, (float, int)) or not 1 <= self.floors.value <= 50 or self.floors.value != int(self.floors.value)):
            raise ValueError('Pisos debe ser un entero entre 1 y 50')
        if self.style.value is not None and self.style.value not in STYLES:
            raise ValueError('Estilo desconocido')
        if len(set(self.photo_ids)) != len(self.photo_ids):
            raise ValueError('Fotos duplicadas')
        if self.floor_height_m is not None:
            if self.floors.value is None or self.height.value is None:
                raise ValueError('Los sliders requieren pisos y altura total')
            first = self.first_floor_height_m if self.first_floor_different else self.floor_height_m
            if first is None:
                raise ValueError('Falta altura del primer piso')
            expected = first + (self.floors.value-1)*self.floor_height_m
            if abs(expected-self.height.value) > .001:
                raise ValueError('Altura total incompatible con alturas de pisos')
        return self


class Proposal(Strict):
    schema_version: Literal['authoring-v1'] = 'authoring-v1'
    height_m: float = Field(ge=1, le=150)
    floors: int = Field(ge=1, le=50, strict=True)
    style: Style
    massing: Massing
    levels_m: list[float] | None = None
    # These dimensions are deliberately independent of style.
    construction: str | None = None
    material: str | None = None
    color: str | None = None
    assumptions: list[str] = Field(default_factory=list)
