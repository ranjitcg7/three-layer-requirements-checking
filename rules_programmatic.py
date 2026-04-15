# backend/app/services/rules_programmatic.py

from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Pattern, Set
import re

from app.core.schemas import RuleViolation

# -----------------------------------------------------------------------------
# Characteristics impacted (from Appendix E Rules to Characteristics matrix)
# -----------------------------------------------------------------------------
# NOTE: Keeping this as C-codes only (C1..C15) so we don't invent/rename labels.
RULE_TO_CHARACTERISTICS = {
    "R1": ["C1", "C2", "C3", "C4", "C5"],
    "R2": ["C1", "C2", "C3", "C4"],
    "R3": ["C1", "C2", "C3", "C4", "C5"],
    "R4": ["C1", "C2", "C3", "C4", "C5", "C6"],
    "R5": ["C1", "C2"],
    "R6": ["C1", "C2", "C3", "C4"],
    "R7": ["C1", "C2", "C3"],
    "R8": ["C1", "C2"],
    "R9": ["C1", "C2", "C3", "C4"],
    "R10": ["C1", "C2"],
    "R11": ["C1", "C2", "C3", "C4"],
    "R12": ["C1", "C2", "C3", "C4"],
    "R13": ["C1", "C2"],
    "R14": ["C1", "C2"],
    "R15": ["C1", "C2"],
    "R16": ["C1", "C2", "C3"],
    "R17": ["C1", "C2"],
    "R18": ["C1", "C2", "C3", "C4", "C5"],
    "R19": ["C1", "C2"],
    "R20": ["C1", "C2"],
    "R21": ["C1"],
    "R22": ["C1", "C2"],
    "R23": ["C1", "C2", "C3"],
    "R24": ["C1", "C2", "C3"],
    "R25": ["C1"],
    "R26": ["C1", "C2", "C3", "C4"],
    "R27": ["C1", "C2", "C3"],
    "R28": ["C1", "C2"],
    "R29": ["C1", "C2"],
    "R30": ["C1", "C2", "C3"],
    "R31": ["C1"],
    "R32": ["C1", "C2", "C3"],
    "R33": ["C1", "C2", "C3", "C4", "C5", "C6"],
    "R34": ["C1", "C2", "C3", "C4"],
    "R35": ["C1", "C2", "C3"],
    "R36": ["C1", "C2", "C3", "C4", "C5", "C6", "C7"],
    "R37": ["C1", "C2", "C3", "C4", "C5", "C6"],
    "R38": ["C1", "C2", "C3", "C4", "C5"],
    "R39": ["C1", "C2", "C3", "C4", "C5", "C6", "C7"],
    "R40": ["C1", "C2", "C3", "C4"],
    "R41": ["C1", "C2", "C3", "C4", "C5", "C6"],
    "R42": ["C1", "C2", "C3", "C4", "C5"],
}


# Only rules marked Prog=✓ in "42 Rules detection methods.xlsx" are registered
# in this module's aggregate check registry.
PROGRAMMATIC_RULE_IDS = (
    "R1",
    "R4",
    "R6",
    "R7",
    "R8",
    "R9",
    "R10",
    "R13",
    "R14",
    "R16",
    "R17",
    "R19",
    "R20",
    "R21",
    "R26",
    "R30",
    "R32",
    "R35",
    "R36",
    "R37",
    "R38",
    "R39",
    "R40",
)


# -----------------------------------------------------------------------------
# Helper phrase lists (from the Guide)
# -----------------------------------------------------------------------------
# R7 - Vague Terms (explicit lists from rule text)
R7_VAGUE_QUANTIFICATION = [
    "some",
    "any",
    "allowable",
    "several",
    "many",
    "a lot of",
    "a few",
    "almost always",
    "very nearly",
    "nearly",
    "about",
    "close to",
    "almost",
    "approximate",
]

R7_VAGUE_ADJECTIVES = [
    "ancillary",
    "relevant",
    "routine",
    "common",
    "generic",
    "significant",
    "flexible",
    "expandable",
    "typical",
    "sufficient",
    "adequate",
    "appropriate",
    "efficient",
    "effective",
    "proficient",
    "reasonable",
    "customary",
]

R7_VAGUE_ADVERBS = [
    "usually",
    "approximately",
    "sufficiently",
    "typically",
]

# R8 - Escape Clauses (explicit list from short description table)
R8_ESCAPE_CLAUSES = [
    "so far as is possible",
    "as little as possible",
    "where possible",
    "as much as possible",
    "if it should prove necessary",
    "if necessary",
    "to the extent necessary",
    "as appropriate",
    "as required",
    "to the extent practical",
    "if practicable",
]

# R9 - Open-ended Clauses (explicit list from definition)
R9_OPEN_ENDED = [
    "including but not limited to",
    "etc.",
    "and so on",
]

# R10 - Superfluous infinitives (explicit list from definition)
R10_SUPERFLUOUS_INFINITIVES = [
    "to be designed to",
    "to be able to",
    "to be capable of",
    "to enable",
    "to allow",
]

# R19 - Combinators (explicit list from Definition)
R19_COMBINATORS = [
    "and",
    "or",
    "then",
    "unless",
    "but",
    "as well as",
    "but also",
    "however",
    "whether",
    "meanwhile",
    "whereas",
    "on the other hand",
    "otherwise",
]

# R20 - Purpose Phrases (phrases called out in Definition + Elaboration)
R20_PURPOSE_PHRASES = [
    "purpose of",
    "intent of",
    "reason for",
    "in order to",
    "so that",
    "thus allowing",
]

# R13 - Correct spelling (project-specific; examples in the Guide)
# NOTE: The Guide shows homophone/word-confusion examples; full spell-checking is typically tool/project-specific.
R13_SPELLING_EXAMPLE_TERMS = [
    "ordinance",  # example confusion: ordinance vs ordnance
]

# R14 - Correct punctuation (example pattern from the Guide)
R14_EXAMPLE_BAD_COMMA_PATTERNS = [
    ", engaged in",
]

# R4 / R36 / R39 depend on project-level context defined by the organization.
PROJECT_GLOSSARY_TERMS: Set[str] = set()
PROJECT_ALLOWED_UNITS: Set[str] = set()
PROJECT_ALLOWED_ACRONYMS: Set[str] = set()
PROJECT_ALLOWED_ABBREVIATIONS: Set[str] = set()
PROJECT_STYLE_GUIDE_PATTERNS: List[Pattern[str]] = []

# R21 - Parentheses
# Definition (from the Guide): Avoid the use of parentheses or brackets for subordinate text.
# (We only need to detect the presence of parentheses/brackets; deeper semantics belong to LLM.)
R21_PAREN_PATTERN = re.compile(r"[\(\)\[\]]")

# R22 - Enumeration
# Definition (from the Guide): Enumerate lists of items after a group noun, rather than leaving a group noun ambiguous.
# Keep this list minimal and grounded in the Guide’s examples/wording (no invented domain terms).
R22_GROUP_NOUN_CANDIDATES = [
    "functions",
    "information",
]

# R26 - Absolutes (explicit examples given in R26 elaboration)
R26_ABSOLUTE_WORDS = [
    "all",
    "every",
    "always",
    "never",
]
R26_PERCENT_100_PATTERN = re.compile(r"\b100\s*%|\b100\s*percent\b", re.IGNORECASE)

# R27 / R28 use simple structural cues (condition + multiple actions)
R27_CONDITION_STARTERS = ["when", "if"]

# A small helper for detecting multiple requirement actions in one statement
_SHALL_PATTERN = re.compile(r"\bshall\b", re.IGNORECASE)


# R32 - Universal Qualification (explicit short description)
R32_UNIVERSAL_BAD = ["all", "any", "both"]
R32_UNIVERSAL_PREFERRED = "each"

# R35 - Temporal Dependencies (explicit list from short description)
R35_INDEFINITE_TEMPORAL_KEYWORDS = [
    "eventually",
    "until",
    "before",
    "after",
    "as",
    "once",
    "earliest",
    "latest",
    "instantaneous",
    "simultaneous",
    "at last",
]

# R40 - Decimal Format (see R40 elaboration/examples)
R40_LEADING_DECIMAL_PATTERN = re.compile(r"(?<!\d)\.(\d+)")  # e.g., ".99"
R40_LEADING_DECIMAL_COMMA_PATTERN = re.compile(r"(?<!\d),(\d+)")  # e.g., ",99"
R40_NEGATIVE_LEADING_DECIMAL_COMMA_PATTERN = re.compile(r"-(\s*)?,(\d+)")
R40_NUMERIC_TOKEN_PATTERN = re.compile(r"\b\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d+)?\b")
R4_GLOSSARY_STYLE_TERM_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b")
R36_MEASURED_UNIT_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s*([A-Za-z%°]+(?:/[A-Za-z%°]+)?)\b")


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------
def _chars_for(rule_id: str) -> str:
    chars = RULE_TO_CHARACTERISTICS.get(rule_id, [])
    return ", ".join(chars) if chars else "N/A"


def _mk_violation(
    rule_id: str,
    rule_name: str,
    issue: str,
    suggestion: str,
    source: str = "python",
) -> RuleViolation:
    return RuleViolation(
        rule_id=rule_id,
        rule_name=rule_name,
        issue=issue,
        suggestion=f"{suggestion} (Characteristics impacted: {_chars_for(rule_id)})",
        source=source,
    )


def _contains_phrase(text_lc: str, phrase_lc: str) -> bool:
    # Simple containment for multi-word phrases; word-boundary checks are done in callers when needed.
    return phrase_lc in text_lc


def configure_programmatic_resources(
    *,
    glossary_terms: Optional[Iterable[str]] = None,
    allowed_units: Optional[Iterable[str]] = None,
    allowed_acronyms: Optional[Iterable[str]] = None,
    allowed_abbreviations: Optional[Iterable[str]] = None,
    style_guide_patterns: Optional[Iterable[str]] = None,
) -> None:
    """
    Configure project-specific resources needed by PDF-defined programmatic rules
    such as R4, R36, R38, and R39.
    """
    global PROJECT_GLOSSARY_TERMS
    global PROJECT_ALLOWED_UNITS
    global PROJECT_ALLOWED_ACRONYMS
    global PROJECT_ALLOWED_ABBREVIATIONS
    global PROJECT_STYLE_GUIDE_PATTERNS

    if glossary_terms is not None:
        PROJECT_GLOSSARY_TERMS = {term.strip() for term in glossary_terms if term and term.strip()}
    if allowed_units is not None:
        PROJECT_ALLOWED_UNITS = {unit.strip().lower() for unit in allowed_units if unit and unit.strip()}
    if allowed_acronyms is not None:
        PROJECT_ALLOWED_ACRONYMS = {acr.strip() for acr in allowed_acronyms if acr and acr.strip()}
    if allowed_abbreviations is not None:
        PROJECT_ALLOWED_ABBREVIATIONS = {abbr.strip().lower() for abbr in allowed_abbreviations if abbr and abbr.strip()}
    if style_guide_patterns is not None:
        PROJECT_STYLE_GUIDE_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in style_guide_patterns if pattern]


def _strip_angle_bracket_placeholders(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def _extract_glossary_style_terms(text: str) -> Set[str]:
    cleaned = _strip_angle_bracket_placeholders(text)
    return {match.group(0) for match in R4_GLOSSARY_STYLE_TERM_PATTERN.finditer(cleaned)}


def _preferred_spelling_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for term in PROJECT_GLOSSARY_TERMS:
        if "_" in term:
            mapping[term.replace("_", " ").lower()] = term
    return mapping


# -----------------------------------------------------------------------------
# R1 - Structured Statements
# -----------------------------------------------------------------------------
def check_r1_structured_statements(text: str) -> List[RuleViolation]:
    """
    R1 - Structured Statements
    Need statements and requirement statements must conform to one of the agreed patterns.

    Minimal coded heuristic:
    - Accept if it looks like a requirement statement using "shall"
    - OR it looks like a need statement using "need the"
    """
    t = text.strip()
    t_lc = t.lower()

    has_shall = " shall " in f" {t_lc} "
    has_need_pattern = " need the " in f" {t_lc} "

    if has_shall or has_need_pattern:
        return []

    issue = (
        "The statement does not appear to conform to the agreed structured patterns "
        "(e.g., requirement statements using 'shall' or need statements using 'need the ...')."
    )
    suggestion = (
        "Rewrite the statement to conform to an agreed pattern, "
        "e.g., use a clear subject + 'shall' + action for a requirement statement, or a "
        "stakeholder 'need' pattern for a need statement."
    )

    return [_mk_violation("R1", "Structured Statements", issue, suggestion)]


# -----------------------------------------------------------------------------
# R4 - Defined Terms
# -----------------------------------------------------------------------------
def check_r4_defined_terms(text: str) -> List[RuleViolation]:
    """
    R4 - Defined Terms
    Definition: Define all terms used within an associated glossary and/or data dictionary.

    Conservative programmatic implementation:
    - Only check terms written in the glossary-style convention used by the Guide
      (capitalized multi-word terms joined by underscores, e.g., "Current_Time").
    - Only flag when a project glossary/data dictionary has been configured.
    """
    violations: List[RuleViolation] = []
    if not PROJECT_GLOSSARY_TERMS:
        return violations

    for term in sorted(_extract_glossary_style_terms(text)):
        if term in PROJECT_GLOSSARY_TERMS:
            continue
        issue = (
            f"Uses glossary-style term '{term}', but it is not present in the configured glossary/data dictionary."
        )
        suggestion = (
            "Add the term to the project glossary/data dictionary, or replace it with the project's approved defined term."
        )
        violations.append(_mk_violation("R4", "Defined Terms", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R6 - Common Units of Measure
# -----------------------------------------------------------------------------
def check_r6_common_units_of_measure(text: str) -> List[RuleViolation]:
    """
    R6 - Common Units of Measure
    Definition: When stating quantities, all numbers should have appropriate and consistent units of measure
    explicitly stated using a common measurement system in terms of the thing the number refers.

    Coded heuristic:
    - Flag numeric values that do not appear to be followed by a unit token (word/symbol),
      while allowing common inline forms like '85°C' and '95%'.
    """
    t = text.strip()
    t_lc = t.lower()

    # Find numbers, including decimals. We also catch inline percent and degree/unit suffixes.
    number_iter = list(re.finditer(r"\b\d+(?:\.\d+)?\b", t_lc))

    violations: List[RuleViolation] = []
    for m in number_iter:
        end = m.end()
        num = m.group(0)

        # Allow immediately-suffixed units like 85°C or 95% (no space)
        suffix = t_lc[end : end + 3]  # small window is enough for %, °c, etc.
        if suffix.startswith("%") or suffix.startswith("\u00b0") or suffix.startswith("c") or suffix.startswith("f"):
            continue

        # Look ahead for the next non-space token
        rest = t_lc[end:]
        ws = re.match(r"\s+", rest)
        if not ws:
            # End of string right after number => no unit
            issue = f"Quantity '{num}' is stated without an explicit unit of measure."
            suggestion = (
                "Add an appropriate unit of measure explicitly, and ensure units are consistent across related statements "
                "using a common measurement system."
            )
            violations.append(_mk_violation("R6", "Common Units of Measure", issue, suggestion))
            continue

        after_ws = rest[ws.end() :]
        next_token_match = re.match(r"([^\s,;:.]+)", after_ws)
        next_token = next_token_match.group(1) if next_token_match else ""

        # If the next token has no letters and is not a known symbol-like unit, treat as missing unit.
        # (We avoid inventing a unit list; we only check "is there some unit-like token".)
        has_letter = bool(re.search(r"[a-z]", next_token))
        has_unit_symbol = "%" in next_token or "\u00b0" in next_token or "/" in next_token

        if not (has_letter or has_unit_symbol):
            issue = f"Quantity '{num}' may not have an explicit unit of measure."
            suggestion = (
                "Add an appropriate unit of measure explicitly, and ensure units are consistent across related statements "
                "using a common measurement system."
            )
            violations.append(_mk_violation("R6", "Common Units of Measure", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R7 - Vague Terms
# -----------------------------------------------------------------------------
def check_r7_vague_terms(text: str) -> List[RuleViolation]:
    """
    R7 - Vague Terms
    Definition: Avoid the use of vague terms.
    The Guide provides explicit lists of vague quantification words, vague adjectives, and vague adverbs.
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    def flag_term(term: str, kind: str) -> None:
        issue = f"Uses vague {kind} term '{term}', which can lead to ambiguity and unverifiable statements."
        suggestion = (
            "Replace the vague term with a specific, measurable, and verifiable expression "
            "(e.g., a defined value, range, tolerance, or explicit condition)."
        )
        violations.append(_mk_violation("R7", "Vague Terms", issue, suggestion))

    # Quantification: mix of single- and multi-word terms
    for term in R7_VAGUE_QUANTIFICATION:
        if " " in term:
            if _contains_phrase(t_lc, term):
                flag_term(term, "quantification")
        else:
            if re.search(rf"\b{re.escape(term)}\b", t_lc):
                flag_term(term, "quantification")

    # Adjectives
    for term in R7_VAGUE_ADJECTIVES:
        if re.search(rf"\b{re.escape(term)}\b", t_lc):
            flag_term(term, "adjective")

    # Adverbs
    for term in R7_VAGUE_ADVERBS:
        if re.search(rf"\b{re.escape(term)}\b", t_lc):
            flag_term(term, "adverb")

    return violations


# -----------------------------------------------------------------------------
# R8 - Escape Clauses
# -----------------------------------------------------------------------------
def check_r8_escape_clauses(text: str) -> List[RuleViolation]:
    """
    R8 - Escape Clauses
    Avoid the inclusion of escape clauses that state vague conditions or possibilities.
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    for phrase in R8_ESCAPE_CLAUSES:
        if _contains_phrase(t_lc, phrase):
            issue = f"Contains escape clause '{phrase}', which makes applicability/obligation vague."
            suggestion = (
                "Remove the escape clause and replace it with explicit, objective conditions for when the statement applies, "
                "or create separate statements for each condition."
            )
            violations.append(_mk_violation("R8", "Escape Clauses", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R9 - Open-ended Clauses
# -----------------------------------------------------------------------------
def check_r9_open_ended_clauses(text: str) -> List[RuleViolation]:
    """
    R9 - Open-ended Clauses
    Definition: Avoid open-ended, non-specific clauses such as "including but not limited to", "etc." and "and so on".
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    # "etc." is often written without the dot; detect both via regex but keep the canonical list unchanged.
    etc_found = bool(re.search(r"\betc\.?\b", t_lc))

    for phrase in R9_OPEN_ENDED:
        if phrase == "etc.":
            if etc_found:
                issue = "Contains open-ended clause 'etc.', implying unstated additional items."
                suggestion = (
                    "Replace the open-ended clause by explicitly stating all items needed, "
                    "or split into additional statements that explicitly state each case."
                )
                violations.append(_mk_violation("R9", "Open-ended Clauses", issue, suggestion))
        else:
            if _contains_phrase(t_lc, phrase):
                issue = f"Contains open-ended clause '{phrase}', implying unstated additional items."
                suggestion = (
                    "Replace the open-ended clause by explicitly stating all items needed, "
                    "or split into additional statements that explicitly state each case."
                )
                violations.append(_mk_violation("R9", "Open-ended Clauses", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R10 - Superfluous Infinitives
# -----------------------------------------------------------------------------
def check_r10_superfluous_infinitives(text: str) -> List[RuleViolation]:
    """
    R10 - Superfluous Infinitives
    Definition: Avoid the use of superfluous infinitives such as "to be designed to", "to be able to",
    "to be capable of", "to enable", "to allow".
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    for phrase in R10_SUPERFLUOUS_INFINITIVES:
        if _contains_phrase(t_lc, phrase):
            issue = f"Uses superfluous infinitive phrase '{phrase}', adding unnecessary wording and potential ambiguity."
            suggestion = (
                "Rewrite to state the required action directly (conform to the agreed structured statement patterns), "
                "e.g., '<entity> shall <action> ...', and include any needed conditions explicitly."
            )
            violations.append(_mk_violation("R10", "Superfluous Infinitives", issue, suggestion))

    return violations

# -----------------------------------------------------------------------------
# R13 - Correct Spelling
# -----------------------------------------------------------------------------
def check_r13_correct_spelling(text: str) -> List[RuleViolation]:
    """
    R13 - Correct Spelling
    Use correct spelling.

    NOTE (per Guide): spelling checks are often tool/project-specific. Here we only flag
    the explicit example confusion term shown in the Guide.
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    for term in R13_SPELLING_EXAMPLE_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", t_lc):
            issue = f"Contains '{term}', which is an example of a word-confusion spelling issue in the Guide."
            suggestion = (
                "Verify spelling against the project glossary/data dictionary and correct the term if needed. "
                "If using automated spelling tools, configure them for project-specific vocabulary."
            )
            violations.append(_mk_violation("R13", "Correct Spelling", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R14 - Correct Punctuation
# -----------------------------------------------------------------------------
def check_r14_correct_punctuation(text: str) -> List[RuleViolation]:
    """
    R14 - Correct Punctuation
    Use correct punctuation.

    Minimal coded heuristic based on the explicit example in the Guide where an incorrectly
    placed comma changes meaning.
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    for pat in R14_EXAMPLE_BAD_COMMA_PATTERNS:
        if pat in t_lc:
            issue = f"Contains punctuation pattern '{pat}' that matches the Guide's example of a confusing comma placement."
            suggestion = (
                "Adjust punctuation so sub-clauses are clearly attached to the intended phrase, reducing ambiguity. "
                "Also keep punctuation minimal to reduce ambiguity."
            )
            violations.append(_mk_violation("R14", "Correct Punctuation", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R16 - Use of “Not”
# -----------------------------------------------------------------------------
def check_r16_use_of_not(text: str) -> List[RuleViolation]:
    """
    R16 - Use of “Not”
    Avoid the use of the word “not”.

    Key consideration in the Guide is verification: 'not ever' is not verifiable in finite time,
    except where a logical NOT is explicitly intended.
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    for m in re.finditer(r"\bnot\b", t_lc):
        issue = "Uses the word 'not', which can imply 'not ever' and may be impossible to verify in finite time."
        suggestion = (
            "Rewrite the statement in the positive (what the entity shall do), or express a measurable/verifiable constraint. "
            "If a logical condition is intended, use an explicit logical expression convention (e.g., NOT [X OR Y])."
        )
        violations.append(_mk_violation("R16", "Use of “Not”", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R17 - Use of Oblique Symbol
# -----------------------------------------------------------------------------
def check_r17_use_of_oblique_symbol(text: str) -> List[RuleViolation]:
    """
    R17 - Use of Oblique Symbol
    Avoid the use of the oblique ('/') symbol because it can have many meanings.

    Exceptions in the Guide include:
    - units (e.g., km/h)
    - symmetrical ranges (+/- 5 degrees F)
    - ratios/fractions (e.g., 1/16)
    """
    t = text
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    # Quick allow for '+/-' (explicit exception)
    tmp = t.replace("+/-", "")

    # Find remaining slashes
    for m in re.finditer(r"/", tmp):
        idx = m.start()

        # Allow units such as km/h or g/s (explicit exception in the Guide).
        left_char = tmp[idx - 1] if idx > 0 else ""
        right_char = tmp[idx + 1] if idx + 1 < len(tmp) else ""
        if re.match(r"[A-Za-z%°]", left_char) and re.match(r"[A-Za-z%°]", right_char):
            continue

        # Allow fractions/ratios like 1/16 (explicit exception)
        # Check a small window around the slash for digit/digit
        left = tmp[max(0, idx - 10) : idx]
        right = tmp[idx + 1 : idx + 11]
        if re.search(r"\d\s*$", left) and re.search(r"^\s*\d", right):
            continue

        issue = "Uses '/', which can be ambiguous (e.g., user/operator, budget/schedule, and/or)."
        suggestion = (
            "Replace '/' with explicit wording (e.g., 'and', 'or', or separate statements), unless it is strictly a unit or ratio. "
            "If it implies multiple actions, split into separate need/requirement statements."
        )
        violations.append(_mk_violation("R17", "Use of Oblique Symbol", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R19 - Combinators
# -----------------------------------------------------------------------------
def check_r19_combinators(text: str) -> List[RuleViolation]:
    """
    R19 - Combinators
    Avoid words that join/combine clauses (often indicates multiple thoughts in one statement).
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    for term in R19_COMBINATORS:
        if " " in term:
            found = _contains_phrase(t_lc, term)
        else:
            found = bool(re.search(rf"\b{re.escape(term)}\b", t_lc))

        if found:
            issue = f"Contains combinator '{term}', which often indicates multiple thoughts in one statement."
            suggestion = (
                "Break into separate need/requirement statements (one thought each), or use an explicit logical expression convention "
                "if the intent is a logical condition."
            )
            violations.append(_mk_violation("R19", "Combinators", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R20 - Purpose Phrases
# -----------------------------------------------------------------------------
def check_r20_purpose_phrases(text: str) -> List[RuleViolation]:
    """
    R20 - Purpose Phrases
    Avoid phrases that indicate purpose/intent/reason inside the statement.
    The Guide recommends putting such information separately (e.g., via a rationale attribute),
    not inside the requirement text.
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    for phrase in R20_PURPOSE_PHRASES:
        if _contains_phrase(t_lc, phrase):
            issue = f"Contains purpose/intent phrase '{phrase}', adding extra explanatory text inside the statement."
            suggestion = (
                "Remove the purpose/intent phrase from the statement and keep the requirement concise. "
                "Put the purpose/intent separately (e.g., in rationale) rather than as part of the requirement sentence."
            )
            violations.append(_mk_violation("R20", "Purpose Phrases", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R21 - Parentheses
# -----------------------------------------------------------------------------
def check_r21_parentheses(text: str) -> List[RuleViolation]:
    """
    R21 - Parentheses
    Avoid the use of parentheses or brackets for subordinate text.
    """
    t = text.strip()
    if not t:
        return []

    if not R21_PAREN_PATTERN.search(t):
        return []

    issue = "Contains parentheses or brackets, which can hide subordinate text and reduce clarity."
    suggestion = (
        "Remove the parentheses/brackets and rewrite the subordinate text as an explicit clause "
        "or separate statement so the requirement is clear and unambiguous."
    )
    return [_mk_violation("R21", "Parentheses", issue, suggestion)]


# -----------------------------------------------------------------------------
# R22 - Enumeration
# -----------------------------------------------------------------------------
def check_r22_enumeration(text: str) -> List[RuleViolation]:
    """
    R22 - Enumeration
    Enumerate lists of items after a group noun, rather than leaving a group noun ambiguous.

    Coded heuristic (conservative):
    - If a known group noun appears (from minimal candidate list),
      and there is no obvious enumeration/list following it (no ':' and no comma-separated list),
      flag as potentially not enumerated.
    """
    t = text.strip()
    t_lc = t.lower()
    if not t:
        return []

    violations: List[RuleViolation] = []

    for gn in R22_GROUP_NOUN_CANDIDATES:
        # Find the group noun as a whole word
        if not re.search(rf"\b{re.escape(gn)}\b", t_lc):
            continue

        # Look for obvious enumeration indicators after the group noun:
        # - a colon introducing a list
        # - multiple comma-separated items somewhere after it
        # - bullet-ish separators (; or line breaks) after it
        # This is intentionally minimal to avoid inventing domain rules.
        idx = t_lc.find(gn)
        tail = t_lc[idx + len(gn) :]

        has_colon = ":" in tail
        has_commas = tail.count(",") >= 1
        has_semicolons_or_newlines = (";" in tail) or ("\n" in tail)

        if not (has_colon or has_commas or has_semicolons_or_newlines):
            issue = f"Uses a group noun ('{gn}') without an explicit enumeration of the items."
            suggestion = (
                "Enumerate the specific items (e.g., list each item explicitly), "
                "or split into separate statements so each item is stated clearly."
            )
            violations.append(_mk_violation("R22", "Enumeration", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R23 - Supporting Diagram, Model or ICD
# -----------------------------------------------------------------------------
def check_r23_supporting_diagram_model_icd(text: str) -> List[RuleViolation]:
    """
    R23 - Supporting Diagram, Model or ICD
    When a need/requirement is related to complex behavior, refer to the supporting diagram, model, or ICD.

    NOTE:
    - Determining "complex behavior" robustly is hard with pure coded heuristics.
    - This coded check only flags a likely case: multiple conditions/actions in one sentence with
      no sign of any reference to an external model/diagram/ICD.
    """
    t = text.strip()
    t_lc = t.lower()
    if not t:
        return []

    # Heuristic: multi-action / multi-clause often correlates with "complex behavior"
    shall_count = len(_SHALL_PATTERN.findall(t_lc))
    has_multiple_actions = shall_count >= 2

    # Look for a basic "reference" signal in the text (diagram/model/ICD/figure/standard)
    has_reference_signal = any(
        k in t_lc for k in ["diagram", "model", "icd", "figure", "per <", "per ", "as defined in", "as shown in"]
    )

    if has_multiple_actions and not has_reference_signal:
        issue = "Appears to describe complex behavior (multiple actions) without referencing a supporting diagram/model/ICD."
        suggestion = (
            "If this statement depends on complex behavior, add a reference to the supporting diagram, model, or ICD "
            "that defines the context, or split into clearer single-thought statements."
        )
        return [_mk_violation("R23", "Supporting Diagram, Model or ICD", issue, suggestion)]

    return []


# -----------------------------------------------------------------------------
# R25 - Headings
# -----------------------------------------------------------------------------
def check_r25_headings(text: str) -> List[RuleViolation]:
    """
    R25 - Headings
    Avoid relying on headings to support explanation or understanding of the need/requirement.

    Coded heuristic:
    - If the statement begins with a section-like heading number (e.g., '4.1 ') and then a requirement,
      flag it as likely being embedded in heading-dependent formatting.
    """
    t = text.strip()
    if not t:
        return []

    if re.match(r"^\d+(\.\d+)+\s+", t):
        issue = "Appears to be written as a numbered/heading-dependent statement."
        suggestion = (
            "Ensure the statement is understandable without any heading context. "
            "Rewrite so the requirement is self-contained (no reliance on section headings)."
        )
        return [_mk_violation("R25", "Headings", issue, suggestion)]

    return []


# -----------------------------------------------------------------------------
# R26 - Absolutes
# -----------------------------------------------------------------------------
def check_r26_absolutes(text: str) -> List[RuleViolation]:
    """
    R26 - Absolutes
    Avoid using unachievable absolutes (e.g., 100% availability; 'all', 'every', 'always', 'never').
    """
    t = text.strip()
    t_lc = t.lower()
    if not t:
        return []

    violations: List[RuleViolation] = []

    # 100% / 100 percent
    if R26_PERCENT_100_PATTERN.search(t):
        issue = "Contains an absolute (100%), which is typically not achievable or verifiable."
        suggestion = (
            "Replace the absolute with a feasible, verifiable target (e.g., a threshold such as ≥ 98%) "
            "and specify the applicable condition/time period."
        )
        violations.append(_mk_violation("R26", "Absolutes", issue, suggestion))

    # all/every/always/never
    for w in R26_ABSOLUTE_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", t_lc):
            issue = f"Contains an absolute word ('{w}'), which may be infeasible or unverifiable."
            suggestion = (
                "Replace the absolute with a measurable, bounded statement (e.g., specify a percentage/threshold, "
                "time window, and conditions of applicability)."
            )
            violations.append(_mk_violation("R26", "Absolutes", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R27 - Explicit Conditions
# -----------------------------------------------------------------------------
def check_r27_explicit_conditions(text: str) -> List[RuleViolation]:
    """
    R27 - Explicit Conditions
    State conditions’ applicability explicitly; repeat the condition for each action
    instead of listing multiple actions under one condition.
    """
    t = text.strip()
    t_lc = t.lower()
    if not t:
        return []

    # If it starts with a condition and then contains multiple 'shall' actions, flag.
    starts_with_condition = any(t_lc.startswith(c + " ") for c in R27_CONDITION_STARTERS)
    shall_count = len(_SHALL_PATTERN.findall(t_lc))

    if starts_with_condition and shall_count >= 2:
        issue = "A single condition appears to govern multiple actions in one statement."
        suggestion = (
            "Repeat the condition in separate statements (one action per statement), "
            "so each action is explicitly conditioned and can be verified independently."
        )
        return [_mk_violation("R27", "Explicit Conditions", issue, suggestion)]

    return []


# -----------------------------------------------------------------------------
# R28 - Multiple Conditions
# -----------------------------------------------------------------------------
def check_r28_multiple_conditions(text: str) -> List[RuleViolation]:
    """
    R28 - Multiple Conditions
    Express the propositional nature of a condition explicitly for a single action
    instead of giving lists of actions for a specific condition.

    Coded heuristic:
    - If there is a condition starter (when/if) and the condition contains list-like separators
      without explicit logical operators (AND/OR/EITHER), flag.
    """
    t = text.strip()
    t_lc = t.lower()
    if not t:
        return []

    # Quick gate: must contain a condition starter
    if not any(re.search(rf"\b{re.escape(c)}\b", t_lc) for c in R27_CONDITION_STARTERS):
        return []

    # Condition list cues
    has_list_cues = (";" in t) or ("\n" in t) or (":" in t)
    has_explicit_logic = any(k in t_lc for k in [" and ", " or ", " either ", " neither ", " not "])

    if has_list_cues and not has_explicit_logic:
        issue = "Condition appears list-like, but propositional logic is not stated explicitly."
        suggestion = (
            "Rewrite the condition using explicit logical operators (e.g., AND/OR/EITHER), "
            "or split into separate conditioned statements, each with a single clear condition."
        )
        return [_mk_violation("R28", "Multiple Conditions", issue, suggestion)]

    return []


# -----------------------------------------------------------------------------
# R29 - Classification
# -----------------------------------------------------------------------------
def check_r29_classification(text: str) -> List[RuleViolation]:
    """
    R29 - Classification
    Classify needs/requirements according to the aspects of the problem/system it addresses.

    NOTE:
    - This is normally handled via metadata (Type/Category attribute / project schema),
      not reliably detectable from a single requirement sentence alone.
    """
    return []


# -----------------------------------------------------------------------------
# R30 - Unique Expression
# -----------------------------------------------------------------------------
def check_r30_unique_expression(text: str) -> List[RuleViolation]:
    """
    R30 - Unique Expression
    Express each need/requirement once and only once.

    NOTE:
    - Per the Guide, this is primarily a set-level rule that requires comparison
      across the need/requirement set. The single-statement pipeline cannot
      determine duplication by itself, so this check is a no-op until corpus
      context is supplied.
    """
    return []


# -----------------------------------------------------------------------------
# R32 - Universal Qualification
# -----------------------------------------------------------------------------
def check_r32_universal_qualification(text: str) -> List[RuleViolation]:
    """
    R32 - Universal Qualification
    Use “each” instead of “all”, “any” or “both” when universal quantification is intended.
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    for w in R32_UNIVERSAL_BAD:
        if re.search(rf"\b{re.escape(w)}\b", t_lc):
            issue = f"Uses '{w}' where universal quantification may be intended."
            suggestion = f"Use '{R32_UNIVERSAL_PREFERRED}' instead of '{w}' when universal quantification is intended."
            violations.append(_mk_violation("R32", "Universal Qualification", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R33 - Range of Values
# -----------------------------------------------------------------------------
def check_r33_range_of_values(text: str) -> List[RuleViolation]:
    """
    R33 - Range of Values
    Define each quantity with a range of values appropriate to the entity.

    Conservative coded heuristic:
    - If the statement contains numeric values, but none of them appear with an explicit range/tolerance cue,
      flag. (True determination of "appropriate range" is domain-specific.)
    """
    t = text.strip()
    t_lc = t.lower()
    if not t:
        return []

    nums = list(re.finditer(r"\b\d+(?:[.,]\d+)?\b", t_lc))
    if not nums:
        return []

    # Range/tolerance cues that are *structural*, not domain-specific:
    # symbols: ≤ ≥ < > ±
    # patterns: "+/-", " - " between numbers, "to" between numbers
    has_structural_range = any(sym in t for sym in ["≤", "≥", "<", ">", "±"]) or "+/-" in t_lc

    # Check simple "between X and Y" / "X to Y" / "X - Y" patterns
    between_and = bool(re.search(r"\bbetween\b.*\band\b", t_lc))
    x_to_y = bool(re.search(r"\b\d+(?:[.,]\d+)?\b\s+to\s+\b\d+(?:[.,]\d+)?\b", t_lc))
    x_dash_y = bool(re.search(r"\b\d+(?:[.,]\d+)?\b\s*-\s*\b\d+(?:[.,]\d+)?\b", t_lc))

    if not (has_structural_range or between_and or x_to_y or x_dash_y):
        issue = "Contains a quantity but does not appear to specify a range/tolerance for verification/validation."
        suggestion = (
            "Define the quantity using an explicit range/tolerance appropriate to the entity, "
            "so it can be verified/validated against that range."
        )
        return [_mk_violation("R33", "Range of Values", issue, suggestion)]

    return []


# -----------------------------------------------------------------------------
# R35 - Temporal Dependencies
# -----------------------------------------------------------------------------
def check_r35_temporal_dependencies(text: str) -> List[RuleViolation]:
    """
    R35 - Temporal Dependencies
    Define temporal dependencies explicitly instead of using indefinite temporal keywords
    such as: “eventually”, “until”, “before”, “after”, “as”, “once”, “earliest”, “latest”,
    “instantaneous”, “simultaneous”, and “at last”.
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    for kw in R35_INDEFINITE_TEMPORAL_KEYWORDS:
        if " " in kw:
            found = _contains_phrase(t_lc, kw)
        else:
            found = bool(re.search(rf"\b{re.escape(kw)}\b", t_lc))

        if found:
            issue = f"Uses indefinite temporal keyword '{kw}'."
            suggestion = (
                "Define the temporal dependency explicitly (e.g., specify an exact timing/ordering constraint "
                "or measurable time window) instead of relying on an indefinite temporal keyword."
            )
            violations.append(_mk_violation("R35", "Temporal Dependencies", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R36 - Consistent Terms and Units
# -----------------------------------------------------------------------------
def check_r36_consistent_terms_and_units(text: str) -> List[RuleViolation]:
    """
    R36 - Consistent Terms and Units
    Use each term and unit of measure consistently throughout the project artifacts.

    Conservative programmatic implementation:
    - If a glossary is configured, flag use of a spaced/lowercase variant when a
      glossary-preferred underscore term exists (e.g., "current time" vs "Current_Time").
    - If a project unit set is configured, flag measured units outside that approved set.
    """
    violations: List[RuleViolation] = []
    t_lc = text.lower()

    preferred_map = _preferred_spelling_map()
    for loose_variant, preferred_term in preferred_map.items():
        if loose_variant in t_lc and preferred_term not in text:
            issue = (
                f"Uses '{loose_variant}' instead of the configured glossary term '{preferred_term}', "
                "which is inconsistent with the project ontology."
            )
            suggestion = (
                f"Use the glossary-defined term '{preferred_term}' consistently throughout requirements and related artifacts."
            )
            violations.append(_mk_violation("R36", "Consistent Terms and Units", issue, suggestion))

    if PROJECT_ALLOWED_UNITS:
        for match in R36_MEASURED_UNIT_PATTERN.finditer(text):
            unit = match.group(1).lower()
            if unit in PROJECT_ALLOWED_UNITS:
                continue
            issue = f"Uses unit '{match.group(1)}', which is not in the configured project unit set."
            suggestion = "Use the project's agreed unit names/symbols consistently throughout the requirement set and related artifacts."
            violations.append(_mk_violation("R36", "Consistent Terms and Units", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R37 - Acronyms
# -----------------------------------------------------------------------------
def check_r37_acronyms(text: str) -> List[RuleViolation]:
    """
    R37 - Acronyms
    If acronyms are used, they must be consistent throughout sets and across lifecycle artifacts.
    Acronyms must be written consistently in capitalization and periods (e.g., “CMDP” not “C.M.D.P.” nor “CmdP”).

    Single-statement coded heuristic:
    - Flag acronym-like tokens that contain periods (e.g., C.M.D.P.).
    - Flag mixed-case acronym patterns like 'CmdP' (letters with internal case changes).
    NOTE: True consistency requires set-level analysis.
    """
    t = text.strip()
    if not t:
        return []

    violations: List[RuleViolation] = []

    # Period-separated acronym pattern like C.M.D.P.
    if re.search(r"\b(?:[A-Za-z]\.){2,}[A-Za-z]?\b", t):
        issue = "Contains an acronym written with periods (e.g., 'C.M.D.P.'), which the Guide flags as an inconsistent form."
        suggestion = (
            "Use a single consistent acronym format (e.g., 'CMDP') and define the acronym in the project glossary/data dictionary."
        )
        violations.append(_mk_violation("R37", "Acronyms", issue, suggestion))

    # Mixed-case internal changes (e.g., CmdP)
    if re.search(r"\b[A-Z][a-z]+[A-Z][A-Za-z]*\b", t):
        issue = "Contains a mixed-case acronym form (e.g., 'CmdP'), which can indicate inconsistency."
        suggestion = (
            "Use one consistent capitalization style for the acronym and define it in the project acronym list/glossary."
        )
        violations.append(_mk_violation("R37", "Acronyms", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R38 - Abbreviations
# -----------------------------------------------------------------------------
def check_r38_abbreviations(text: str) -> List[RuleViolation]:
    """
    R38 - Abbreviations
    Avoid the use of abbreviations unless the context is clear and the abbreviation is defined in the glossary/acronym list.

    Coded check grounded in the Guide's explicit example ('op' used ambiguously).
    """
    t_lc = text.lower()
    violations: List[RuleViolation] = []

    if re.search(r"\bop\b", t_lc) and "op" not in PROJECT_ALLOWED_ABBREVIATIONS:
        issue = "Contains abbreviation 'op', which the Guide uses as an example of ambiguous abbreviation usage."
        suggestion = "Avoid the abbreviation and use the full term consistently, unless it is uniquely defined in the project glossary/acronym list."
        violations.append(_mk_violation("R38", "Abbreviations", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R39 - Style Guide
# -----------------------------------------------------------------------------
def check_r39_style_guide(text: str) -> List[RuleViolation]:
    """
    R39 - Style Guide
    Use a project-wide style guide for individual need and requirement statements.

    Conservative programmatic implementation:
    - Only enforce this rule when the project's allowed textual patterns/templates
      have been configured as regex patterns.
    """
    if not PROJECT_STYLE_GUIDE_PATTERNS:
        return []

    for pattern in PROJECT_STYLE_GUIDE_PATTERNS:
        if pattern.search(text.strip()):
            return []

    issue = "The statement does not match any configured project style-guide pattern/template."
    suggestion = "Rewrite the statement so it conforms to one of the project's approved requirement patterns/templates."
    return [_mk_violation("R39", "Style Guide", issue, suggestion)]


# -----------------------------------------------------------------------------
# R40 - Decimal Format
# -----------------------------------------------------------------------------
def check_r40_decimal_format(text: str) -> List[RuleViolation]:
    """
    R40 - Decimal Format
    Use a consistent format and number of significant digits for decimal numbers.

    Single-statement coded heuristics from the Guide:
    - Avoid numbers between 1 and –1 written without a leading zero (e.g., '.99' or '–,99').
    - Flag obvious mixed separator usage within the same statement (period+comma patterns in numeric tokens).
    NOTE: Full consistency and significant-digit uniformity is best validated at the set level.
    """
    t = text.strip()
    if not t:
        return []

    violations: List[RuleViolation] = []

    # Leading zero rule: ".99" or "-,99"
    if R40_LEADING_DECIMAL_PATTERN.search(t) or R40_LEADING_DECIMAL_COMMA_PATTERN.search(t) or R40_NEGATIVE_LEADING_DECIMAL_COMMA_PATTERN.search(t):
        issue = "Contains a decimal number written without a leading zero (e.g., '.99' or '–,99')."
        suggestion = "Use a leading zero for numbers between 1 and –1 (e.g., '0.99' or '–0,99')."
        violations.append(_mk_violation("R40", "Decimal Format", issue, suggestion))

    # Mixed decimal/thousands separators within the same statement (heuristic)
    numeric_tokens = R40_NUMERIC_TOKEN_PATTERN.findall(t)
    # If we see tokens that include both ',' and '.' across tokens, it may indicate inconsistency.
    has_dot = any("." in tok for tok in numeric_tokens)
    has_comma = any("," in tok for tok in numeric_tokens)
    if has_dot and has_comma:
        issue = "Appears to mix comma and period numeric separators within the same statement."
        suggestion = (
            "Use one consistent numeric convention for thousand separators and decimal separators throughout "
            "the requirement set."
        )
        violations.append(_mk_violation("R40", "Decimal Format", issue, suggestion))

    return violations


# -----------------------------------------------------------------------------
# R41 - Related Needs and Requirements
# -----------------------------------------------------------------------------
def check_r41_related_needs_and_requirements(text: str) -> List[RuleViolation]:
    """
    R41 - Related Needs and Requirements
    Group related needs and requirements together.

    NOTE: This is inherently a set-level organizational rule; cannot be detected from a single statement.
    """
    return []


# -----------------------------------------------------------------------------
# R42 - Structured Sets
# -----------------------------------------------------------------------------
def check_r42_structured_sets(text: str) -> List[RuleViolation]:
    """
    R42 - Structured Sets
    Conform to a defined structure or template for organizing sets of needs and requirements.

    NOTE: This is a set-level/template compliance rule; cannot be detected from a single statement.
    """
    return []



# -----------------------------------------------------------------------------
# Aggregate
# -----------------------------------------------------------------------------
CODED_CHECKS: dict[str, Callable[[str], List[RuleViolation]]] = {
    "R1": check_r1_structured_statements,
    "R4": check_r4_defined_terms,
    "R6": check_r6_common_units_of_measure,
    "R7": check_r7_vague_terms,
    "R8": check_r8_escape_clauses,
    "R9": check_r9_open_ended_clauses,
    "R10": check_r10_superfluous_infinitives,
    "R13": check_r13_correct_spelling,
    "R14": check_r14_correct_punctuation,
    "R16": check_r16_use_of_not,
    "R17": check_r17_use_of_oblique_symbol,
    "R19": check_r19_combinators,
    "R20": check_r20_purpose_phrases,
    "R21": check_r21_parentheses,
    "R26": check_r26_absolutes,
    "R30": check_r30_unique_expression,
    "R32": check_r32_universal_qualification,
    "R35": check_r35_temporal_dependencies,
    "R36": check_r36_consistent_terms_and_units,
    "R37": check_r37_acronyms,
    "R38": check_r38_abbreviations,
    "R39": check_r39_style_guide,
    "R40": check_r40_decimal_format,
}


def run_programmatic_checks(req_text: str, allowed_rules: Optional[Set[str]] = None) -> List[RuleViolation]:
    active = set(CODED_CHECKS.keys()) if allowed_rules is None else (set(CODED_CHECKS.keys()) & allowed_rules)
    violations: List[RuleViolation] = []
    for rid in sorted(active):
        violations.extend(CODED_CHECKS[rid](req_text))
    return violations


def run_coded_checks(req_text: str, allowed_rules: Optional[Set[str]] = None) -> List[RuleViolation]:
    """
    Backward-compatible alias for older imports that still use the previous name.
    """
    return run_programmatic_checks(req_text, allowed_rules=allowed_rules)
