# backend/app/services/rules_nlp.py

from __future__ import annotations

from typing import Callable, List, Optional, Set

import spacy

from app.core.schemas import RuleViolation

# Load spaCy model ONCE on import
nlp = spacy.load("en_core_web_sm")

# -----------------------------------------------------------------------------
# Characteristics impacted (from Appendix E Rules to Characteristics matrix)
# -----------------------------------------------------------------------------
RULE_TO_CHARACTERISTICS = {
    "R1": ["C1", "C2", "C3", "C4", "C5"],
    "R2": ["C1", "C2", "C3", "C4"],
    "R5": ["C1", "C2"],
    "R11": ["C1", "C2", "C3", "C4"],
    "R12": ["C1", "C2", "C3", "C4"],
    "R18": ["C1", "C2", "C3", "C4", "C5"],
    "R19": ["C1", "C2"],
    "R24": ["C1", "C2", "C3"],
    "R35": ["C1", "C2", "C3"],
}

# -----------------------------------------------------------------------------
# Helper phrase lists (from the Guide)
# -----------------------------------------------------------------------------
# R19 - Combinators (explicit list from the PDF)
R19_SINGLE_TOKEN_COMBINATORS = {
    "and",
    "or",
    "then",
    "unless",
    "but",
    "however",
    "whether",
    "meanwhile",
    "whereas",
    "otherwise",
}
R19_MULTIWORD_COMBINATORS = {
    "as well as",
    "but also",
    "on the other hand",
}

# R35 - Temporal Dependencies (explicit list from the PDF)
R35_TEMPORAL_MARKERS = {
    "until",
    "before",
    "after",
    "as",
    "once",
}
R35_OTHER_TEMPORAL_KEYWORDS = {
    "eventually",
    "earliest",
    "latest",
    "instantaneous",
    "simultaneous",
}

# R24 - Pronouns (explicit lists from rule text)
R24_PERSONAL_PRONOUNS = {
    "it",
    "this",
    "that",
    "he",
    "she",
    "they",
    "them",
}

R24_INDEFINITE_PRONOUNS = {
    "all",
    "another",
    "any",
    "anybody",
    "anything",
    "both",
    "each",
    "either",
    "every",
    "everybody",
    "everyone",
    "everything",
    "few",
    "many",
    "most",
    "much",
    "neither",
    "no one",
    "nobody",
    "none",
    "one",
    "several",
    "some",
    "somebody",
    "someone",
    "something",
    "such",
}

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
    source: str = "spacy",
) -> RuleViolation:
    return RuleViolation(
        rule_id=rule_id,
        rule_name=rule_name,
        issue=issue,
        suggestion=f"{suggestion} (Characteristics impacted: {_chars_for(rule_id)})",
        source=source,
    )


# Small utility: join token texts once to keep phrase checks consistent.
def _joined_lower(doc) -> str:
    return " ".join(token.text.lower() for token in doc)


# -----------------------------------------------------------------------------
# R1 - Structured Statements
# -----------------------------------------------------------------------------
def check_r1_structured_statements(text: str) -> List[RuleViolation]:
    """
    R1 - Structured Statements
    Need and requirement statements should conform to agreed patterns.

    spaCy contribution for this mixed-method rule:
    - If the text uses a requirement-style modal ("shall"), require an explicit
      subject and a main action verb after "shall".
    - If the text uses a need-style root verb ("need"), require an explicit
      subject and some object/complement for the need.
    - If neither signal is present, leave detection to the programmatic layer.
    """
    doc = nlp(text)
    shall_tokens = [t for t in doc if t.lower_ == "shall"]
    has_subject = any(t.dep_ in ("nsubj", "nsubjpass") for t in doc)

    if shall_tokens:
        has_main_action_after_shall = False
        for shall in shall_tokens:
            if any(
                t.i > shall.i and t.pos_ == "VERB" and t.dep_ not in ("aux", "auxpass")
                for t in doc
            ):
                has_main_action_after_shall = True
                break

        if has_subject and has_main_action_after_shall:
            return []

        issue = "Requirement-style wording is present, but the sentence does not clearly match a subject + 'shall' + action pattern."
        suggestion = (
            "Rewrite the statement to match an agreed requirement pattern with an explicit subject, "
            "'shall', and one clear action verb."
        )
        return [_mk_violation("R1", "Structured Statements", issue, suggestion)]

    need_tokens = [t for t in doc if t.lemma_.lower() == "need" and t.pos_ in ("VERB", "AUX")]
    if need_tokens:
        has_need_object = any(t.dep_ in ("dobj", "obj", "attr", "oprd", "xcomp", "ccomp") for t in doc)
        if has_subject and has_need_object:
            return []

        issue = "Need-style wording is present, but the sentence does not clearly match an agreed need statement pattern."
        suggestion = (
            "Rewrite the statement to match an agreed need pattern with an explicit subject, "
            "the need, and the needed object/action."
        )
        return [_mk_violation("R1", "Structured Statements", issue, suggestion)]

    return []


# -----------------------------------------------------------------------------
# R2 - Active Voice
# -----------------------------------------------------------------------------
def check_r2_active_voice(text: str) -> List[RuleViolation]:
    """
    R2 - Active Voice
    Definition: Write requirements in active voice.

    spaCy heuristic:
    - Detect passive voice using dependency labels 'auxpass' or 'nsubjpass'.
    """
    doc = nlp(text)
    passive_tokens = [t for t in doc if t.dep_ in ("auxpass", "nsubjpass")]

    if not passive_tokens:
        return []

    issue = "Requirement appears to be written in passive voice."
    suggestion = (
        "Rewrite using active voice so the responsible entity performs the action, "
        "e.g., '<entity> shall <action> ...'."
    )
    return [_mk_violation("R2", "Active Voice", issue, suggestion)]


# -----------------------------------------------------------------------------
# R5 - Definite Articles
# -----------------------------------------------------------------------------
def check_r5_definite_articles(text: str) -> List[RuleViolation]:
    """
    R5 - Definite Articles
    Use the definite article "the" rather than the indefinite article "a/an"
    when referring to entities.

    Conservative spaCy heuristic grounded in the PDF:
    - Flag singular noun phrases introduced by "a" or "an".
    - Exempt the explicit PDF exception "with an accuracy ...".
    - Exempt explicit either/or choice phrasing, where the PDF allows the
      logical intent to be stated explicitly.
    """
    doc = nlp(text)
    found: List[str] = []

    for token in doc:
        if token.lower_ not in ("a", "an") or token.dep_ != "det":
            continue

        head = token.head
        if head.lemma_.lower() == "accuracy":
            continue

        local_window = " ".join(t.text.lower() for t in doc[max(0, token.i - 2) : min(len(doc), head.right_edge.i + 3)])
        if "either" in local_window and " or " in local_window:
            continue

        if head.pos_ not in ("NOUN", "PROPN"):
            continue

        found.append(f"{token.text} {head.text}")

    if not found:
        return []

    issue = "Uses indefinite article phrasing for entity references: " + ", ".join(found) + "."
    suggestion = (
        "Use the definite article 'the' when a specific defined entity is intended, "
        "so the requirement does not read as 'any one of'."
    )
    return [_mk_violation("R5", "Definite Articles", issue, suggestion)]


# -----------------------------------------------------------------------------
# R11 - Separate Clauses
# -----------------------------------------------------------------------------
def check_r11_separate_clauses(text: str) -> List[RuleViolation]:
    """
    R11 - Separate Clauses
    Definition: Use a separate clause for each condition or qualification.

    spaCy heuristic:
    - Flag when multiple subordinate clauses / qualifiers are attached to the main clause.
    - Uses dependency structure rather than hardcoded word lists.
    """
    doc = nlp(text)

    # Subordinate clause-like structures that often carry conditions/qualifications
    # (advcl = adverbial clause modifier; relcl = relative clause modifier; ccomp/xcomp = clausal complements)
    clause_heads = [t for t in doc if t.dep_ in ("advcl", "relcl", "ccomp", "xcomp")]
    # Markers (e.g., subordinating conjunctions) often introduce conditions/qualifications
    markers = [t for t in doc if t.dep_ == "mark"]

    # Conservative threshold: only flag if there is clear evidence of multiple clause/qualification structures.
    if len(clause_heads) + len(markers) <= 1:
        return []

    issue = "Multiple conditions/qualifications appear to be combined within the same statement."
    suggestion = (
        "Split into separate requirement statements, repeating the triggering condition as needed, "
        "so each statement contains one action and one clear condition/qualification."
    )
    return [_mk_violation("R11", "Separate Clauses", issue, suggestion)]


# -----------------------------------------------------------------------------
# R12 - Correct Grammar
# -----------------------------------------------------------------------------
def check_r12_correct_grammar(text: str) -> List[RuleViolation]:
    """
    R12 - Correct Grammar
    Definition: Use correct grammar.

    spaCy heuristic:
    - Flag if sentence lacks a clear main verb (ROOT as VERB/AUX) or lacks a subject where one is expected.
    - This is a lightweight grammar signal, not a full grammar checker.
    """
    doc = nlp(text)

    roots = [t for t in doc if t.dep_ == "ROOT"]
    root = roots[0] if roots else None

    # Root should typically be a verb/aux in a well-formed statement
    root_ok = bool(root) and root.pos_ in ("VERB", "AUX")

    # Subject presence (active or passive) is a basic grammatical indicator
    has_subject = any(t.dep_ in ("nsubj", "nsubjpass") for t in doc)

    if root_ok and has_subject:
        return []

    problems: List[str] = []
    if not root_ok:
        problems.append("no clear main verb")
    if not has_subject:
        problems.append("no explicit subject")

    issue = "Requirement may not use correct grammar (" + ", ".join(problems) + ")."
    suggestion = (
        "Rewrite the statement using correct grammar with a clear subject and main verb, "
        "consistent with the agreed requirement/need statement patterns."
    )
    return [_mk_violation("R12", "Correct Grammar", issue, suggestion)]


# -----------------------------------------------------------------------------
# R18 - Single-thought Sentence
# -----------------------------------------------------------------------------
def check_r18_single_thought_sentence(text: str) -> List[RuleViolation]:
    """
    R18 - Single-thought Sentence
    Definition: Write a single sentence that contains a single thought conditioned and qualified by
    relevant sub-clauses.

    spaCy heuristic:
    - Flag if multiple main actions are present (multiple non-aux verbs that are ROOT/conj).
    """
    doc = nlp(text)

    if sum(1 for _ in doc.sents) > 1:
        issue = "Requirement appears to be written as more than one sentence."
        suggestion = (
            "Write one single sentence containing one single thought, with any needed conditions "
            "or qualifications expressed as subordinate clauses."
        )
        return [_mk_violation("R18", "Single-thought Sentence", issue, suggestion)]

    main_verbs = []
    for t in doc:
        if t.pos_ != "VERB":
            continue
        # Ignore auxiliary verbs (spaCy tags AUX separately, but some verbs may still function as aux)
        if t.dep_ in ("aux", "auxpass"):
            continue
        # Treat ROOT verb and coordinated verbs as main actions
        if t.dep_ == "ROOT" or (t.dep_ == "conj" and t.head.dep_ == "ROOT"):
            main_verbs.append(t)

    # Conservative: if more than one main action, likely violates single-thought
    if len(main_verbs) <= 1:
        return []

    issue = f"Requirement appears to contain multiple actions ({len(main_verbs)} main verbs)."
    suggestion = (
        "Split into separate requirement statements so each contains exactly one main action/single thought; "
        "repeat any required trigger/condition in each resulting statement."
    )
    return [_mk_violation("R18", "Single-thought Sentence", issue, suggestion)]


# -----------------------------------------------------------------------------
# R19 - Combinators
# -----------------------------------------------------------------------------
def check_r19_combinators(text: str) -> List[RuleViolation]:
    """
    R19 - Combinators
    Avoid clause-joining words such as "and", "or", "then", "unless", etc.

    spaCy contribution for this mixed method rule:
    - Flag explicit multiword combinator phrases from the PDF.
    - Flag coordinating conjunctions that join verbs, objects, or clauses.
    - Exempt explicit EITHER/OR phrasing because the PDF treats that as an
      explicit logical expression rather than an implicit combinator problem.
    """
    doc = nlp(text)
    joined = _joined_lower(doc)
    found: List[str] = []

    explicit_either_or = "either" in joined and " or " in joined

    for phrase in sorted(R19_MULTIWORD_COMBINATORS):
        if phrase in joined:
            found.append(phrase)

    for token in doc:
        if token.lower_ not in R19_SINGLE_TOKEN_COMBINATORS:
            continue

        if token.lower_ == "or" and explicit_either_or:
            continue

        if token.dep_ != "cc":
            continue

        head = token.head
        if head.dep_ == "conj" or any(child.dep_ == "conj" for child in head.children):
            found.append(token.text)

    if not found:
        return []

    seen = set()
    unique = []
    for item in found:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    issue = "Uses clause-joining combinator(s) that may indicate multiple thoughts: " + ", ".join(unique) + "."
    suggestion = (
        "Break the statement into separate single-thought requirements, or rewrite the logic explicitly "
        "if a formal logical expression is intended."
    )
    return [_mk_violation("R19", "Combinators", issue, suggestion)]


# -----------------------------------------------------------------------------
# R24 - Pronouns
# -----------------------------------------------------------------------------
def check_r24_pronouns(text: str) -> List[RuleViolation]:
    """
    R24 - Pronouns
    Definition: Avoid the use of personal and indefinite pronouns.
    """
    doc = nlp(text)

    found: List[str] = []
    # Detect single-token pronouns
    for t in doc:
        tl = t.text.lower()
        if tl in R24_PERSONAL_PRONOUNS:
            found.append(t.text)
        # Indefinite pronouns: handle single-token items here; multi-token handled below
        if tl in R24_INDEFINITE_PRONOUNS:
            found.append(t.text)

    # Detect multi-token indefinite pronoun "no one" (as written in the Guide)
    joined = " ".join(t.text.lower() for t in doc)
    if "no one" in joined:
        found.append("no one")

    if not found:
        return []

    # De-duplicate while preserving order
    seen = set()
    found_unique = []
    for x in found:
        xl = x.lower()
        if xl not in seen:
            seen.add(xl)
            found_unique.append(x)

    issue = f"Uses pronoun(s) that the Guide recommends avoiding: {', '.join(found_unique)}."
    suggestion = (
        "Repeat the noun(s) in full instead of using pronouns, so the statement is not ambiguous "
        "when needs/requirements are reordered or managed as individual database entries."
    )
    return [_mk_violation("R24", "Pronouns", issue, suggestion)]


# -----------------------------------------------------------------------------
# R35 - Temporal Dependencies
# -----------------------------------------------------------------------------
def check_r35_temporal_dependencies(text: str) -> List[RuleViolation]:
    """
    R35 - Temporal Dependencies
    Replace indefinite temporal wording with explicit timing constraints.

    spaCy contribution for this mixed-method rule:
    - Detect temporal subordinators such as "before", "after", "until", "once",
      and "as" when they function as clause markers.
    - Detect adverb/adjective temporal keywords such as "eventually", "earliest",
      "latest", "instantaneous", and "simultaneous".
    - Detect the explicit phrase "at last".
    """
    doc = nlp(text)
    joined = _joined_lower(doc)
    found: List[str] = []

    if "at last" in joined:
        found.append("at last")

    for token in doc:
        tl = token.text.lower()

        if tl in R35_TEMPORAL_MARKERS and (token.dep_ == "mark" or token.pos_ in ("SCONJ", "ADV", "ADP")):
            found.append(token.text)
            continue

        if tl in R35_OTHER_TEMPORAL_KEYWORDS and token.pos_ in ("ADV", "ADJ"):
            found.append(token.text)

    if not found:
        return []

    seen = set()
    unique = []
    for item in found:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    issue = "Uses indefinite temporal wording: " + ", ".join(unique) + "."
    suggestion = (
        "Replace the indefinite temporal wording with an explicit, measurable timing or ordering constraint "
        "that can be verified."
    )
    return [_mk_violation("R35", "Temporal Dependencies", issue, suggestion)]


# -----------------------------------------------------------------------------
# Aggregate
# -----------------------------------------------------------------------------
SPACY_CHECKS: dict[str, Callable[[str], List[RuleViolation]]] = {
    "R1": check_r1_structured_statements,
    "R2": check_r2_active_voice,
    "R5": check_r5_definite_articles,
    "R11": check_r11_separate_clauses,
    "R12": check_r12_correct_grammar,
    "R18": check_r18_single_thought_sentence,
    "R19": check_r19_combinators,
    "R24": check_r24_pronouns,
    "R35": check_r35_temporal_dependencies,
}


def run_spacy_checks(req_text: str, allowed_rules: Optional[Set[str]] = None) -> List[RuleViolation]:
    active_ids = set(SPACY_CHECKS.keys()) if allowed_rules is None else (set(SPACY_CHECKS.keys()) & allowed_rules)

    violations: List[RuleViolation] = []
    for rid in sorted(active_ids):
        violations.extend(SPACY_CHECKS[rid](req_text))
    return violations
