# three-layer-requirements-checking
A hybrid requirements-checking workflow that detects rule violations using programmatic checks, NLP, and LLM-based semantic analysis.
Three-Layer Requirements Checking

A hybrid requirements-checking workflow for detecting requirement-writing rule violations using three complementary layers:

Programmatic checks for deterministic and rule-based violations
NLP checks (spaCy) for grammar, voice, pronouns, and sentence structure
LLM checks for semantic and contextual judgment

This repository supports the idea that not every requirement issue needs an LLM. Some violations are better handled with simple code, some with lightweight linguistic analysis, and only a smaller subset truly requires semantic reasoning.

Why this repository

In requirements engineering, using an LLM for every rule check is often expensive, less transparent, and not always the most reliable choice.

Many violations are deterministic:

vague terms
escape clauses
open-ended phrases
missing units
absolutes
punctuation or decimal-format issues

Some violations are more about sentence structure:

passive voice
pronoun use
multiple clauses
single-thought violations
temporal dependency wording

Only some rules really need deeper interpretation:

appropriate subject-verb usage
solution-free wording
measurable performance in context
explicit conditions
logical ambiguity
set-level or contextual judgments

This repository implements that split directly.

Repository structure
three-layer-requirements-checking/
│
├── rules_programmatic.py   # deterministic rule checks
├── rules_nlp.py            # spaCy-based linguistic checks
├── rules_llm.py            # LLM-based semantic checks
└── README.md
Three-layer workflow
1. Programmatic layer

This layer handles violations that can be detected through:

keyword lists
regular expressions
explicit textual patterns
lightweight heuristics

Examples include:

vague terms
escape clauses
open-ended clauses
superfluous infinitives
use of "not"
oblique symbol /
purpose phrases
parentheses
absolutes
universal qualification
temporal keywords
acronyms, abbreviations, style-guide issues
decimal-format issues
2. NLP layer

This layer uses spaCy to inspect sentence structure and grammar.

Examples include:

active vs passive voice
definite vs indefinite articles
separate clauses
correct grammar
single-thought sentence detection
combinators
pronouns
temporal dependency wording
3. LLM layer

This layer is used only where semantic interpretation or contextual judgment is needed.

Examples include:

appropriate subject-verb alignment
logical expressions
implicit vs explicit conditions
solution-free wording
measurable performance
range of values
enumeration in context
complex behavior requiring supporting diagrams/models
set-level or organizational rules where enough context exists
Core idea

The goal is not to replace engineering judgment with AI.

The goal is to use:

code where rules are deterministic
NLP where structure matters
LLM only where genuine reasoning is needed

This makes the workflow:

more transparent
more testable
more efficient
easier to trust
Example philosophy

Using an LLM for every requirement check is like using a hammer to drive a screw.

A stronger workflow uses the right tool for the right kind of violation.

Files
rules_programmatic.py

Contains rule checks based on deterministic logic, phrase matching, regex patterns, and project-configurable resources such as glossary terms, units, acronyms, abbreviations, and style-guide patterns. It exposes run_programmatic_checks() and run_coded_checks() for execution.

rules_nlp.py

Contains spaCy-based checks for linguistic structure and grammar. The module loads en_core_web_sm and exposes run_spacy_checks() for applying supported NLP-based rule checks.

rules_llm.py

Contains prompt-driven LLM checks for rules that require semantic judgment. The module builds rule-specific prompts, calls the LLM, parses JSON responses, and returns structured rule violations.

Usage idea

A typical pipeline would look like this:

Run programmatic checks
Run spaCy checks
Run LLM checks only for selected semantic rules
Merge all violations into one report
Use that report for downstream requirement rewriting or human review
Notes
Some rules are naturally single-statement checks
Some rules are context-sensitive
Some rules are set-level and cannot be judged reliably from one isolated requirement alone

This repository reflects that distinction instead of pretending all rules can be solved the same way.

Related blog posts

This repository accompanies blog posts discussing:

why LLMs should not be used for every rule violation
how a hybrid checking pipeline works
how patterns and TBDs improve rewriting quality
Status

This repository is intended as a practical reference for hybrid rule checking in requirements engineering and can be extended with:

additional rules
project-specific glossaries
set-level analysis
requirement rewriting support
traceability and reporting features
