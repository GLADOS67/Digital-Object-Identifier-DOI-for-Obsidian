# MarkDown Citation Processor
A Python script for batch processing academic notes in Markdown format. It automatically cleans up redundant links, extracts DOIs, builds a citation relationship graph, and generates citation counts and tags for each document.
## ✨ Features
\- Automatically parses YAML frontmatter to distinguish processed from unprocessed files
\- Cleans redundant links in Markdown (e.g., login pages, article anchors)
\- Fixes malformed image links by converting non-standard formats to plain parentheses
\- Extracts all DOIs from the content and generates standardized display names and safe filenames
\- Generates a reference list for each document (\`reference\` field) in the format: \`\[\[display\_name|DOI\]\]\`
\- Counts global DOI citations and writes them to the \`citation\_count\` field
\- Automatically tags documents as \`positive\` (cited) or \`negative\` (uncited)
\- Supports incremental processing; re-runs only update statistics
## 📦 Requirements
\- Python 3.7+
\- \[PyYAML\](https://pyyaml.org/)
Install dependencies:
\`\`\`bash
pip install pyyaml

## 🚀 Usage

### 1\. Run the Batch File (Windows)

Double-click `MarkDown.bat` to process all `.md` files in the same directory as the batch file.

### 2\. Command Line

bash

python MarkDown.py \--path "/your/markdown/directory"

Arguments:

- `--path` : Required. Specifies the directory containing the Markdown files.

## 📄 Processing Details

### Identifying Unprocessed Files

The script checks for the presence of the `aliases` field in the frontmatter to determine whether a file has already been processed.

### Actions on First Processing

- Removes `author` and `published` fields (optional, currently removed by the script)
- Fixes malformed image links (e.g., `[![[image.png]]](url)` → `![[image.png]](url)`)
- Converts useless links (containing keywords like `login`, `article`, `md5=`) to plain text in parentheses
- Extracts all DOIs and generates a reference list under the `reference` field
- Adds `aliases: []` and a `special_reference_count` field

### Updating Processed Files

- Collects DOI mappings from all files and calculates global citation counts
- Updates `citation_count` and `tags` fields (`positive` / `negative`)
- Removes the legacy `reference_status` field

## 📂 Example Output

After processing, the frontmatter of each Markdown file will look like:

yaml

\---
title: "Sample Paper Title"
doi: "10.1234/example"
aliases: \[\]
reference:
  \- "\[\[Smith2023|10.5678/ref1\]\]"
  \- "\[\[Jones2022|10.9012/ref2\]\]"
citation\_count: 3
tags:
  \- positive
special\_reference\_count: 0
\---

## ⚠️ Important Notes

- The script modifies original `.md` files in place. It is recommended to back up your files or use version control before running.
- DOI-safe filenames replace `/` with `￥` and strip illegal filename characters.
- Citation counts are based on a global DOI map; multiple references to the same DOI are counted only once per file.

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](https://LICENSE) file for details.

---

For questions or suggestions, feel free to open an issue or pull request.


# MarkDown 文献引用处理器
一个用于批量处理 Markdown 学术笔记的 Python 脚本，自动清洗无用链接、提取 DOI 并构建引用关系图，最终为每篇文献生成引用计数与标签。
## ✨ 功能特性
\- 自动解析 YAML frontmatter，识别已处理与未处理文件
\- 清理 Markdown 中的冗余链接（如登录页、文章页锚点等）
\- 修复图片链接格式，将非标准图片链接转换为普通括号形式
\- 提取全文中的 DOI，生成标准化显示名称与安全文件名
\- 为每篇文献生成引用列表（\`reference\` 字段），格式：\`\[\[显示名|DOI\]\]\`
\- 全局统计 DOI 被引用次数，写入 \`citation\_count\` 字段
\- 自动标记文献为 \`positive\`（有引用）或 \`negative\`（无引用）
\- 支持增量处理，重复运行仅更新统计信息
## 📦 依赖环境
\- Python 3.7+
\- \[PyYAML\](https://pyyaml.org/)
安装依赖：
\`\`\`bash
pip install pyyaml

## 🚀 使用方法

### 1\. 直接运行批处理（Windows）

双击 `MarkDown.bat`，脚本将自动处理批处理文件所在目录下的所有 `.md` 文件。

### 2\. 命令行调用

bash

python MarkDown.py \--path "/your/markdown/directory"

参数说明：

- `--path`：必选，指定包含 Markdown 文件的目录路径。

## 📄 处理规则详解

### 未处理文件的判断

脚本通过检测 frontmatter 中是否包含 `aliases` 字段来判断文件是否已处理。

### 首次处理时的操作

- 移除 `author`、`published` 字段（可选，当前代码中已移除）
- 修复错误格式的图片链接（如 `[![[image.png]]](url)` → `![[image.png]](url)`）
- 将无用链接（包含 `login`、`article`、`md5=` 等关键词）转为纯文本括号
- 提取所有 DOI，生成引用列表写入 `reference`
- 添加 `aliases: []` 及 `special_reference_count` 字段

### 已处理文件的更新

- 收集所有文件的 DOI 映射，统计全局引用次数
- 更新 `citation_count` 和 `tags` 字段（`positive` / `negative`）
- 移除旧版 `reference_status` 字段

## 📂 输出示例

处理完成后，每篇 Markdown 文件的 frontmatter 将包含如下内容：

yaml

\---
title: "示例文献标题"
doi: "10.1234/example"
aliases: \[\]
reference:
  \- "\[\[Smith2023|10.5678/ref1\]\]"
  \- "\[\[Jones2022|10.9012/ref2\]\]"
citation\_count: 3
tags:
  \- positive
special\_reference\_count: 0
\---

## ⚠️ 注意事项

- 脚本会直接修改原始 `.md` 文件，建议在处理前进行备份或使用版本控制。
- 文件名中的 DOI 安全处理会将 `/` 替换为 `￥`，并移除非法文件名字符。
- 引用统计基于全局 DOI 映射，多次引用同一 DOI 只计一次。

## 📜 许可证

本项目采用 MIT 许可证，详情见 [LICENSE](https://LICENSE) 文件。
