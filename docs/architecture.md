Workspace

↓

Filesystem Scanner

↓

Project Graph

↓

Language Detection

↓

Specialists

↓

Master Inspector

↓

Engineering Report

## v0.1 foundation boundary

The v0.1 foundation scans a workspace once and shares an immutable
`ProjectContext` with every specialist. The context contains the resolved root,
an ordered inventory of project-relative regular files, detected languages,
and the active directory-exclusion policy. Symbolic links are never included
or followed. A filesystem access error aborts context creation instead of
silently producing a partial inventory.

The default scanner excludes these directory names wherever they occur:
`.git`, `.idea`, `.mypy_cache`, `.nocturne`, `.pytest_cache`, `.ruff_cache`,
`.venv`, `.vscode`, `__pycache__`, `build`, `coverage`, `dist`, `logs`,
`node_modules`, `out`, and `release`. Language detection is an explicit,
case-insensitive extension map for C, C++, C#, Go, Java, JavaScript, Kotlin,
PHP, Python, Ruby, Rust, Scala, Shell, Swift, and TypeScript. Unknown extensions
remain in the inventory but do not produce a language claim.

The pipeline owns context creation, orchestration, and report assembly. The
registry owns inspector discovery. Specialists remain independent, receive the
same context instance, and receive no knowledge of one another. Project Graph
remains a future architecture stage and must be introduced behind a documented
contract without moving specialist analysis or report persistence into the
CLI.
