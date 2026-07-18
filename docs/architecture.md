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

The v0.1 foundation uses a workspace `Path` as the input shared by the
inspector contract and the sequential inspection pipeline. The registry owns
inspector discovery, and the pipeline owns orchestration and report assembly.
Specialists remain independent and receive no knowledge of one another.

Filesystem Scanner, Project Graph, and Language Detection remain explicit
future architecture stages. The v0.1 pipeline does not emulate them or claim
to produce their outputs. When those stages are implemented, they must be
introduced behind a documented contract without moving specialist analysis or
report persistence into the CLI.
