import pytest
from pathlib import Path
from app.core.parser import CodeParser, ParsedFile

def test_python_code_parsing(tmp_path: Path):
    parser = CodeParser()
    code = """
import os
from typing import List

class AuthService:
    def __init__(self, secret: str):
        self.secret = secret

    def authenticate(self, token: str) -> bool:
        return token == self.secret

def verify_token(token: str) -> bool:
    auth = AuthService("secret123")
    return auth.authenticate(token)
"""
    test_file = tmp_path / "auth.py"
    test_file.write_text(code, encoding="utf-8")

    parsed = parser.parse_file(test_file)
    assert parsed is not None
    assert parsed.language == "python"
    
    # Check classes
    class_names = [c.name for c in parsed.classes]
    assert "AuthService" in class_names

    # Check functions
    func_names = [f.name for f in parsed.functions]
    assert "authenticate" in func_names or "verify_token" in func_names

    # Check imports
    import_names = [imp.module for imp in parsed.imports]
    assert any("os" in imp or "typing" in imp for imp in import_names)
