import pytest
from pathlib import Path
from app.core.parser import CodeParser
from app.core.chunker import CodeChunker

def test_chunker(tmp_path: Path):
    parser = CodeParser()
    chunker = CodeChunker()

    code = """
def calculate_tax(income: float) -> float:
    \"\"\"Calculate tax based on income brackets.\"\"\"
    if income < 10000:
        return 0.0
    return income * 0.2

def calculate_net(income: float) -> float:
    tax = calculate_tax(income)
    return income - tax
"""
    test_file = tmp_path / "tax.py"
    test_file.write_text(code, encoding="utf-8")

    parsed = parser.parse_file(test_file)
    chunks = chunker.chunk_file(parsed)

    assert len(chunks) >= 2
    assert any(c.name == "calculate_tax" for c in chunks)
    assert any(c.name == "calculate_net" for c in chunks)
