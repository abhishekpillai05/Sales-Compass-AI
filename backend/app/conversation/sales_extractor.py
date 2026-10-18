"""
Sales Conversation Requirement Extraction and Follow-up Question Generation.

Provides category-specific product requirement extraction, missing attribute
detection, focused follow-up question formulation, and catalogue matching readiness.
"""
import re
from typing import Dict, Any, List, Optional, Tuple

from app.generation.llm import generate_llm_response
from app.logging.config import get_logger

logger = get_logger(__name__)

# Category definitions and their relevant attributes in priority order
CATEGORY_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "ladder": {
        "label": "Ladders & Access Equipment",
        "keywords": ["ladder", "ladders", "step ladder", "extension ladder", "stepladder", "scaffold"],
        "attributes": [
            {
                "key": "height",
                "label": "Height / Size",
                "question": "What working height or ladder size do you need (e.g. 6 ft, 8 ft, 10 ft, 12 ft)?",
                "patterns": [r"(\b\d{1,2}\s*(?:ft|feet|foot|meter|m)\b)", r"(\b\d{1,2}['\"]\b)"],
            },
            {
                "key": "material",
                "label": "Material",
                "question": "What material do you prefer (e.g. non-conductive fiberglass for electrical work, or lightweight aluminum)?",
                "patterns": [r"\b(fiberglass|aluminium|aluminum|wood|steel)\b"],
            },
            {
                "key": "load_capacity",
                "label": "Load Capacity / Duty Rating",
                "question": "What load capacity or duty rating is required (e.g. 250 lbs Type I, 300 lbs Type IA, or 375 lbs Type IAA)?",
                "patterns": [
                    r"(\b\d{3}\s*(?:lbs?|pounds?|kg)\b)",
                    r"\b(type\s*i{1,3}[a-z]?|commercial|heavy\s*duty|industrial|duty\s*rating)\b",
                ],
            },
            {
                "key": "application",
                "label": "Intended Application",
                "question": "What is the intended application or job environment (e.g. electrical work, painting, warehouse, roofing)?",
                "patterns": [r"\b(electrical|electrician|painting|painter|roofing|warehouse|construction|indoor|outdoor|diy)\b"],
            },
            {
                "key": "brand",
                "label": "Preferred Brand",
                "question": "Do you have a preferred manufacturer or brand (e.g. Werner, Louisville, Little Giant, or any)?",
                "patterns": [r"\b(werner|louisville|little\s*giant|bauer|gorilla)\b"],
            },
            {
                "key": "budget",
                "label": "Budget Range",
                "question": "Do you have a target budget per unit?",
                "patterns": [r"(\$\s*\d+(?:\.\d+)?|\b\d+\s*(?:dollars?|usd|euro|eur)\b|under\s*\$?\s*\d+)"],
            },
            {
                "key": "quantity",
                "label": "Quantity",
                "question": "How many units do you require?",
                "patterns": [r"\b(\d+)\s*(?:units?|pieces?|ladders?|qty|pcs)\b", r"\b(?:need|want|order)\s*(\d+)\b"],
            },
        ],
    },
    "floor_scrubber": {
        "label": "Floor Scrubbers & Cleaning Machines",
        "keywords": ["scrubber", "scrubbers", "scrubber-dryer", "floor cleaning", "floor scrubber", "cleaning machine", "karcher", "kärcher"],
        "attributes": [
            {
                "key": "machine_type",
                "label": "Machine Type",
                "question": "Are you looking for a walk-behind scrubber-dryer or a larger ride-on machine?",
                "patterns": [r"\b(walk-behind|walk\s*behind|ride-on|ride\s*on|compact|step-on)\b"],
            },
            {
                "key": "capacity_or_width",
                "label": "Tank Capacity / Working Width",
                "question": "What tank capacity or working width do you require (e.g. 40-50 litre, 43cm disc brush)?",
                "patterns": [r"(\b\d{1,3}\s*(?:litre|liter|l|gal|gallons?)\b)", r"(\b\d{2,3}\s*(?:cm|mm|inch|in)\b)"],
            },
            {
                "key": "power_source",
                "label": "Power Source",
                "question": "Do you prefer a battery-powered model (cordless mobility) or mains cable-operated power?",
                "patterns": [r"\b(battery|cordless|cable|mains|electric|lithium|li-ion)\b"],
            },
            {
                "key": "application",
                "label": "Floor Type / Area",
                "question": "What floor surface or facility type will you be cleaning (e.g. warehouse concrete, retail tiles, hospital)?",
                "patterns": [r"\b(warehouse|factory|retail|hospital|concrete|tiles?|epoxy|vinyl|hard\s*floors?)\b"],
            },
            {
                "key": "brand",
                "label": "Preferred Brand",
                "question": "Do you have a preferred manufacturer (e.g. Kärcher, Tennant, Nilfisk)?",
                "patterns": [r"\b(karcher|kärcher|tennant|nilfisk|clarke|taski)\b"],
            },
            {
                "key": "budget",
                "label": "Budget Range",
                "question": "What is your target budget for this equipment?",
                "patterns": [r"(\$\s*\d+(?:\.\d+)?|\b\d+\s*(?:dollars?|usd|euro|eur)\b|under\s*\$?\s*\d+)"],
            },
            {
                "key": "quantity",
                "label": "Quantity",
                "question": "How many units are you looking to purchase?",
                "patterns": [r"\b(\d+)\s*(?:units?|machines?|scrubbers?|qty|pcs)\b", r"\b(?:need|want|order)\s*(\d+)\b"],
            },
        ],
    },
    "vacuum_cleaner": {
        "label": "Industrial Vacuum Cleaners",
        "keywords": ["vacuum", "vacuums", "dust extractor", "wet and dry", "wet & dry", "vacuum cleaner"],
        "attributes": [
            {
                "key": "vacuum_type",
                "label": "Vacuum Type",
                "question": "Do you need a wet & dry vacuum cleaner, or a dry-only / HEPA filtration dust extractor?",
                "patterns": [r"\b(wet\s*(?:and|&)\s*dry|dry\s*only|hepa|dust\s*extractor|hazardous\s*dust)\b"],
            },
            {
                "key": "capacity",
                "label": "Container Capacity",
                "question": "What container capacity do you need (e.g. 30L, 40L, 50L)?",
                "patterns": [r"(\b\d{1,3}\s*(?:litre|liter|l|gal)\b)"],
            },
            {
                "key": "brand",
                "label": "Preferred Brand",
                "question": "Do you have a preferred brand (e.g. Kärcher, Nilfisk, Bosch)?",
                "patterns": [r"\b(karcher|kärcher|nilfisk|bosch|makita|dewalt|festool)\b"],
            },
            {
                "key": "budget",
                "label": "Budget Range",
                "question": "What is your budget per unit?",
                "patterns": [r"(\$\s*\d+(?:\.\d+)?|\b\d+\s*(?:dollars?|usd|euro|eur)\b|under\s*\$?\s*\d+)"],
            },
            {
                "key": "quantity",
                "label": "Quantity",
                "question": "How many units do you need?",
                "patterns": [r"\b(\d+)\s*(?:units?|vacuums?|qty|pcs)\b", r"\b(?:need|want|order)\s*(\d+)\b"],
            },
        ],
    },
    "networking": {
        "label": "Networking & IT Infrastructure",
        "keywords": ["router", "routers", "switch", "switches", "access point", "firewall", "networking"],
        "attributes": [
            {
                "key": "device_type",
                "label": "Device Type",
                "question": "Are you looking for an industrial router, a managed network switch, a firewall, or an access point?",
                "patterns": [r"\b(router|switch|firewall|access\s*point|gateway)\b"],
            },
            {
                "key": "ports_or_speed",
                "label": "Ports / Throughput",
                "question": "What port count or speed is required (e.g. 24-port Gigabit, PoE+, 10G uplink)?",
                "patterns": [r"(\b\d{1,2}\s*(?:ports?|pt)\b)", r"\b(gigabit|10g|poe\+?|fast\s*ethernet)\b"],
            },
            {
                "key": "brand",
                "label": "Preferred Brand",
                "question": "Which manufacturer do you prefer (e.g. Cisco, Fortinet, Aruba)?",
                "patterns": [r"\b(cisco|fortinet|aruba|juniper|ubiquiti|netgear)\b"],
            },
            {
                "key": "budget",
                "label": "Budget Range",
                "question": "What is your target budget for this equipment?",
                "patterns": [r"(\$\s*\d+(?:\.\d+)?|\b\d+\s*(?:dollars?|usd|euro|eur)\b|under\s*\$?\s*\d+)"],
            },
            {
                "key": "quantity",
                "label": "Quantity",
                "question": "How many units do you need?",
                "patterns": [r"\b(\d+)\s*(?:units?|devices?|qty|pcs)\b", r"\b(?:need|want|order)\s*(\d+)\b"],
            },
        ],
    },
    "general": {
        "label": "General Equipment & Products",
        "keywords": [],
        "attributes": [
            {
                "key": "specifications",
                "label": "Key Specifications / Size",
                "question": "What specific size, capacity, or performance specifications do you need?",
                "patterns": [],
            },
            {
                "key": "application",
                "label": "Intended Application",
                "question": "What is the primary application or operational environment?",
                "patterns": [],
            },
            {
                "key": "brand",
                "label": "Preferred Brand",
                "question": "Do you have a preferred manufacturer or brand?",
                "patterns": [],
            },
            {
                "key": "budget",
                "label": "Budget Range",
                "question": "What is your budget range?",
                "patterns": [r"(\$\s*\d+(?:\.\d+)?|\b\d+\s*(?:dollars?|usd|euro|eur)\b|under\s*\$?\s*\d+)"],
            },
            {
                "key": "quantity",
                "label": "Quantity",
                "question": "How many units do you require?",
                "patterns": [r"\b(\d+)\s*(?:units?|pieces?|items?|qty|pcs)\b", r"\b(?:need|want|order)\s*(\d+)\b"],
            },
        ],
    },
}

# Neutral / skip signals indicating user does not have a preference for an attribute
SKIP_PATTERNS = [
    r"\b(?:no|none|any|skip|doesn'?t\s*matter|don'?t\s*(?:care|mind|know)|no\s*preference|either)\b",
    r"\b(?:whatever|standard|regular|standard\s*is\s*fine|not\s*sure)\b",
]


def is_skip_response(text: str) -> bool:
    """Check if the user response indicates skipping or having no preference."""
    t = text.lower().strip()
    for pat in SKIP_PATTERNS:
        if re.search(pat, t):
            return True
    return False


def detect_product_category(text: str, current_category: Optional[str] = None) -> str:
    """
    Detect the product category from text or retain the current one.
    """
    t_lower = text.lower()
    for cat_id, cat_info in CATEGORY_SCHEMAS.items():
        if cat_id == "general":
            continue
        for kw in cat_info["keywords"]:
            if kw in t_lower:
                return cat_id

    if current_category and current_category in CATEGORY_SCHEMAS:
        return current_category

    # Fallback heuristic
    if any(w in t_lower for w in ["clean", "wash", "scrub", "sweep"]):
        return "floor_scrubber"
    if any(w in t_lower for w in ["climb", "reach", "rung", "ladder"]):
        return "ladder"
    if any(w in t_lower for w in ["router", "switch", "ethernet", "port"]):
        return "networking"

    return current_category or "general"


def extract_regex_attributes(
    category_id: str,
    text: str,
    existing_requirements: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract attributes using schema regex patterns.
    Handles multi-attribute inputs in a single sentence.
    """
    extracted: Dict[str, Any] = {}
    schema = CATEGORY_SCHEMAS.get(category_id, CATEGORY_SCHEMAS["general"])

    for attr in schema["attributes"]:
        key = attr["key"]
        # Skip if already extracted with a meaningful value
        if existing_requirements.get(key) and existing_requirements[key] not in ("None", "Unspecified"):
            continue

        for pattern in attr.get("patterns", []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                # Clean value if necessary
                if key == "quantity":
                    try:
                        extracted[key] = int(val)
                    except ValueError:
                        extracted[key] = val
                else:
                    extracted[key] = val
                break

    # General quantity extractor fallback
    if "quantity" not in extracted and not existing_requirements.get("quantity"):
        q_match = re.search(r"\b(?:need|want|order|quantity|qty)\s*(?:is|of)?\s*(\d+)\b", text, re.IGNORECASE)
        if q_match:
            try:
                extracted["quantity"] = int(q_match.group(1))
            except ValueError:
                pass

    # General budget extractor fallback
    if "budget" not in extracted and not existing_requirements.get("budget"):
        b_match = re.search(r"(?:budget\s*(?:is|of)?\s*|under\s*|around\s*)(\$\s*\d+(?:\.\d+)?|\d+\s*(?:dollars?|usd))", text, re.IGNORECASE)
        if b_match:
            extracted["budget"] = b_match.group(1).strip()

    return extracted


def extract_attributes_llm(
    category_id: str,
    query: str,
    existing_requirements: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Use LLM to extract structured attributes when complex natural language is used.
    Combines with regex for maximum recall and precision.
    """
    schema = CATEGORY_SCHEMAS.get(category_id, CATEGORY_SCHEMAS["general"])
    attr_keys = [a["key"] for a in schema["attributes"]]
    missing_keys = [k for k in attr_keys if not existing_requirements.get(k)]

    if not missing_keys:
        return {}

    system_prompt = (
        "You are an expert sales attribute extractor for product catalogs.\n"
        f"The product category is: {schema['label']}.\n"
        f"Extract any of the following missing attributes if mentioned in the user message:\n"
        f"{', '.join(missing_keys)}\n\n"
        "Rules:\n"
        "1. Return ONLY a valid JSON object of key-value pairs (e.g. {\"height\": \"8 ft\", \"material\": \"fiberglass\"}).\n"
        "2. Only extract information explicitly mentioned or clearly implied by the user.\n"
        "3. If an attribute was not mentioned, DO NOT include it in the JSON.\n"
        "4. If the user indicates they don't care, have no preference, or want to skip an attribute, set its value to 'No preference'.\n"
        "5. Do NOT include any markdown, explanation, or extra keys."
    )

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User message: {query}"},
        ]
        response = generate_llm_response(messages=messages, temperature=0.0)
        # Parse JSON
        import json
        clean_resp = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
        clean_resp = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean_resp, flags=re.MULTILINE).strip()
        parsed = json.loads(clean_resp)
        if isinstance(parsed, dict):
            # Only keep valid missing keys
            return {k: v for k, v in parsed.items() if k in missing_keys and v is not None}
    except Exception as exc:
        logger.warning("extract_attributes_llm failed: %s", exc)

    return {}


def extract_requirements(
    text: str,
    category_id: str,
    existing_requirements: Dict[str, Any],
) -> Tuple[Dict[str, Any], bool]:
    """
    Unified extractor combining regex and LLM parsing.
    Returns (updated_requirements, has_new_updates).
    """
    merged = dict(existing_requirements)
    has_updates = False

    # Check for skip on latest question
    if is_skip_response(text):
        # Find the first missing attribute from the schema and mark as 'No preference'
        schema = CATEGORY_SCHEMAS.get(category_id, CATEGORY_SCHEMAS["general"])
        for attr in schema["attributes"]:
            k = attr["key"]
            if not merged.get(k):
                merged[k] = "No preference"
                has_updates = True
                break

    # 1. Fast regex extraction
    regex_extracted = extract_regex_attributes(category_id, text, merged)
    for k, v in regex_extracted.items():
        if v and merged.get(k) != v:
            merged[k] = v
            has_updates = True

    # 2. LLM extraction for natural language nuances if text contains substance
    if len(text.split()) > 2:
        llm_extracted = extract_attributes_llm(category_id, text, merged)
        for k, v in llm_extracted.items():
            if v and merged.get(k) != v:
                merged[k] = v
                has_updates = True

    return merged, has_updates


def get_next_follow_up_questions(
    category_id: str,
    current_requirements: Dict[str, Any],
    max_questions: int = 2,
) -> List[Dict[str, str]]:
    """
    Identify missing attributes and select the top 1-2 most useful follow-up questions.
    Never asks for attributes already supplied.
    """
    schema = CATEGORY_SCHEMAS.get(category_id, CATEGORY_SCHEMAS["general"])
    missing: List[Dict[str, str]] = []

    for attr in schema["attributes"]:
        key = attr["key"]
        val = current_requirements.get(key)
        # If not supplied or empty
        if not val or str(val).strip() in ("", "None", "Unspecified"):
            missing.append({
                "key": key,
                "label": attr["label"],
                "question": attr["question"],
            })
            if len(missing) >= max_questions:
                break

    return missing


def has_sufficient_information_for_matching(
    category_id: str,
    requirements: Dict[str, Any],
) -> bool:
    """
    Determine if enough key requirements have been gathered to recommend catalogue products.
    For ladders: e.g. Height AND (Material OR Application) OR at least 2 key specs.
    For scrubbers: e.g. Machine type OR Capacity OR Floor surface.
    """
    if not requirements:
        return False

    answered_keys = [
        k for k, v in requirements.items()
        if v and str(v).lower() not in ("none", "unspecified")
    ]

    if category_id == "ladder":
        # At least height plus one other attribute, or 2+ specific attributes
        has_height = bool(requirements.get("height"))
        has_material = bool(requirements.get("material"))
        has_application = bool(requirements.get("application"))
        has_capacity = bool(requirements.get("load_capacity"))
        if (has_height and (has_material or has_application or has_capacity)) or len(answered_keys) >= 2:
            return True

    elif category_id == "floor_scrubber":
        has_type = bool(requirements.get("machine_type"))
        has_cap = bool(requirements.get("capacity_or_width"))
        has_surface = bool(requirements.get("application"))
        if (has_type or has_cap or has_surface) and len(answered_keys) >= 2:
            return True

    elif category_id == "vacuum_cleaner":
        if len(answered_keys) >= 2:
            return True

    elif category_id == "networking":
        if len(answered_keys) >= 2:
            return True

    # General fallback: at least 2 attributes answered
    return len(answered_keys) >= 2
