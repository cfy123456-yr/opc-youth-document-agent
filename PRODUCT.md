# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Inferred from the existing Python project and the instruction to continue without a
structured stack question: Python 3.11+ standard library HTTP server, static HTML,
CSS, and JavaScript. No JavaScript framework is required. This keeps the local web
MVP usable without adding runtime dependencies while preserving the existing CLI.

## Users

Chinese young people who are entering the job market, starting an internship, signing
a first lease or employment agreement, or organizing reimbursements. They need help
turning unfamiliar documents into understandable, reviewable, and exportable results.

## Product Purpose

The product gives a single local-first workflow for resumes, personal letters,
contracts, and receipts. It parses a document, routes the task, runs a specialized
workflow, exposes evidence and warnings, and exports a Markdown report plus structured
JSON. Success means a user can complete one document task end to end without an API
key and can clearly see what must be reviewed before acting.

## Positioning

The agent combines four youth document tasks behind one task router, one result model,
one fact policy, and one review boundary. It is not a general chatbot and does not
claim to replace legal, financial, or hiring professionals.

## Operating Context

Users work from a desktop or phone browser on local files or pasted text. They may
not have an OCR stack installed. The current release therefore prioritizes plain text,
Markdown, JSON, CSV, DOCX, and optional PDF or image parsing. Reports stay local and
are generated under the project output directory.

## Capabilities and Constraints

- Task types: resume, letter, contract, receipt, and automatic routing.
- Local rules run in `mock` mode without a model API key.
- A third-party online model service is optional and is only used after explicit
  configuration.
- Contract output is risk assistance only and is not legal advice.
- Receipt totals are calculated from extracted rows and must be checked against the
  original documents.
- Resume and letter workflows must not invent experience, numbers, certificates, or
  promises.
- The web MVP must not submit, sign, or send documents on the user's behalf.
- Upload and processing must work locally and expose clear error states.

## Brand Commitments

The confirmed product name is 青年文书智能助手. The interface should feel calm,
precise, and practical rather than promotional. It should not use legal-sounding
certainty where the output is only a review aid.

## Evidence on Hand

- Working Python package and CLI under `opc_agent/`.
- Example resume, job description, letter, contract, and receipt files under
  `examples/`.
- 12-case JSONL evaluation set under `evals/cases.jsonl`.
- Verified tests and generated sample reports under `outputs/`.
- No real customer testimonials, compliance certifications, legal conclusions, or
  production usage benchmarks are available yet. Future interface work must not
  fabricate them.

## Product Principles

1. Local-first and useful without a paid model.
2. Keep facts attached to source evidence.
3. Put high-risk boundaries in the result, not in a hidden disclaimer.
4. Make the next action obvious: upload, inspect, confirm, export.
5. Add product surface only after the underlying workflow is reliable.

## Accessibility & Inclusion

The interface must work with keyboard navigation, visible focus, 44px minimum touch
targets, readable contrast, reduced-motion preferences, and responsive layouts from
390px mobile width to desktop.
