"""Dependency analysis engine.

Analyzes import relationships, function calls, class usage, and inheritance
patterns to build a complete dependency map of the codebase.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Set

from loguru import logger

from app.core.parser import CodeParser, _load_language
from app.models.schemas import (
    Dependency,
    DependencyType,
    ParsedFile,
)


class DependencyAnalyzer:
    """Analyzes code dependencies across parsed files."""

    def __init__(self) -> None:
        self.parser = CodeParser()

    def analyze_all(
        self, parsed_files: List[ParsedFile]
    ) -> List[Dependency]:
        """Run all dependency analyses and return combined results.

        Args:
            parsed_files: List of parsed source files.

        Returns:
            Combined list of all discovered dependencies.
        """
        dependencies: List[Dependency] = []

        dependencies.extend(self.analyze_imports(parsed_files))
        dependencies.extend(self.analyze_calls(parsed_files))
        dependencies.extend(self.analyze_class_usage(parsed_files))
        dependencies.extend(self.analyze_containment(parsed_files))

        logger.info(f"Discovered {len(dependencies)} dependencies across {len(parsed_files)} files")
        return dependencies

    analyze = analyze_all

    # ──────────────────────────────────────────
    # Import analysis
    # ──────────────────────────────────────────

    def analyze_imports(
        self, parsed_files: List[ParsedFile]
    ) -> List[Dependency]:
        """Analyze import statements to find file-level and symbol-level dependencies."""
        dependencies: List[Dependency] = []
        file_lookup = self._build_file_lookup(parsed_files)

        # Build map of file_path -> set of known function/class names
        file_symbols: Dict[str, Set[str]] = {}
        for pf in parsed_files:
            symbols = set()
            for f in pf.functions:
                symbols.add(f.name)
            for c in pf.classes:
                symbols.add(c.name)
                for m in c.methods:
                    symbols.add(m.name)
            file_symbols[pf.file_path] = symbols

        for pf in parsed_files:
            for imp in pf.imports:
                resolved = self._resolve_import(imp.module, pf.file_path, file_lookup)
                if resolved:
                    # 1. File -> File import
                    dependencies.append(
                        Dependency(
                            source=pf.file_path,
                            target=resolved,
                            dep_type=DependencyType.IMPORTS,
                            source_location=imp.location,
                            metadata={"module": imp.module, "names": imp.names},
                        )
                    )

                    # 2. File -> Specific imported functions/classes
                    resolved_syms = file_symbols.get(resolved, set())
                    for name in imp.names:
                        if name in resolved_syms:
                            target_qualified = f"{resolved}::{name}"
                            dependencies.append(
                                Dependency(
                                    source=pf.file_path,
                                    target=target_qualified,
                                    dep_type=DependencyType.DEPENDS_ON,
                                    source_location=imp.location,
                                    metadata={"module": imp.module, "imported_symbol": name},
                                )
                            )

        logger.debug(f"Found {len(dependencies)} import dependencies")
        return dependencies

    # ──────────────────────────────────────────
    # Call analysis
    # ──────────────────────────────────────────

    def analyze_calls(
        self, parsed_files: List[ParsedFile]
    ) -> List[Dependency]:
        """Analyze function calls to find caller → callee relationships."""
        dependencies: List[Dependency] = []

        # Build lookup: function name → list of qualified names
        func_lookup: Dict[str, List[str]] = {}
        file_funcs: Dict[str, Set[str]] = {}

        for pf in parsed_files:
            file_funcs[pf.file_path] = set()
            for func in pf.functions:
                if func.name not in func_lookup:
                    func_lookup[func.name] = []
                func_lookup[func.name].append(func.qualified_name)
                file_funcs[pf.file_path].add(func.qualified_name)

            for cls in pf.classes:
                if cls.name not in func_lookup:
                    func_lookup[cls.name] = []
                func_lookup[cls.name].append(cls.qualified_name)
                file_funcs[pf.file_path].add(cls.qualified_name)

                for method in cls.methods:
                    key = f"{cls.name}.{method.name}"
                    if key not in func_lookup:
                        func_lookup[key] = []
                    func_lookup[key].append(method.qualified_name)
                    if method.name not in func_lookup:
                        func_lookup[method.name] = []
                    func_lookup[method.name].append(method.qualified_name)
                    file_funcs[pf.file_path].add(method.qualified_name)

        # Build file lookup for resolving imports per file
        file_lookup = self._build_file_lookup(parsed_files)

        for pf in parsed_files:
            if not pf.raw_content:
                continue

            # Determine files that pf directly imports
            imported_files = set()
            for imp in pf.imports:
                res = self._resolve_import(imp.module, pf.file_path, file_lookup)
                if res:
                    imported_files.add(res)

            source_bytes = pf.raw_content.encode("utf-8")

            try:
                lang_obj, parser = _load_language(pf.language)
                tree = parser.parse(source_bytes)
                calls = self.parser.extract_calls(
                    tree.root_node, source_bytes, pf.file_path, pf.language, lang_obj
                )
            except (ValueError, ImportError):
                continue

            seen_edges: Set[Tuple[str, str]] = set()

            for call in calls:
                call_name = call["name"]
                targets = func_lookup.get(call_name, [])
                if not targets:
                    continue

                caller = self._find_enclosing_function(call["line"], pf)
                source_name = caller or pf.file_path

                # Prioritize target:
                # 1. Same file
                # 2. In an imported file
                # 3. In other files (if single target or fallback)
                chosen_target = None
                for t in targets:
                    t_file = t.split("::")[0]
                    if t_file == pf.file_path and source_name != t:
                        chosen_target = t
                        break
                    elif t_file in imported_files:
                        chosen_target = t
                        break

                if not chosen_target and len(targets) == 1:
                    if source_name != targets[0]:
                        chosen_target = targets[0]

                target_list = [chosen_target] if chosen_target else [t for t in targets if t != source_name][:2]

                for target in target_list:
                    edge_key = (source_name, target)
                    if edge_key not in seen_edges and source_name != target:
                        seen_edges.add(edge_key)
                        dependencies.append(
                            Dependency(
                                source=source_name,
                                target=target,
                                dep_type=DependencyType.CALLS,
                                metadata={
                                    "call_name": call_name,
                                    "line": call["line"],
                                },
                            )
                        )

        logger.debug(f"Found {len(dependencies)} call dependencies")
        return dependencies

    # ──────────────────────────────────────────
    # Class usage / inheritance
    # ──────────────────────────────────────────

    def analyze_class_usage(
        self, parsed_files: List[ParsedFile]
    ) -> List[Dependency]:
        """Analyze class inheritance and usage patterns."""
        dependencies: List[Dependency] = []

        # Build class lookup: class name → qualified name
        class_lookup: Dict[str, str] = {}
        for pf in parsed_files:
            for cls in pf.classes:
                class_lookup[cls.name] = cls.qualified_name

        # Find inheritance relationships
        for pf in parsed_files:
            for cls in pf.classes:
                for base in cls.bases:
                    base_name = base.split(".")[-1].strip()
                    if base_name in class_lookup:
                        dependencies.append(
                            Dependency(
                                source=cls.qualified_name,
                                target=class_lookup[base_name],
                                dep_type=DependencyType.INHERITS,
                                metadata={"base_class": base_name},
                            )
                        )

        logger.debug(f"Found {len(dependencies)} class dependencies")
        return dependencies

    # ──────────────────────────────────────────
    # Containment analysis
    # ──────────────────────────────────────────

    def analyze_containment(
        self, parsed_files: List[ParsedFile]
    ) -> List[Dependency]:
        """Analyze file→class→function containment relationships."""
        dependencies: List[Dependency] = []

        for pf in parsed_files:
            # File contains top-level functions
            for func in pf.functions:
                if not func.is_method:
                    dependencies.append(
                        Dependency(
                            source=pf.file_path,
                            target=func.qualified_name,
                            dep_type=DependencyType.CONTAINS,
                        )
                    )

            # File contains classes
            for cls in pf.classes:
                dependencies.append(
                    Dependency(
                        source=pf.file_path,
                        target=cls.qualified_name,
                        dep_type=DependencyType.CONTAINS,
                    )
                )
                # Class contains methods
                for method in cls.methods:
                    dependencies.append(
                        Dependency(
                            source=cls.qualified_name,
                            target=method.qualified_name,
                            dep_type=DependencyType.CONTAINS,
                        )
                    )

        logger.debug(f"Found {len(dependencies)} containment dependencies")
        return dependencies

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _build_file_lookup(parsed_files: List[ParsedFile]) -> Dict[str, str]:
        """Build a lookup from possible module names to file paths."""
        lookup: Dict[str, str] = {}

        for pf in parsed_files:
            fp = pf.file_path.replace("\\", "/")

            # Register by filename (without extension)
            basename = os.path.splitext(os.path.basename(fp))[0]
            lookup[basename] = fp

            # Register by dotted module path
            # e.g., "app/core/parser.py" → "app.core.parser"
            module_path = fp.replace("/", ".").replace("\\", ".")
            for ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go"):
                module_path = module_path.replace(ext, "")
            lookup[module_path] = fp

            # Register partial paths
            parts = module_path.split(".")
            for i in range(len(parts)):
                partial = ".".join(parts[i:])
                if partial not in lookup:
                    lookup[partial] = fp

        return lookup

    @staticmethod
    def _resolve_import(
        module: str,
        source_file: str,
        file_lookup: Dict[str, str],
    ) -> Optional[str]:
        """Try to resolve an import module name to a file path."""
        if not module:
            return None

        clean_src = source_file.replace("\\", "/")

        # 1. Handle relative paths (e.g., "./config/db", "../models/userModel")
        if module.startswith("."):
            src_dir = os.path.dirname(clean_src)
            norm_path = os.path.normpath(os.path.join(src_dir, module)).replace("\\", "/")

            # Check direct or with extensions
            for ext in ("", ".js", ".jsx", ".ts", ".tsx", ".py", ".json", "/index.js", "/index.jsx", "/index.ts", "/index.tsx"):
                candidate = norm_path + ext
                if candidate in file_lookup.values():
                    if candidate != clean_src:
                        return candidate

            # Also check basename of norm_path
            norm_base = os.path.basename(norm_path)
            if norm_base in file_lookup and file_lookup[norm_base] != clean_src:
                return file_lookup[norm_base]

        # 2. Handle alias paths (e.g. "@/components/Button", "~/lib/utils")
        if module.startswith(("@/", "~/")):
            rel = module[2:]
            for candidate_prefix in ("", "src/", "app/", "lib/"):
                candidate_path = candidate_prefix + rel
                for ext in ("", ".js", ".jsx", ".ts", ".tsx", ".py", "/index.js", "/index.jsx", "/index.ts", "/index.tsx"):
                    cand = candidate_path + ext
                    if cand in file_lookup.values() and cand != clean_src:
                        return cand
            # Check basename in file_lookup
            base = os.path.basename(rel)
            if base in file_lookup and file_lookup[base] != clean_src:
                return file_lookup[base]

        # 3. Direct match in lookup table
        if module in file_lookup:
            resolved = file_lookup[module]
            if resolved != clean_src:
                return resolved

        # 4. Clean module path and check basename or dotted path
        clean_mod = module.replace("/", ".").replace("\\", ".")
        if clean_mod in file_lookup:
            resolved = file_lookup[clean_mod]
            if resolved != clean_src:
                return resolved

        # 5. Try suffix components
        parts = clean_mod.split(".")
        for i in range(len(parts)):
            partial = ".".join(parts[i:])
            if partial in file_lookup:
                resolved = file_lookup[partial]
                if resolved != clean_src:
                    return resolved

        # 6. Try matching basename in file_lookup
        mod_base = os.path.basename(module)
        if mod_base in file_lookup and file_lookup[mod_base] != clean_src:
            return file_lookup[mod_base]

        return None

    @staticmethod
    def _find_enclosing_function(
        line: int, parsed_file: ParsedFile
    ) -> Optional[str]:
        """Find the function/method that contains a given line number."""
        best_match: Optional[str] = None
        best_range = float("inf")

        for func in parsed_file.functions:
            if func.location.start_line <= line <= func.location.end_line:
                func_range = func.location.end_line - func.location.start_line
                if func_range < best_range:
                    best_range = func_range
                    best_match = func.qualified_name

        for cls in parsed_file.classes:
            for method in cls.methods:
                if method.location.start_line <= line <= method.location.end_line:
                    method_range = method.location.end_line - method.location.start_line
                    if method_range < best_range:
                        best_range = method_range
                        best_match = method.qualified_name

        return best_match
