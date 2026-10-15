"""Contratos de cada turno: el modelo nunca reemplaza el request completo."""
from pathlib import Path
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'house_grammar/src'))

from domain.theta import (ArchitecturalMass, RoofControls, RoofOverride, SiteControls,
                          TrimControls, MaterialControl, PlanRegion, SupportControls)
from domain.models import Opening, FacadeProjection, FacadeTopProfile, FacadeMaterialRegion
from domain.balconies import BalconyControls
from domain.vertical_members import VerticalMemberControls
from domain.crowns import CrownControls, EntablatureControls
from domain.roof_details import RoofAssemblyControls, CanopyControls
from domain.entrances import EntranceControls

Style = Literal['republicano', 'barroco', 'clasico', 'madera', 'moderno']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Evidence(Strict):
    element: str
    view_ids: list[str]
    status: Literal['observed', 'inferred', 'unknown']
    description: str


class InventoryItem(Strict):
    id: str
    category: Literal['mass', 'door', 'window', 'balcony', 'member', 'crown', 'roof', 'site', 'material']
    location: str
    description: str
    view_ids: list[str]
    certainty: Literal['observed', 'inferred', 'unknown']


class Reading(Strict):
    target_description: str
    inventory: list[InventoryItem]
    occlusions: list[str]


class Body(Strict):
    id: str
    region: PlanRegion
    levels_m: list[float]
    kind: Literal['enclosed','open'] = 'enclosed'
    cutouts: list[PlanRegion] = Field(default_factory=list)
    support: SupportControls = Field(default_factory=SupportControls)


class Masses(Strict):
    floor_levels_m: list[float] = Field(description='Cotas globales de pisos: N pisos → N+1 cotas, desde 0.')
    components: list[Body] | None = Field(default=None, description='Preferido: regiones relativas al frente; el motor calcula XY.')
    masses: list[ArchitecturalMass] | None = Field(default=None, description='Alternativa explícita cuando ya se conocen vértices XY.')

    @model_validator(mode='after')
    def one_geometry_mode(self):
        if (self.components is None) == (self.masses is None):
            raise ValueError('Elegir exactamente una colección: components o masses.')
        return self


class Language(Strict):
    architectural_style: Style | None


class OpeningPlacement(Strict):
    id: str = Field(description='ID de autoría, fuera del contrato theta; único entre puertas y ventanas.')
    mass_ref: str
    edge: int = Field(ge=0, strict=True)
    opening: Opening


class Openings(Strict):
    placements: list[OpeningPlacement]


class Balconies(Strict):
    balconies: list[BalconyControls]


class Members(Strict):
    vertical_members: list[VerticalMemberControls]


class WallDetail(Strict):
    mass_ref: str
    edge: int = Field(ge=0, strict=True)
    top_profile: FacadeTopProfile | None = None
    projections: list[FacadeProjection] = Field(default_factory=list)


class Crowns(Strict):
    crowns: list[CrownControls]
    entablatures: list[EntablatureControls]
    trim: TrimControls
    wall_details: list[WallDetail]


class Roofs(Strict):
    roof: RoofControls
    roofs: list[RoofOverride]
    roof_assemblies: list[RoofAssemblyControls]
    canopies: list[CanopyControls]


class Site(Strict):
    site: SiteControls
    entrances: list[EntranceControls]


class WallMaterials(Strict):
    mass_ref: str
    edge: int = Field(ge=0, strict=True)
    material_regions: list[FacadeMaterialRegion]


class Materials(Strict):
    primary_color: tuple[float, float, float] | None
    side_material: Literal['brick', 'concrete', 'plaster']
    materials: list[MaterialControl]
    wall_materials: list[WallMaterials]


class Finding(Strict):
    target_stage: str
    element: str
    issue: str
    requested_change: str
    view_ids: list[str]


class Review(Strict):
    verdict: Literal['accept', 'revise', 'insufficient_evidence']
    findings: list[Finding]
    limitations: list[str]


STAGES = {
    '01_lectura': Reading,
    '02_masas': Masses,
    '03_lenguaje': Language,
    '04_puertas': Openings,
    '05_ventanas': Openings,
    '06_balcones': Balconies,
    '07_miembros': Members,
    '08_remates': Crowns,
    '09_cubiertas': Roofs,
    '10_sitio': Site,
    '11_materiales': Materials,
    '12_revision': Review,
}


def response_model(stage):
    return create_model('Response_' + stage, __base__=Strict,
        stage=(Literal[stage], ...), changes=(STAGES[stage], ...),
        evidence=(list[Evidence], ...), notes=(list[str], ...), blockers=(list[str], ...))


def response_schema(stage):
    schema = response_model(stage).model_json_schema()

    def close_objects(node):
        if isinstance(node, dict):
            if node.get('type') == 'object' and 'properties' in node:
                node['additionalProperties'] = False
            for value in node.values():
                close_objects(value)
        elif isinstance(node, list):
            for value in node:
                close_objects(value)

    close_objects(schema)
    return schema
