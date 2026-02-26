from dataclasses import dataclass


@dataclass
class IndustryDef:
    name: str
    keywords: list[str]
    naics_codes: list[str]
    sub_industries: list[str]


INDUSTRIES: dict[str, IndustryDef] = {
    "Aerospace & Defense": IndustryDef(
        name="Aerospace & Defense",
        keywords=["aerospace", "defense", "aviation", "aircraft parts", "missile systems",
                  "satellite", "space systems", "military equipment", "avionics"],
        naics_codes=["3364", "3369", "3345"],
        sub_industries=["Aircraft Parts", "Defense Electronics", "Space Systems",
                        "Avionics", "Military Vehicles", "Missile Systems"],
    ),
    "Industrial Machinery & Equipment": IndustryDef(
        name="Industrial Machinery & Equipment",
        keywords=["industrial machinery", "manufacturing equipment", "CNC machines",
                  "pumps", "compressors", "turbines", "conveyor systems", "hydraulic equipment"],
        naics_codes=["3331", "3332", "3333", "3334"],
        sub_industries=["CNC Machinery", "Pumps & Compressors", "Conveyor Systems",
                        "Turbines", "Hydraulic Equipment", "Material Handling"],
    ),
    "Specialty Chemicals": IndustryDef(
        name="Specialty Chemicals",
        keywords=["specialty chemicals", "chemical manufacturing", "adhesives", "coatings",
                  "polymers", "catalysts", "lubricants", "sealants", "resins"],
        naics_codes=["3251", "3252", "3253", "3255", "3259"],
        sub_industries=["Adhesives & Sealants", "Coatings", "Polymers & Resins",
                        "Catalysts", "Lubricants", "Industrial Gases"],
    ),
    "Commodity Trading": IndustryDef(
        name="Commodity Trading",
        keywords=["commodity trading", "metals trading", "raw materials", "steel trading",
                  "aluminum trading", "copper trading", "commodity broker", "bulk materials"],
        naics_codes=["4234", "4235"],
        sub_industries=["Metals Trading", "Energy Commodities", "Agricultural Commodities",
                        "Bulk Materials", "Precious Metals", "Industrial Minerals"],
    ),
    "Medical & Scientific Equipment": IndustryDef(
        name="Medical & Scientific Equipment",
        keywords=["medical equipment", "scientific instruments", "laboratory equipment",
                  "diagnostic equipment", "surgical instruments", "medical devices", "analytical instruments"],
        naics_codes=["3391", "3345"],
        sub_industries=["Diagnostic Equipment", "Surgical Instruments", "Lab Equipment",
                        "Analytical Instruments", "Patient Monitoring", "Imaging Systems"],
    ),
    "Building Materials": IndustryDef(
        name="Building Materials",
        keywords=["building materials", "construction materials", "lumber", "concrete",
                  "roofing", "insulation", "drywall", "cement", "structural steel"],
        naics_codes=["3273", "3274", "3211", "3221"],
        sub_industries=["Concrete & Cement", "Lumber & Wood", "Roofing Materials",
                        "Insulation", "Structural Steel", "Glass & Glazing"],
    ),
    "Electrical & Electronic Hardware": IndustryDef(
        name="Electrical & Electronic Hardware",
        keywords=["electrical components", "electronic hardware", "connectors", "circuit boards",
                  "transformers", "switches", "relays", "power supplies", "semiconductors"],
        naics_codes=["3344", "3353", "3359"],
        sub_industries=["Connectors", "Circuit Boards", "Transformers",
                        "Switches & Relays", "Power Supplies", "Semiconductors"],
    ),
}
