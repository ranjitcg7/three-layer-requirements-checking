# backend/app/services/rules_llm.py

from __future__ import annotations

from typing import Dict, List, Optional, Set

from app.core.schemas import RuleViolation
from app.services.llm_client import extract_json_from_text, llm_chat


# Rules marked with LLM participation in "42 Rules detection methods.xlsx".
# This includes pure-LLM rules and multi-method rules that explicitly use LLM.
LLM_RULE_IDS: List[str] = [
    "R1",
    "R3",
    "R15",
    "R18",
    "R22",
    "R23",
    "R25",
    "R27",
    "R28",
    "R29",
    "R30",
    "R31",
    "R33",
    "R34",
    "R41",
    "R42",
]


_RULE_META: Dict[str, Dict[str, str]] = {
    "R1": {
        "rule_name": "Structured Statements",
        "definition": (
            "Need statements and requirement statements must conform to one of the agreed patterns."
        ),
        "what_to_flag": (
            "Flag statements that do not fit an agreed need or requirement pattern even if they contain some structural "
            "signals, such as unclear role of the sentence parts, missing required pattern elements, or overall pattern mismatch."
        ),
        "suggestion_hint": (
            "Rewrite using one agreed statement pattern with the required parts stated explicitly."
        ),
    },
    "R3": {
        "rule_name": "Appropriate Subject-Verb",
        "definition": (
            "Ensure the subject and verb of the need or requirement statement are appropriate to the entity "
            "to which the statement refers."
        ),
        "what_to_flag": (
            "Flag cases where the subject is not the intended responsible entity, or the verb or action is not "
            "appropriate for that entity level, such as a user action written as if the system performs it, "
            "or an attribute or thing acting as the subject. Do not flag statements merely because a different "
            "verb could be more specific or stylistically preferable if the current subject-verb pairing is still "
            "semantically appropriate for the entity."
        ),
        "suggestion_hint": (
            "Align the statement so the correct entity is the subject and performs an appropriate action. "
            "Only suggest a change when there is an actual subject-verb mismatch, not just a possible wording refinement."
        ),
    },
    "R15": {
        "rule_name": "Logical Expressions",
        "definition": (
            "Use a defined convention to express logical expressions such as '[X AND Y]', '[X OR Y]', "
            "'[X XOR Y]', and 'NOT [X OR Y]'."
        ),
        "what_to_flag": (
            "Flag ambiguous logic like 'and/or', mixed logical meaning without an explicit convention, or cases where "
            "AND or OR is used in a way that creates ambiguity instead of a clear logical condition."
        ),
        "suggestion_hint": (
            "Rewrite the logic using an explicit logical-expression convention and bracket it to keep the statement singular and unambiguous."
        ),
    },
    "R18": {
        "rule_name": "Single Thought Sentence",
        "definition": (
            "Write a single sentence that contains a single thought conditioned and qualified by relevant sub-clauses."
        ),
        "what_to_flag": (
            "Flag statements that still communicate multiple thoughts or bundled actions even if their grammar looks acceptable, "
            "especially when the actions should be separately allocated, traced, or verified."
        ),
        "suggestion_hint": (
            "Split the text into separate single-thought statements and repeat the triggering condition where needed."
        ),
    },
    "R22": {
        "rule_name": "Enumeration",
        "definition": (
            "Enumerate sets explicitly instead of using a group noun to name the set."
        ),
        "what_to_flag": (
            "Flag group nouns or higher-level functions that leave the membership of the set unclear in a requirement statement, "
            "for example when the text says a system will manage or monitor a broad set without enumerating the distinct members."
        ),
        "suggestion_hint": (
            "Enumerate the members explicitly, usually as separate requirements, or define the set explicitly in the glossary where justified."
        ),
    },
    "R23": {
        "rule_name": "Supporting Diagram, Model, or ICD",
        "definition": (
            "When a need or requirement is related to complex behavior, refer to a supporting diagram, model, or ICD."
        ),
        "what_to_flag": (
            "Flag statements whose behavior is too complex or tightly coupled to express clearly in words alone and that would be clearer "
            "with a referenced diagram, model, timing diagram, table, or ICD."
        ),
        "suggestion_hint": (
            "Add a reference to the supporting diagram, model, table, timing diagram, or ICD, or split the behavior into clearer requirements."
        ),
    },
    "R25": {
        "rule_name": "Headings",
        "definition": (
            "Do not rely on headings to support explanation or understanding of a need or requirement statement."
        ),
        "what_to_flag": (
            "Flag a statement if it depends on an external heading or section title to make sense, for example if the text is not self-contained "
            "or uses wording that only becomes meaningful from heading context."
        ),
        "suggestion_hint": (
            "Rewrite the statement so it is self-contained and understandable without the heading."
        ),
    },
    "R27": {
        "rule_name": "Explicit Conditions",
        "definition": (
            "State conditions' applicability explicitly instead of leaving applicability to be inferred from context."
        ),
        "what_to_flag": (
            "Flag statements where the triggering state, event, or condition is missing or only implied by context rather than stated directly."
        ),
        "suggestion_hint": (
            "State the trigger or condition explicitly in the requirement text and repeat it in each resulting statement if multiple actions are needed."
        ),
    },
    "R28": {
        "rule_name": "Multiple Conditions",
        "definition": (
            "Express the propositional nature of a condition explicitly for a single action instead of giving lists of actions for a specific condition."
        ),
        "what_to_flag": (
            "Flag single-action statements with multiple listed conditions when it is unclear whether the conditions are conjunctive, disjunctive, "
            "inclusive OR, exclusive OR, or otherwise logically combined."
        ),
        "suggestion_hint": (
            "Rewrite the conditions using explicit logical wording, or split them into separate requirements if that better preserves verifiability."
        ),
    },
    "R29": {
        "rule_name": "Classification",
        "definition": (
            "Classify needs and requirements according to the aspects of the problem or system it addresses."
        ),
        "what_to_flag": (
            "This is mainly a set-level organizational rule. Only flag it if the text explicitly reveals a classification or type issue in the provided context; "
            "otherwise do not guess."
        ),
        "suggestion_hint": (
            "Assign an explicit project-defined type or category attribute so the requirement can be grouped and managed appropriately."
        ),
    },
    "R30": {
        "rule_name": "Unique Expression",
        "definition": (
            "Express each need or requirement once and only once."
        ),
        "what_to_flag": (
            "This rule is largely set-level. Only flag it if the provided text itself visibly contains overlapping or redundant expression; "
            "do not invent duplication across unseen statements."
        ),
        "suggestion_hint": (
            "Remove redundant expression and keep the intent in one place only, or compare across the requirement set for duplicates."
        ),
    },
    "R31": {
        "rule_name": "Solution Free",
        "definition": (
            "Avoid stating implementation in a need statement or requirement statement unless there is rationale "
            "for constraining the design."
        ),
        "what_to_flag": (
            "Flag implementation or solution statements, such as specific technology, design choice, architecture, algorithm, "
            "tool, vendor, or how-steps, unless the text provides explicit rationale for constraining the design."
        ),
        "suggestion_hint": (
            "Rewrite to state the required outcome, behavior, or performance and move implementation details to design constraints only when justified."
        ),
    },
    "R33": {
        "rule_name": "Range of Values",
        "definition": (
            "Define each quantity with a range of values appropriate to the entity."
        ),
        "what_to_flag": (
            "Flag quantities that are stated as exact values when the requirement should express an acceptable range, tolerance, or bounded interval "
            "for feasible verification or validation."
        ),
        "suggestion_hint": (
            "Replace the exact value with an explicit acceptable range, tolerance, or interval appropriate to the entity and verification context."
        ),
    },
    "R34": {
        "rule_name": "Measurable Performance",
        "definition": (
            "Provide specific measurable performance targets appropriate to the entity to which the need or requirement "
            "is stated and against which the entity will be verified to meet."
        ),
        "what_to_flag": (
            "Flag unmeasured quantification signals such as prompt, fast, routine, maximum, minimum, optimum, nominal, "
            "easy to use, close quickly, high speed, medium-sized, best practices, and user-friendly when used without "
            "a measurable target, range, or reference to a standard or threshold."
        ),
        "suggestion_hint": (
            "Replace qualitative terms with measurable targets such as value plus unit, range or tolerance, threshold, "
            "or a referenced standard clause that provides measurable criteria."
        ),
    },
    "R41": {
        "rule_name": "Related Needs and Requirements",
        "definition": (
            "Group related needs and requirements together."
        ),
        "what_to_flag": (
            "This is a set-level organizational rule. Only flag it if the provided context explicitly shows a grouping or relationship issue; "
            "otherwise do not infer one from a single isolated statement."
        ),
        "suggestion_hint": (
            "Group the statement with related requirements by function, type or category, interface, scenario, capability, or compliance purpose."
        ),
    },
    "R42": {
        "rule_name": "Structured Sets",
        "definition": (
            "Conform to a defined structure or template for organizing sets of needs and requirements."
        ),
        "what_to_flag": (
            "This is a set-level template rule. Only flag it if the provided context explicitly shows nonconformance to the defined set structure; "
            "do not invent a missing structure from a single statement."
        ),
        "suggestion_hint": (
            "Organize the requirement within the project's defined set structure or template so its context is clear and manageable."
        ),
    },
}


def _build_prompt(req_text: str, rule_ids: List[str]) -> List[dict]:
    rules_payload = []
    for rid in rule_ids:
        meta = _RULE_META.get(rid)
        if not meta:
            continue
        rules_payload.append(
            {
                "rule_id": rid,
                "rule_name": meta["rule_name"],
                "definition": meta["definition"],
                "what_to_flag": meta["what_to_flag"],
                "suggestion_hint": meta["suggestion_hint"],
            }
        )

    system_msg = (
        "You are a requirements quality checker following the INCOSE Guide to Writing Requirements (1 July 2023).\n"
        "Return JSON only. No markdown. No extra text.\n"
        "Output schema:\n"
        "{\n"
        '  "violations": [\n'
        "    {\n"
        '      "rule_id": "Rxx",\n'
        '      "rule_name": "...",\n'
        '      "issue": "...",\n'
        '      "suggestion": "...",\n'
        '      "source": "llm"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        'If there are no violations, return {"violations": []}.\n'
        "Be specific: cite the exact word or phrase causing the violation when possible.\n"
        "Do not guess. If the provided text does not contain enough evidence for a rule, do not report a violation for that rule.\n"
        "Do not report a violation just because the wording could be more precise, more specific, or more stylistically preferred.\n"
        "Report a violation only when the rule is actually violated.\n"
        "For set-level rules such as classification, unique expression, related needs and requirements, and structured sets, "
        "only report a violation if the issue is explicit in the provided text or context itself."
    )

    user_msg = (
        "Check this requirement against the following rules.\n\n"
        f"Requirement:\n{req_text}\n\n"
        f"Rules:\n{rules_payload}\n\n"
        "Instructions for suggestions:\n"
        "- Keep suggestions actionable and aligned with the rule definition.\n"
        "- Do not invent missing glossary items, headings, diagrams, classifications, or related requirements.\n"
        "- For multi-method rules, return only the semantic or contextual judgment supported by the provided text.\n"
        "- For R3 specifically, do not flag valid system actions such as communicate, transmit, receive, detect, store, display, stop, or move just because a narrower verb might also be possible.\n"
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def llm_check_rules(
    req_text: str,
    rules: List[str],
    allowed_rules: Optional[Set[str]] = None,
) -> List[RuleViolation]:
    """
    LLM-based rule checker for selected INCOSE rules.

    - Does not rewrite the requirement.
    - Only returns violations for the requested rule IDs.
    - Supports the rule IDs listed in LLM_RULE_IDS.
    """

    if allowed_rules is not None:
        rules = [r for r in rules if r in allowed_rules]

    rules = [r for r in rules if r in _RULE_META]

    if not rules:
        return []

    messages = _build_prompt(req_text=req_text, rule_ids=rules)

    content = llm_chat(
        messages=messages,
        temperature=0.1,
        max_tokens=1200,
    )

    try:
        payload = extract_json_from_text(content)
    except ValueError:
        return []

    violations_raw = payload.get("violations", []) if isinstance(payload, dict) else []
    violations: List[RuleViolation] = []

    for item in violations_raw:
        if not isinstance(item, dict):
            continue

        item.setdefault("source", "llm")

        rule_id = item.get("rule_id")
        if rule_id not in rules:
            continue

        if rule_id in _RULE_META:
            item["rule_name"] = _RULE_META[rule_id]["rule_name"]

        if _should_suppress_violation(req_text, item):
            continue

        try:
            violations.append(RuleViolation.model_validate(item))
        except Exception:
            continue

    return violations


def _should_suppress_violation(req_text: str, item: dict) -> bool:
    rule_id = item.get("rule_id")
    issue = str(item.get("issue") or "").lower()
    suggestion = str(item.get("suggestion") or "").lower()
    req_lower = (req_text or "").lower()

    if rule_id != "R3":
        return False

    soft_r3_markers = [
        "may not be the most precise",
        "more specific verb",
        "better describes the intended action",
        "could be more specific",
        "more precise action",
        "stylistically",
    ]
    if any(marker in issue for marker in soft_r3_markers) or any(marker in suggestion for marker in soft_r3_markers):
        return True

    acceptable_patterns = [
        "shall communicate",
        "shall transmit",
        "shall receive",
        "shall detect",
        "shall store",
        "shall display",
        "shall stop",
        "shall move",
        "shall navigate",
        "shall log",
        "shall measure",
    ]
    if any(pattern in req_lower for pattern in acceptable_patterns):
        if "subject" in issue and "appropriate" in issue and ("verb" in issue or "action" in issue):
            return True

    return False
