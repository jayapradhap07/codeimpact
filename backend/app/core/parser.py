"""Tree-sitter based code parser.

Parses source files into ASTs and extracts structured code elements:
functions, classes, imports, methods, variables, and API endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.models.schemas import (
    ClassInfo,
    CodeLocation,
    FunctionInfo,
    ImportInfo,
    ParsedFile,
)

# ──────────────────────────────────────────────
# Tree-sitter language loading
# ──────────────────────────────────────────────

_LANGUAGES: Dict[str, Any] = {}
_PARSERS: Dict[str, Any] = {}


def _load_language(lang: str):
    """Lazily load a tree-sitter language grammar and parser."""
    if lang in _LANGUAGES:
        return _LANGUAGES[lang], _PARSERS[lang]

    try:
        from tree_sitter import Language, Parser

        if lang == "python":
            import tree_sitter_python as ts_lang
            raw_lang = ts_lang.language()
        elif lang == "javascript":
            import tree_sitter_javascript as ts_lang
            raw_lang = ts_lang.language()
        elif lang == "typescript":
            import tree_sitter_typescript as ts_lang
            raw_lang = ts_lang.language_typescript() if hasattr(ts_lang, "language_typescript") else ts_lang.language()
        elif lang == "java":
            import tree_sitter_java as ts_lang
            raw_lang = ts_lang.language()
        elif lang == "go":
            import tree_sitter_go as ts_lang
            raw_lang = ts_lang.language()
        elif lang == "c":
            import tree_sitter_c as ts_lang
            raw_lang = ts_lang.language()
        else:
            raise ValueError(f"Unsupported language: {lang}")

        language = Language(raw_lang)
        parser = Parser(language)
        _LANGUAGES[lang] = language
        _PARSERS[lang] = parser
        return language, parser

    except ImportError as e:
        logger.warning(f"Tree-sitter grammar for '{lang}' not installed: {e}")
        raise


# ──────────────────────────────────────────────
# Language-specific query definitions
# ──────────────────────────────────────────────

QUERIES: Dict[str, Dict[str, str]] = {
    "python": {
        "functions": """
            (function_definition
              name: (identifier) @func.name
              parameters: (parameters) @func.params
            ) @func.def
        """,
        "classes": """
            (class_definition
              name: (identifier) @class.name
            ) @class.def
        """,
        "imports": """
            [
              (import_statement
                name: (dotted_name) @import.module
              ) @import.def
              (import_from_statement
                module_name: (dotted_name) @import.module
              ) @import.def
            ]
        """,
        "decorators": """
            (decorator
              (identifier) @decorator.name
            )
        """,
        "calls": """
            (call
              function: [
                (identifier) @call.name
                (attribute
                  attribute: (identifier) @call.name
                )
              ]
            ) @call.def
        """,
    },
    "javascript": {
        "functions": """
            [
              (function_declaration
                name: (identifier) @func.name
                parameters: (formal_parameters) @func.params
              ) @func.def
              (variable_declarator
                name: (identifier) @func.name
                value: [
                  (arrow_function)
                  (function_expression)
                  (call_expression
                    arguments: (arguments [(arrow_function) (function_expression)])
                  )
                ]
              ) @func.def
              (assignment_expression
                left: (member_expression
                  object: [(identifier) (member_expression)]
                  property: (property_identifier) @func.name
                )
                right: [
                  (arrow_function)
                  (function_expression)
                  (call_expression
                    arguments: (arguments [(arrow_function) (function_expression)])
                  )
                ]
              ) @func.def
              (method_definition
                name: [(property_identifier) (identifier)] @func.name
                parameters: (formal_parameters) @func.params
              ) @func.def
            ]
        """,
        "classes": """
            [
              (class_declaration
                name: (identifier) @class.name
              ) @class.def
              (class
                name: (identifier) @class.name
              ) @class.def
            ]
        """,
        "imports": """
            [
              (import_statement
                source: (string) @import.module
              ) @import.def
              (export_statement
                source: (string) @import.module
              ) @import.def
              (call_expression
                function: (identifier) @req_id
                arguments: (arguments (string) @import.module)
              ) @import.def
            ]
        """,
        "calls": """
            [
              (call_expression
                function: [
                  (identifier) @call.name
                  (member_expression
                    property: (property_identifier) @call.name
                  )
                ]
              )
              (call_expression
                arguments: (arguments [
                  (identifier) @call.name
                  (member_expression
                    property: (property_identifier) @call.name
                  )
                ])
              )
              (new_expression
                constructor: [
                  (identifier) @call.name
                  (member_expression
                    property: (property_identifier) @call.name
                  )
                ]
              )
              (jsx_opening_element
                name: (identifier) @call.name
              )
              (jsx_self_closing_element
                name: (identifier) @call.name
              )
            ] @call.def
        """,
    },
    "typescript": {
        "functions": """
            [
              (function_declaration
                name: (identifier) @func.name
                parameters: (formal_parameters) @func.params
              ) @func.def
              (variable_declarator
                name: (identifier) @func.name
                value: [
                  (arrow_function)
                  (function_expression)
                  (call_expression
                    arguments: (arguments [(arrow_function) (function_expression)])
                  )
                ]
              ) @func.def
              (assignment_expression
                left: (member_expression
                  object: [(identifier) (member_expression)]
                  property: (property_identifier) @func.name
                )
                right: [
                  (arrow_function)
                  (function_expression)
                  (call_expression
                    arguments: (arguments [(arrow_function) (function_expression)])
                  )
                ]
              ) @func.def
              (method_definition
                name: [(property_identifier) (identifier)] @func.name
                parameters: (formal_parameters) @func.params
              ) @func.def
            ]
        """,
        "classes": """
            [
              (class_declaration
                name: (type_identifier) @class.name
              ) @class.def
              (class
                name: (type_identifier) @class.name
              ) @class.def
            ]
        """,
        "imports": """
            [
              (import_statement
                source: (string) @import.module
              ) @import.def
              (export_statement
                source: (string) @import.module
              ) @import.def
              (call_expression
                function: (identifier) @req_id
                arguments: (arguments (string) @import.module)
              ) @import.def
            ]
        """,
        "calls": """
            [
              (call_expression
                function: [
                  (identifier) @call.name
                  (member_expression
                    property: (property_identifier) @call.name
                  )
                ]
              )
              (call_expression
                arguments: (arguments [
                  (identifier) @call.name
                  (member_expression
                    property: (property_identifier) @call.name
                  )
                ])
              )
              (new_expression
                constructor: [
                  (identifier) @call.name
                  (member_expression
                    property: (property_identifier) @call.name
                  )
                ]
              )
              (jsx_opening_element
                name: (identifier) @call.name
              )
              (jsx_self_closing_element
                name: (identifier) @call.name
              )
            ] @call.def
        """,
    },
    "java": {
        "functions": """
            (method_declaration
              name: (identifier) @func.name
              parameters: (formal_parameters) @func.params
            ) @func.def
        """,
        "classes": """
            [
              (class_declaration
                name: (identifier) @class.name
              ) @class.def
              (interface_declaration
                name: (identifier) @class.name
              ) @class.def
            ]
        """,
        "imports": """
            (import_declaration
              (scoped_identifier) @import.module
            ) @import.def
        """,
        "calls": """
            (method_invocation
              name: (identifier) @call.name
            ) @call.def
        """,
    },
    "go": {
        "functions": """
            (function_declaration
              name: (identifier) @func.name
              parameters: (parameter_list) @func.params
            ) @func.def
        """,
        "classes": """
            (type_declaration
              (type_spec
                name: (type_identifier) @class.name
              )
            ) @class.def
        """,
        "imports": """
            (import_spec
              path: (interpreted_string_literal) @import.module
            ) @import.def
        """,
        "calls": """
            (call_expression
              function: [
                (identifier) @call.name
                (selector_expression
                  field: (field_identifier) @call.name
                )
              ]
            ) @call.def
        """,
    },
    "c": {
        "functions": """
            (function_definition
              declarator: (function_declarator
                declarator: (identifier) @func.name
                parameters: (parameter_list) @func.params
              )
            ) @func.def
        """,
        "classes": """
            (struct_specifier
              name: (type_identifier) @class.name
            ) @class.def
        """,
        "imports": """
            (preproc_include
              path: [
                (string_literal) @import.module
                (system_lib_string) @import.module
              ]
            ) @import.def
        """,
        "calls": """
            (call_expression
              function: (identifier) @call.name
            ) @call.def
        """,
    },
}


class CodeParser:
    """Parses source files using Tree-sitter to extract code elements."""

    def __init__(self) -> None:
        self._loaded_languages: set = set()

    def parse_file(self, file_path: Path, language: Optional[str] = None) -> ParsedFile:
        """Parse a single source file and extract all code elements.

        Args:
            file_path: Path to the source file.
            language: Optional language identifier (e.g., "python", "javascript").
                      If None, auto-detected from file extension.

        Returns:
            ParsedFile with extracted functions, classes, imports, etc.
        """
        path_obj = Path(file_path)
        if language is None:
            ext = path_obj.suffix.lower()
            ext_map = {
                ".py": "python",
                ".js": "javascript",
                ".jsx": "javascript",
                ".mjs": "javascript",
                ".cjs": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".java": "java",
                ".go": "go",
                ".c": "c",
                ".h": "c",
                ".cpp": "c",
                ".cc": "c",
                ".hpp": "c",
            }
            language = ext_map.get(ext, "python")

        try:
            with open(path_obj, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (OSError, IOError) as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return ParsedFile(file_path=str(file_path), language=language)

        source_bytes = content.encode("utf-8")
        line_count = content.count("\n") + 1

        try:
            lang_obj, parser = _load_language(language)
            tree = parser.parse(source_bytes)
            root = tree.root_node
        except (ValueError, ImportError) as e:
            logger.warning(f"Cannot parse {file_path} ({language}): {e}")
            return ParsedFile(
                file_path=str(file_path),
                language=language,
                line_count=line_count,
                raw_content=content,
            )

        # Extract elements
        functions = self._extract_functions(
            root, source_bytes, str(file_path), language, lang_obj
        )
        classes = self._extract_classes(
            root, source_bytes, str(file_path), language, lang_obj, functions
        )
        imports = self._extract_imports(
            root, source_bytes, str(file_path), language, lang_obj
        )
        variables = self._extract_top_level_variables(root, source_bytes, language)

        return ParsedFile(
            file_path=str(file_path),
            language=language,
            functions=functions,
            classes=classes,
            imports=imports,
            variables=variables,
            line_count=line_count,
            raw_content=content,
        )

    def parse_files(
        self, files: List[Tuple[Path, str]]
    ) -> List[ParsedFile]:
        """Parse multiple files.

        Args:
            files: List of (file_path, language) tuples.

        Returns:
            List of ParsedFile results.
        """
        results: List[ParsedFile] = []
        for i, (file_path, lang) in enumerate(files):
            if (i + 1) % 100 == 0:
                logger.info(f"Parsed {i + 1}/{len(files)} files...")
            try:
                result = self.parse_file(file_path, lang)
                results.append(result)
            except Exception as e:
                logger.error(f"Error parsing {file_path}: {e}")
                results.append(
                    ParsedFile(file_path=str(file_path), language=lang)
                )
        logger.info(f"Finished parsing {len(results)} files")
        return results

    def _run_query(self, lang_obj, query_str: str, root) -> List[Dict[str, Any]]:
        """Execute a tree-sitter query and return list of matched capture maps."""
        if not query_str or root is None:
            return []
        try:
            import tree_sitter
            if hasattr(tree_sitter, "Query") and hasattr(tree_sitter, "QueryCursor"):
                q = tree_sitter.Query(lang_obj, query_str)
                qc = tree_sitter.QueryCursor(q)
                matches = qc.matches(root)
                results = []
                for _, cap_map in matches:
                    item = {}
                    for k, node_list in cap_map.items():
                        if node_list:
                            item[k] = node_list[0]
                    if item:
                        results.append(item)
                return results
            elif hasattr(lang_obj, "query"):
                q = lang_obj.query(query_str)
                captures = q.captures(root)
                return list(self._group_captures(captures).values())
        except Exception as e:
            logger.debug(f"Query error: {e}")
        return []

    # ──────────────────────────────────────────
    # Function extraction
    # ──────────────────────────────────────────

    def _extract_functions(
        self,
        root,
        source: bytes,
        file_path: str,
        language: str,
        lang_obj,
    ) -> List[FunctionInfo]:
        """Extract function/method definitions."""
        functions: List[FunctionInfo] = []
        queries = QUERIES.get(language, {})
        func_query_str = queries.get("functions")

        matches = self._run_query(lang_obj, func_query_str, root)

        for cap_dict in matches:
            name_node = cap_dict.get("func.name")
            def_node = cap_dict.get("func.def")
            if not name_node or not def_node:
                continue

            name = self._node_text(name_node, source)
            params_node = cap_dict.get("func.params")
            params = self._extract_params(params_node, source) if params_node else []

            # Check if this is a method (inside a class)
            is_method = self._is_inside_class(def_node, language)
            class_name = self._get_parent_class_name(def_node, source, language)

            # Extract docstring
            docstring = self._extract_docstring(def_node, source, language)

            # Extract decorators
            decorators = self._extract_decorator_list(def_node, source, language)

            # Build qualified name
            qualified_name = f"{file_path}::{class_name}.{name}" if class_name else f"{file_path}::{name}"

            functions.append(
                FunctionInfo(
                    name=name,
                    qualified_name=qualified_name,
                    parameters=params,
                    docstring=docstring,
                    location=CodeLocation(
                        file_path=file_path,
                        start_line=def_node.start_point[0] + 1,
                        end_line=def_node.end_point[0] + 1,
                        language=language,
                    ),
                    is_method=is_method,
                    class_name=class_name,
                    decorators=decorators,
                )
            )

        # Fallback to Python AST if tree-sitter found nothing and language is python
        if not functions and language == "python":
            functions.extend(self._extract_python_functions_ast(source, file_path))

        return functions

    def _extract_python_functions_ast(self, source: bytes, file_path: str) -> List[FunctionInfo]:
        """Extract Python functions using built-in ast module fallback."""
        import ast
        functions = []
        try:
            tree = ast.parse(source.decode("utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    params = [arg.arg for arg in node.args.args]
                    docstring = ast.get_docstring(node)
                    functions.append(
                        FunctionInfo(
                            name=node.name,
                            qualified_name=f"{file_path}::{node.name}",
                            parameters=params,
                            docstring=docstring,
                            location=CodeLocation(
                                file_path=file_path,
                                start_line=node.lineno,
                                end_line=node.end_lineno or node.lineno,
                                language="python",
                            ),
                            is_method=False,
                            class_name=None,
                            decorators=[ast.unparse(d) for d in node.decorator_list] if hasattr(ast, "unparse") else [],
                        )
                    )
        except Exception:
            pass
        return functions

    # ──────────────────────────────────────────
    # Class extraction
    # ──────────────────────────────────────────

    def _extract_classes(
        self,
        root,
        source: bytes,
        file_path: str,
        language: str,
        lang_obj,
        all_functions: List[FunctionInfo],
    ) -> List[ClassInfo]:
        """Extract class definitions."""
        classes: List[ClassInfo] = []
        queries = QUERIES.get(language, {})
        class_query_str = queries.get("classes")

        matches = self._run_query(lang_obj, class_query_str, root)

        for cap_dict in matches:
            name_node = cap_dict.get("class.name")
            def_node = cap_dict.get("class.def")
            if not name_node or not def_node:
                continue

            name = self._node_text(name_node, source)

            # Find methods belonging to this class
            class_start = def_node.start_point[0] + 1
            class_end = def_node.end_point[0] + 1
            methods = [
                f
                for f in all_functions
                if f.is_method
                and f.class_name == name
                and f.location.start_line >= class_start
                and f.location.end_line <= class_end
            ]

            # Extract base classes
            bases = self._extract_bases(def_node, source, language)

            # Extract docstring
            docstring = self._extract_docstring(def_node, source, language)

            qualified_name = f"{file_path}::{name}"

            classes.append(
                ClassInfo(
                    name=name,
                    qualified_name=qualified_name,
                    bases=bases,
                    methods=methods,
                    docstring=docstring,
                    location=CodeLocation(
                        file_path=file_path,
                        start_line=class_start,
                        end_line=class_end,
                        language=language,
                    ),
                )
            )

        if not classes and language == "python":
            classes.extend(self._extract_python_classes_ast(source, file_path))

        return classes

    def _extract_python_classes_ast(self, source: bytes, file_path: str) -> List[ClassInfo]:
        """Extract Python classes using built-in ast module fallback."""
        import ast
        classes = []
        try:
            tree = ast.parse(source.decode("utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else []
                    docstring = ast.get_docstring(node)
                    classes.append(
                        ClassInfo(
                            name=node.name,
                            qualified_name=f"{file_path}::{node.name}",
                            bases=bases,
                            methods=[],
                            docstring=docstring,
                            location=CodeLocation(
                                file_path=file_path,
                                start_line=node.lineno,
                                end_line=node.end_lineno or node.lineno,
                                language="python",
                            ),
                        )
                    )
        except Exception:
            pass
        return classes

    # ──────────────────────────────────────────
    # Import extraction
    # ──────────────────────────────────────────

    def _extract_imports(
        self,
        root,
        source: bytes,
        file_path: str,
        language: str,
        lang_obj,
    ) -> List[ImportInfo]:
        """Extract import statements."""
        imports: List[ImportInfo] = []
        queries = QUERIES.get(language, {})
        import_query_str = queries.get("imports")

        matches = self._run_query(lang_obj, import_query_str, root)

        for cap_dict in matches:
            module_node = cap_dict.get("import.module")
            def_node = cap_dict.get("import.def")
            if not module_node or not def_node:
                continue

            req_id_node = cap_dict.get("req_id")
            if req_id_node:
                req_name = self._node_text(req_id_node, source)
                if req_name != "require":
                    continue

            module = self._node_text(module_node, source).strip("'\"")
            if not module or len(module) < 2:
                continue

            is_from = def_node.type in (
                "import_from_statement",
                "import_statement",
            )

            names: List[str] = []
            if is_from and language == "python":
                for child in def_node.children:
                    if child.type == "import_list" or child.type == "dotted_name":
                        if child != module_node:
                            for name_item in self._node_text(child, source).split(","):
                                cleaned_name = name_item.strip().split(" as ")[0].strip()
                                if cleaned_name:
                                    names.append(cleaned_name)
            elif language in ("javascript", "typescript"):
                # Handle ES6 import statement: import { a, b }, import defaultName
                if def_node.type == "import_statement":
                    for child in def_node.children:
                        if child.type == "import_clause":
                            for sub in child.children:
                                if sub.type == "identifier":
                                    names.append(self._node_text(sub, source))
                                elif sub.type == "named_imports":
                                    for spec in sub.children:
                                        if spec.type == "import_specifier":
                                            name_node = spec.child_by_field_name("name") or spec.children[0]
                                            names.append(self._node_text(name_node, source))
                # Handle CommonJS require: const { a, b } = require('...')
                elif req_id_node:
                    parent = def_node.parent
                    while parent and parent.type not in ("variable_declarator", "lexical_declaration", "variable_declaration"):
                        parent = parent.parent
                    if parent:
                        name_node = parent.child_by_field_name("name")
                        if name_node:
                            if name_node.type == "object_pattern":
                                for prop in name_node.children:
                                    if prop.type in ("shorthand_property_identifier_pattern", "property_identifier", "identifier"):
                                        names.append(self._node_text(prop, source))
                                    elif prop.type == "pair_pattern":
                                        val = prop.child_by_field_name("value") or prop.children[-1]
                                        names.append(self._node_text(val, source))
                            elif name_node.type == "identifier":
                                names.append(self._node_text(name_node, source))

            imports.append(
                ImportInfo(
                    module=module,
                    names=names,
                    is_from_import=is_from,
                    location=CodeLocation(
                        file_path=file_path,
                        start_line=def_node.start_point[0] + 1,
                        end_line=def_node.end_point[0] + 1,
                        language=language,
                    ),
                )
            )

        if not imports and language == "python":
            imports.extend(self._extract_python_imports_ast(source, file_path))

        return imports

    def _extract_python_imports_ast(self, source: bytes, file_path: str) -> List[ImportInfo]:
        """Extract Python imports using built-in ast module fallback."""
        import ast
        imports = []
        try:
            tree = ast.parse(source.decode("utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(
                            ImportInfo(
                                module=alias.name,
                                names=[],
                                is_from_import=False,
                                location=CodeLocation(
                                    file_path=file_path,
                                    start_line=node.lineno,
                                    end_line=node.end_lineno or node.lineno,
                                    language="python",
                                ),
                            )
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        names = [alias.name for alias in node.names]
                        imports.append(
                            ImportInfo(
                                module=node.module,
                                names=names,
                                is_from_import=True,
                                location=CodeLocation(
                                    file_path=file_path,
                                    start_line=node.lineno,
                                    end_line=node.end_lineno or node.lineno,
                                    language="python",
                                ),
                            )
                        )
        except Exception:
            pass
        return imports

    # ──────────────────────────────────────────
    # Function call extraction (for dependency analysis)
    # ──────────────────────────────────────────

    def extract_calls(
        self,
        root,
        source: bytes,
        file_path: str,
        language: str,
        lang_obj,
    ) -> List[Dict[str, Any]]:
        """Extract function calls from the AST."""
        calls: List[Dict[str, Any]] = []
        queries = QUERIES.get(language, {})
        call_query_str = queries.get("calls")

        matches = self._run_query(lang_obj, call_query_str, root)

        for cap_dict in matches:
            call_node = cap_dict.get("call.name")
            if call_node:
                calls.append({
                    "name": self._node_text(call_node, source),
                    "line": call_node.start_point[0] + 1,
                    "file": file_path,
                })

        if not calls and language == "python":
            import ast
            try:
                tree = ast.parse(source.decode("utf-8", errors="ignore"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        name = None
                        if isinstance(node.func, ast.Name):
                            name = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            name = node.func.attr
                        if name:
                            calls.append({
                                "name": name,
                                "line": node.lineno,
                                "file": file_path,
                            })
            except Exception:
                pass

        return calls

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _node_text(node, source: bytes) -> str:
        """Extract text from a tree-sitter node."""
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

    @staticmethod
    def _group_captures(captures) -> Dict:
        """Group tree-sitter query captures by their definition node."""
        groups: Dict = {}

        # Handle both old tuple-style and new dict-style captures
        if isinstance(captures, dict):
            # New API: dict of {capture_name: [nodes]}
            # Reconstruct into (node, name) pairs
            pairs = []
            for name, nodes in captures.items():
                if isinstance(nodes, list):
                    for n in nodes:
                        pairs.append((n, name))
                else:
                    pairs.append((nodes, name))
        else:
            pairs = captures

        for node, name in pairs:
            # Find the outermost definition node (the @*.def capture)
            if name.endswith(".def"):
                if node not in groups:
                    groups[node] = {}
                groups[node]["_def"] = node
            else:
                # Walk up to find the parent def node
                parent = node.parent
                while parent:
                    if parent in groups:
                        groups[parent][name] = node
                        break
                    parent = parent.parent
                else:
                    # If no parent def found, create entry with the node
                    # as its own definition context
                    if node not in groups:
                        groups[node] = {}
                    groups[node][name] = node

        return groups

    @staticmethod
    def _is_inside_class(node, language: str) -> bool:
        """Check if a node is inside a class definition."""
        class_types = {
            "python": "class_definition",
            "javascript": "class_declaration",
            "typescript": "class_declaration",
            "java": "class_declaration",
        }
        class_type = class_types.get(language)
        if not class_type:
            return False

        parent = node.parent
        while parent:
            if parent.type == class_type:
                return True
            parent = parent.parent
        return False

    def _get_parent_class_name(self, node, source: bytes, language: str) -> Optional[str]:
        """Get the name of the enclosing class."""
        class_types = {
            "python": "class_definition",
            "javascript": "class_declaration",
            "typescript": "class_declaration",
            "java": "class_declaration",
        }
        class_type = class_types.get(language)
        if not class_type:
            return None

        parent = node.parent
        while parent:
            if parent.type == class_type:
                name_node = parent.child_by_field_name("name")
                if name_node:
                    return self._node_text(name_node, source)
            parent = parent.parent
        return None

    def _extract_params(self, params_node, source: bytes) -> List[str]:
        """Extract parameter names from a parameters node."""
        params: List[str] = []
        text = self._node_text(params_node, source)
        # Simple param extraction: strip parens and split by comma
        text = text.strip("()")
        for param in text.split(","):
            param = param.strip()
            if param and param != "self" and param != "cls":
                # Remove type annotations and defaults
                param_name = param.split(":")[0].split("=")[0].strip()
                if param_name:
                    params.append(param_name)
        return params

    def _extract_docstring(self, node, source: bytes, language: str) -> Optional[str]:
        """Extract docstring from a function or class definition."""
        if language == "python":
            body = node.child_by_field_name("body")
            if body and body.child_count > 0:
                first_stmt = body.children[0]
                if first_stmt.type == "expression_statement":
                    expr = first_stmt.children[0] if first_stmt.child_count > 0 else None
                    if expr and expr.type == "string":
                        doc = self._node_text(expr, source)
                        return doc.strip("'\"").strip()
        return None

    def _extract_decorator_list(
        self, node, source: bytes, language: str
    ) -> List[str]:
        """Extract decorator names from a function/class node."""
        decorators: List[str] = []
        if language != "python":
            return decorators

        # In Python, decorators are siblings before the definition
        parent = node.parent
        if parent:
            for sibling in parent.children:
                if sibling == node:
                    break
                if sibling.type == "decorator":
                    decorators.append(
                        self._node_text(sibling, source).lstrip("@").strip()
                    )
        return decorators

    def _extract_bases(
        self, node, source: bytes, language: str
    ) -> List[str]:
        """Extract base class names from a class definition."""
        bases: List[str] = []
        if language == "python":
            arg_list = node.child_by_field_name("superclasses")
            if arg_list:
                text = self._node_text(arg_list, source).strip("()")
                bases = [b.strip() for b in text.split(",") if b.strip()]
        elif language in ("javascript", "typescript"):
            # Look for heritage clause
            for child in node.children:
                if child.type == "class_heritage":
                    bases.append(self._node_text(child, source).replace("extends", "").strip())
        elif language == "java":
            for child in node.children:
                if child.type == "superclass":
                    bases.append(self._node_text(child, source).replace("extends", "").strip())
        return bases

    def _extract_top_level_variables(
        self, root, source: bytes, language: str
    ) -> List[str]:
        """Extract top-level variable/constant names."""
        variables: List[str] = []
        for child in root.children:
            if language == "python" and child.type == "expression_statement":
                # Look for assignments
                for sub in child.children:
                    if sub.type == "assignment":
                        left = sub.child_by_field_name("left")
                        if left:
                            variables.append(self._node_text(left, source))
            elif language in ("javascript", "typescript") and child.type in (
                "variable_declaration",
                "lexical_declaration",
            ):
                for decl in child.children:
                    if decl.type == "variable_declarator":
                        name_node = decl.child_by_field_name("name")
                        if name_node:
                            variables.append(self._node_text(name_node, source))
        return variables
