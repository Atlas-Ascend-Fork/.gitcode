import textwrap

def print_table_stdlib():
    # 列定义、固定宽度
    col_names = ["文件名", "行数", "告警编码", "告警详情"]
    widths = [20, 6, 45, 80]

    # 分割线
    sep = "+" + "+".join("-" * w for w in widths) + "+"
    # 表头行
    header_cells = [name.ljust(w) for name, w in zip(col_names, widths)]
    header_row = "|" + "|".join(header_cells) + "|"

    print(sep)
    print(header_row)
    print(sep)



    cells = ['README.md', '1', 'MD041/first-line-heading/first-line-h1 First line in a file should be a top-level heading [Context: "### ops-nn"]', 'msg']

    # 对长文本自动换行
    wrapped_cells = []
    for txt, w in zip(cells, widths):
        wrapped = textwrap.wrap(txt, width=w)
        wrapped_cells.append(wrapped)

    # 获取最大行数，逐行打印
    max_lines = max(len(lines) for lines in wrapped_cells)
    for i in range(max_lines):
        row_parts = []
        for idx, lines in enumerate(wrapped_cells):
            cell_text = lines[i] if i < len(lines) else ""
            row_parts.append(cell_text.ljust(widths[idx]))
        print("|" + "|".join(row_parts) + "|")
    print(sep)

# 测试数据

print_table_stdlib()