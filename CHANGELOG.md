## [0.2.0] - 2026-09-12

### 🚀 Features

- Group unknown modules to clear up graph
- Add output argument to write directly into a file
- Handle cyclic imports by merging them into groups and add mutual edge rendering

### 📚 Documentation

- Fix python execution command
- Add docs about merging, grouping and recursion
- Use inline mermaid for result examples
- Add coloring to mermaid examples

### ⚙️ Miscellaneous Tasks

- Use mermaid-py to visualize mermaid
- Add build system definition
- Add git-cliff
## [0.1.0] - 2026-03-14

### 🚀 Features

- Add support for anonymous functions and unknown modules
- Add support for aarch64-linux
- Add mermaid format

### 🐛 Bug Fixes

- Add missing types

### 🚜 Refactor

- Add __eq__ to all classes
- Add helper function to create test graphs
- Create module for nixoscope
- Use strategy pattern for visualizers

### 📚 Documentation

- Fix typo
- Add proper documentation
- Update readme

### 🧪 Testing

- Add tests for ModuleGraphEdge
- Add tests for ModuleGraph
- Add option filter tests

### ⚙️ Miscellaneous Tasks

- Prepare for nixpkgs release
- Add checkphase to flake
- Ignore print statement in linter
- Add graphs to gitignore
- Print version in help page
