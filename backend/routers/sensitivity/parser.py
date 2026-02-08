import ast
import logging

logger = logging.getLogger(__name__)

def extract_strategy_parameters(file_path):
    """
    Parses a python strategy file to extract StrategyConfig parameters and default values.
    Assumes structure:
    1. StrategyConfig = namedtuple('StrategyConfig', ['param1', 'param2', ...])
    2. class StrategyEngine:
           def __init__(self):
               self.config = StrategyConfig(param1=val1, param2=val2, ...)
    """
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())

        param_names = []
        defaults = {}

        # 1. Find StrategyConfig definition
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Check for StrategyConfig = namedtuple(...)
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'StrategyConfig':
                        if isinstance(node.value, ast.Call) and getattr(node.value.func, 'id', '') == 'namedtuple':
                            # Extract list of names
                            if len(node.value.args) >= 2:
                                fields_node = node.value.args[1]
                                if isinstance(fields_node, ast.List):
                                    param_names = [elt.value for elt in fields_node.elts if isinstance(elt, ast.Constant)]
        
        # 2. Find default values in StrategyEngine.__init__
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'StrategyEngine':
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                        for stmt in item.body:
                            if isinstance(stmt, ast.Assign) or isinstance(stmt, ast.AnnAssign):
                                # Check for self.config = ...
                                # Assign can be multiple targets, AnnAssign is single
                                target = stmt.target if isinstance(stmt, ast.AnnAssign) else stmt.targets[0]
                                
                                if isinstance(target, ast.Attribute) and \
                                   isinstance(target.value, ast.Name) and \
                                   target.value.id == 'self' and \
                                   target.attr == 'config':
                                    
                                    if isinstance(stmt.value, ast.Call) and getattr(stmt.value.func, 'id', '') == 'StrategyConfig':
                                        # Extract keywords
                                        for keyword in stmt.value.keywords:
                                            if isinstance(keyword.value, ast.Constant):
                                                defaults[keyword.arg] = keyword.value.value
                                            elif isinstance(keyword.value, ast.UnaryOp) and \
                                                 isinstance(keyword.value.op, ast.USub) and \
                                                 isinstance(keyword.value.operand, ast.Constant):
                                                 # Handle negative numbers
                                                 defaults[keyword.arg] = -keyword.value.operand.value

        # Combine results
        extracted = {}
        for name in param_names:
            extracted[name] = defaults.get(name, 0.0) # Default to 0.0 if not found

        return extracted

    except Exception as e:
        logger.error(f"Failed to parse strategy file: {e}")
        return {}
