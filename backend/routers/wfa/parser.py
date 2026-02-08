import ast
import logging

logger = logging.getLogger(__name__)

def extract_strategy_parameters(file_path):
    """
    Parses the strategy file using AST.
    Supports:
    1. StrategyConfig = namedtuple(...) followed by self.config = StrategyConfig(...) in __init__
    2. StrategyConfig class with default attributes.
    3. Backtrader style 'params = (...)'.
    """
    parameters = {}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
            
        # StrategyConfig Fields (Capture order)
        strategy_config_fields = []
        
        # 1. Scan for namedtuple definition first
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # StrategyConfig = namedtuple('StrategyConfig', ['field1', ...])
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'StrategyConfig':
                        if isinstance(node.value, ast.Call) and getattr(node.value.func, 'id', '') == 'namedtuple':
                            if len(node.value.args) >= 2:
                                fields_node = node.value.args[1]
                                if isinstance(fields_node, ast.List):
                                    strategy_config_fields = [elt.value for elt in fields_node.elts if isinstance(elt, ast.Constant)]

        # 2. Scan for __init__ to find default values
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'StrategyEngine':
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                        for stmt in item.body:
                            # Search for self.config = StrategyConfig(...)
                            if isinstance(stmt, ast.Assign):
                                target = stmt.targets[0]
                                if isinstance(target, ast.Attribute) and target.attr == 'config':
                                    if isinstance(stmt.value, ast.Call) and getattr(stmt.value.func, 'id', '') == 'StrategyConfig':
                                        
                                        # A. Keyword Arguments: StrategyConfig(param=1, ...)
                                        for keyword in stmt.value.keywords:
                                            val = _extract_value(keyword.value)
                                            if val is not None:
                                                parameters[keyword.arg] = val
                                        
                                        # B. Positional Arguments: StrategyConfig(1, 2, ...)
                                        # If we found fields earlier, map them!
                                        if strategy_config_fields and stmt.value.args:
                                            for i, arg_val_node in enumerate(stmt.value.args):
                                                if i < len(strategy_config_fields):
                                                    val = _extract_value(arg_val_node)
                                                    if val is not None:
                                                        parameters[strategy_config_fields[i]] = val
        
        # 3. Fallback: Check for class StrategyConfig definition (Pydantic/Dataclass style)
        if not parameters:
             for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == 'StrategyConfig':
                    for item in node.body:
                        # Case A: Simple assignment (sma_fast = 10)
                        if isinstance(item, ast.Assign):
                             for target in item.targets:
                                if isinstance(target, ast.Name):
                                    val = _extract_value(item.value)
                                    if val is not None:
                                        parameters[target.id] = val
                        # Case B: Annotated assignment for dataclasses (sma_fast: int = 10)
                        elif isinstance(item, ast.AnnAssign):
                            if isinstance(item.target, ast.Name) and item.value is not None:
                                val = _extract_value(item.value)
                                if val is not None:
                                    parameters[item.target.id] = val

    except Exception as e:
        logger.error(f"AST parsing failed: {e}")

    return parameters

def _extract_value(node):
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Num): # Python < 3.8
        return node.n
    elif isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
             val = _extract_value(node.operand)
             # Basic types only
             if isinstance(val, (int, float)):
                 return -val
    return None
