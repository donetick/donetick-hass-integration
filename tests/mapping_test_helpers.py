"""Load the pure mapping resolver without requiring Home Assistant."""
import ast
from pathlib import Path


def load_completion_user():
    root = Path(__file__).resolve().parents[1] / "custom_components/donetick"
    namespace = {"HomeAssistantError": ValueError}
    exec((root / "const.py").read_text(), namespace)
    tree = ast.parse((root / "user_mapping.py").read_text())
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    exec(compile(tree, "user_mapping", "exec"), namespace)
    return namespace["completion_user"]


def load_username_mappings():
    root = Path(__file__).resolve().parents[1] / "custom_components/donetick"
    tree = ast.parse((root / "user_mapping.py").read_text())
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    namespace = {}
    exec(compile(tree, "user_mapping", "exec"), namespace)
    return namespace["username_mappings"]
