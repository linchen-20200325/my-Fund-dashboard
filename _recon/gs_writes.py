"""AST 掃：哪些函式裡有 gspread 寫入形態的呼叫。

判定方式刻意「寧可多抓」：任何 `X.<write_method>(...)` 的呼叫都先收進候選，
再由人工逐一判讀（因為 dict.update / DataFrame.update / list.append 同名）。
"""
import ast, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WRITE_ATTRS = {
    # gspread Worksheet / Spreadsheet 寫入面
    "update", "update_cell", "update_cells", "update_acell", "update_title",
    "append_row", "append_rows", "insert_row", "insert_rows", "insert_note",
    "batch_update", "batch_clear", "clear", "delete_rows", "delete_columns",
    "delete_row", "add_worksheet", "del_worksheet", "duplicate_sheet",
    "resize", "add_rows", "add_cols", "format", "set_basic_filter",
    "sort", "freeze", "hide", "copy", "share", "create",
}


def scan(path: str):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    except SyntaxError:
        return
    # 建 node -> 所屬函式 的對照
    stack = []

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, n):
            stack.append(n.name); self.generic_visit(n); stack.pop()
        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, n):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in WRITE_ATTRS:
                recv = ast.unparse(f.value)
                print(f"{os.path.relpath(path, ROOT)}\t{n.lineno}\t"
                      f"{'::'.join(stack) or '<module>'}\t{recv}.{f.attr}")
            self.generic_visit(n)

    V().visit(tree)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        scan(os.path.join(ROOT, p))
