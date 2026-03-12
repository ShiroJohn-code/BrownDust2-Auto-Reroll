import os
import ast
import json
import fnmatch

def get_file_structure(root_dir):
    structure = []
    for root, dirs, files in os.walk(root_dir):
        if '.git' in dirs:
            dirs.remove('.git')
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
            
        for file in files:
            if file.endswith('.pyc'): continue
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, root_dir)
            structure.append(rel_path)
    return structure

def analyze_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return {"error": str(e), "loc": len(content.splitlines())}

    loc = len(content.splitlines())
    classes = []
    functions = []
    imports = []
    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            classes.append({
                "name": node.name,
                "lineno": node.lineno,
                "methods": methods,
                "docstring": ast.get_docstring(node) is not None
            })
        elif isinstance(node, ast.FunctionDef):
            # Check for complexity/length
            func_len = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
            if func_len > 50:
                issues.append({"type": "complexity", "msg": f"Function '{node.name}' is too long ({func_len} lines)", "lineno": node.lineno})
            
            functions.append({
                "name": node.name,
                "lineno": node.lineno,
                "length": func_len,
                "docstring": ast.get_docstring(node) is not None
            })
        elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.append(n.name)
            else:
                module = node.module if node.module else ''
                for n in node.names:
                    imports.append(f"{module}.{n.name}")
        
        # Basic Linter Checks
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append({"type": "warning", "msg": "Bare 'except:' clause found", "lineno": node.lineno})
            elif isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                issues.append({"type": "info", "msg": "Broad 'except Exception:' found", "lineno": node.lineno})
                
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'print':
             issues.append({"type": "info", "msg": "Found print() statement", "lineno": node.lineno})

    return {
        "loc": loc,
        "classes": classes,
        "functions": functions,
        "imports": imports,
        "issues": issues
    }

def main():
    root_dir = "."
    report = {
        "file_structure": get_file_structure(root_dir),
        "code_analysis": {},
        "linter_reports": {}
    }

    for file_path in report["file_structure"]:
        if file_path.endswith(".py"):
            full_path = os.path.join(root_dir, file_path)
            analysis = analyze_file(full_path)
            report["code_analysis"][file_path] = analysis
            if "issues" in analysis:
                report["linter_reports"][file_path] = analysis.pop("issues")

    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
