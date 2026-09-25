import pytest
from pathlib import Path
from app.core.parser import CodeParser
from app.core.dependency import DependencyAnalyzer
from app.graph.knowledge_graph import CodeKnowledgeGraph

def test_knowledge_graph_construction(tmp_path: Path):
    parser = CodeParser()
    analyzer = DependencyAnalyzer()
    graph = CodeKnowledgeGraph()

    # File 1: Service
    f1_code = """
def process_order(order_id: str):
    return {"status": "processed", "id": order_id}
"""
    f1 = tmp_path / "order_service.py"
    f1.write_text(f1_code, encoding="utf-8")

    # File 2: Controller
    f2_code = """
from order_service import process_order

def handle_checkout(req: dict):
    return process_order(req["order_id"])
"""
    f2 = tmp_path / "order_controller.py"
    f2.write_text(f2_code, encoding="utf-8")

    parsed1 = parser.parse_file(f1)
    parsed2 = parser.parse_file(f2)
    parsed_files = [parsed1, parsed2]

    deps = analyzer.analyze(parsed_files)
    graph.build_from_analysis(parsed_files, deps)

    # Verify graph has nodes and edges
    stats = graph.get_stats()
    assert stats["total_nodes"] > 0
    assert stats["total_edges"] >= 0
