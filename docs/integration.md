# Nocturne Ecosystem Integration

## Overview

The Nocturne ecosystem is composed of independent tools with clearly defined responsibilities.

Each tool should solve one problem well.

No component should duplicate the responsibilities of another.

---

## Nocturne Inspector

The Inspector is the Engineering Intelligence Engine.

Its responsibility is to understand software through deterministic analysis.

The Inspector:

- inspects projects
- collects evidence
- analyzes architecture
- evaluates security
- examines documentation
- identifies engineering risks
- produces structured reports

The Inspector never:

- modifies source code
- applies fixes
- executes Git operations
- rewrites projects

---

## Nocturne Codex

The Codex is the Engineering Execution Engine.

Its responsibility is to help developers plan, approve, implement and validate changes.

The Codex:

- imports engineering intelligence
- presents findings
- creates implementation plans
- manages approvals
- executes modifications
- validates results

The Codex should never reproduce deterministic analysis already provided by the Inspector.

---

## Communication

The Inspector and the Codex communicate through a versioned inspection report.
The contract is documented in [report-schema.md](report-schema.md) and defined
formally by [inspection-report.schema.json](inspection-report.schema.json).

Generating an inspection report and persisting it are separate operations.
Analysis never creates or modifies files in the inspected workspace. A report
is written only when the user explicitly supplies an output path. That path may
be inside the inspected project when chosen consciously by the user, but its
parent directory must already exist and an existing file is never overwritten
without explicit permission. Symbolic-link destinations are rejected so report
output cannot be redirected to an unexpected file.

Example:

Project

↓

Nocturne Inspector

↓

inspection.json

↓

Nocturne Codex

↓

Review

↓

Planning

↓

Implementation

↓

Validation

---

## Separation of Responsibilities

Inspector

✓ Read-only

✓ Deterministic

✓ Evidence-based

✓ Stateless

Codex

✓ Interactive

✓ Planning

✓ User approval

✓ Source code modification

✓ Validation

---

## Design Principle

The Inspector understands software.

The Codex transforms understanding into implementation.

Together they create an engineering workflow based on:

Understand

↓

Plan

↓

Implement

↓

Validate

## Future Integration

Future versions of the Nocturne Codex may invoke the Inspector directly.

The Inspector should remain an independent application.

Communication should occur exclusively through versioned and documented contracts.

The Inspector must remain usable as a standalone CLI outside of the Nocturne ecosystem.
