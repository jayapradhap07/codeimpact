"""Repository ingestion pipeline.

Handles cloning repositories, detecting languages, identifying source files,
and filtering out noise (node_modules, build artifacts, vendor dirs).
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from app.config import settings

# ──────────────────────────────────────────────
# File extension → language mapping
# ──────────────────────────────────────────────

LANGUAGE_EXTENSIONS: Dict[str, List[str]] = {
    "python": [".py", ".pyw"],
    "javascript": [".js", ".jsx", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"],
    "java": [".java"],
    "go": [".go"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".hpp", ".cc", ".cxx", ".hxx", ".hh"],
    "rust": [".rs"],
    "ruby": [".rb"],
    "php": [".php"],
    "csharp": [".cs"],
    "swift": [".swift"],
    "kotlin": [".kt", ".kts"],
    "scala": [".scala"],
    "html": [".html", ".htm"],
    "css": [".css", ".scss", ".sass", ".less"],
    "json": [".json"],
    "yaml": [".yml", ".yaml"],
    "markdown": [".md", ".mdx"],
    "shell": [".sh", ".bash", ".zsh"],
}

# Reverse mapping: extension → language
EXT_TO_LANGUAGE: Dict[str, str] = {}
for lang, exts in LANGUAGE_EXTENSIONS.items():
    for ext in exts:
        EXT_TO_LANGUAGE[ext] = lang

# Supported tree-sitter languages for deep parsing
SUPPORTED_PARSE_LANGUAGES = {"python", "javascript", "typescript", "java", "go", "c"}

# ──────────────────────────────────────────────
# Ignore patterns
# ──────────────────────────────────────────────

DEFAULT_IGNORE_PATTERNS = [
    # Package managers
    "node_modules/",
    "vendor/",
    "bower_components/",
    ".yarn/",
    ".pnp.*",
    "packages/*/node_modules/",

    # Build output
    "build/",
    "dist/",
    "out/",
    "target/",
    "bin/",
    "obj/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.class",
    "*.o",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",

    # IDE / Editor
    ".idea/",
    ".vscode/",
    ".vs/",
    "*.swp",
    "*.swo",

    # Version control
    ".git/",
    ".svn/",
    ".hg/",

    # Environment
    ".env",
    ".env.*",
    "venv/",
    ".venv/",
    "env/",
    ".conda/",

    # OS files
    ".DS_Store",
    "Thumbs.db",

    # Minified / bundled
    "*.min.js",
    "*.min.css",
    "*.bundle.js",
    "*.chunk.js",
    "*.map",

    # Test fixtures / snapshots (keep test files, ignore fixtures)
    "__snapshots__/",

    # Docs / generated
    "docs/_build/",
    "site/",

    # Lock files
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
    "Cargo.lock",
    "go.sum",

    # Data / media
    "*.sqlite",
    "*.db",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.svg",
    "*.ico",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.mp3",
    "*.mp4",
    "*.webm",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
]


class RepositoryIngester:
    """Handles repository cloning, language detection, and source file identification."""

    def __init__(self) -> None:
        self.repo_storage = Path(settings.repo_storage_path)
        self.repo_storage.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────
    # Clone
    # ──────────────────────────────────────────

    def clone_repository(self, url: str, name: Optional[str] = None) -> Path:
        """Clone a git repository to local storage.

        Args:
            url: Git clone URL.
            name: Optional directory name (auto-detected from URL if omitted).

        Returns:
            Path to the cloned repository.
        """
        if name is None:
            name = self._extract_repo_name(url)

        dest = self.repo_storage / name

        if dest.exists():
            logger.info(f"Repository already cloned at {dest}, pulling latest...")
            try:
                subprocess.run(
                    ["git", "pull"],
                    cwd=str(dest),
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120,
                )
            except subprocess.CalledProcessError as e:
                logger.warning(f"Git pull failed: {e.stderr}")
            return dest

        logger.info(f"Cloning {url} to {dest}...")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", url, str(dest)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to clone repository: {e.stderr}") from e

        return dest

    def use_local_path(self, path: str) -> Path:
        """Use an existing local directory as a repository.

        Args:
            path: Absolute path to the local repository.

        Returns:
            Path to the repository.

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        repo_path = Path(path)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {path}")
        if not repo_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")
        return repo_path

    # ──────────────────────────────────────────
    # Language detection
    # ──────────────────────────────────────────

    def detect_languages(self, repo_path: Path) -> Dict[str, int]:
        """Detect programming languages and formats in the repository.

        Returns:
            Dictionary mapping language/format name to file count.
        """
        language_counts: Dict[str, int] = {}
        source_files = self.identify_source_files(repo_path)

        for file_path in source_files:
            fname = file_path.name.lower()
            ext = file_path.suffix.lower()

            if fname in ("package.json", "package-lock.json", "composer.json", "tsconfig.json"):
                lang = "JSON (Package)"
            elif ext == ".jsx":
                lang = "JavaScript (React)"
            elif ext == ".tsx":
                lang = "TypeScript (React)"
            elif ext in (".js", ".mjs", ".cjs"):
                lang = "JavaScript"
            elif ext == ".ts":
                lang = "TypeScript"
            elif ext in (".html", ".htm"):
                lang = "HTML"
            elif ext in (".css", ".scss", ".sass", ".less"):
                lang = "CSS"
            elif ext in (".py", ".pyw"):
                lang = "Python"
            elif ext in (".json",):
                lang = "JSON"
            elif ext in (".txt", ".log") or fname in ("readme", "license", ".env.example"):
                lang = "Text"
            elif ext in (".md", ".mdx"):
                lang = "Markdown"
            elif ext in (".yml", ".yaml"):
                lang = "YAML"
            else:
                raw_lang = EXT_TO_LANGUAGE.get(ext)
                lang = raw_lang.capitalize() if raw_lang else "Other"

            language_counts[lang] = language_counts.get(lang, 0) + 1

        # Sort by count descending
        return dict(sorted(language_counts.items(), key=lambda x: x[1], reverse=True))

    # ──────────────────────────────────────────
    # Source file identification
    # ──────────────────────────────────────────

    def identify_source_files(self, repo_path: Path) -> List[Path]:
        """Identify all source files in the repository, filtering out noise.

        Args:
            repo_path: Path to the repository root.

        Returns:
            List of source file paths.
        """
        ignore_spec = self._build_ignore_spec(repo_path)
        source_files: List[Path] = []

        for root, dirs, files in os.walk(repo_path):
            root_path = Path(root)

            # Filter directories in-place to avoid descending into ignored dirs
            dirs[:] = [
                d
                for d in dirs
                if not ignore_spec.match_file(
                    str((root_path / d).relative_to(repo_path)) + "/"
                )
            ]

            for filename in files:
                file_path = root_path / filename
                rel_path = str(file_path.relative_to(repo_path))

                # Skip ignored files
                if ignore_spec.match_file(rel_path):
                    continue

                # Only include files with known extensions
                ext = file_path.suffix.lower()
                if ext in EXT_TO_LANGUAGE:
                    source_files.append(file_path)

        logger.info(f"Found {len(source_files)} source files in {repo_path}")
        return source_files

    def identify_parseable_files(self, repo_path: Path) -> List[Tuple[Path, str]]:
        """Identify files that can be parsed by tree-sitter.

        Returns:
            List of (file_path, language) tuples.
        """
        source_files = self.identify_source_files(repo_path)
        parseable: List[Tuple[Path, str]] = []

        for file_path in source_files:
            ext = file_path.suffix.lower()
            lang = EXT_TO_LANGUAGE.get(ext)
            if lang and lang in SUPPORTED_PARSE_LANGUAGES:
                parseable.append((file_path, lang))

        logger.info(
            f"Found {len(parseable)} parseable files out of {len(source_files)} source files"
        )
        return parseable

    def count_total_lines(self, files: List[Path]) -> int:
        """Count total lines across all files."""
        total = 0
        for f in files:
            try:
                total += sum(1 for _ in open(f, "r", encoding="utf-8", errors="ignore"))
            except (OSError, IOError):
                continue
        return total

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _build_ignore_spec(self, repo_path: Path) -> PathSpec:
        """Build a PathSpec combining default patterns and .gitignore."""
        patterns = list(DEFAULT_IGNORE_PATTERNS)

        # Read .gitignore if it exists
        gitignore_path = repo_path / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except (OSError, IOError):
                pass

        return PathSpec.from_lines(GitWildMatchPattern, patterns)

    @staticmethod
    def _extract_repo_name(url: str) -> str:
        """Extract repository name from a git URL."""
        # Handle various URL formats
        name = url.rstrip("/").split("/")[-1]
        name = re.sub(r"\.git$", "", name)
        return name or "repository"
