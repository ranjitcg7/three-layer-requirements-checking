# Three-Layer Requirements Checking

A hybrid workflow for detecting requirement-writing rule violations using three complementary layers:

- **Programmatic checks** for deterministic and rule-based violations
- **spaCy-based NLP checks** for grammar and sentence structure
- **LLM checks** for semantic and contextual judgment

The main idea is simple: not every requirement issue needs an LLM.

This repository separates rule checking into three layers so that each method is used where it performs best:
- **code** for strict rule-based patterns
- **NLP** for linguistic structure
- **LLM** for genuine reasoning tasks

## Files

- `rules_programmatic.py` — deterministic checks for issues such as vague terms, escape clauses, open-ended clauses, missing units, absolutes, acronyms, abbreviations, and decimal formatting
- `rules_nlp.py` — spaCy-based checks for issues such as passive voice, grammar, pronouns, combinators, temporal wording, and sentence-structure problems
- `rules_llm.py` — LLM-based checks for semantic rules such as appropriate subject-verb usage, solution-free wording, measurable performance, explicit conditions, and contextual interpretation

## Purpose

This project supports a more engineering-oriented approach to requirements checking: use the right tool for the right kind of violation.
