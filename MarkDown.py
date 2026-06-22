import re
import argparse
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import yaml
try:
    from yaml import CSafeLoader as _YamlLoader, CSafeDumper as _YamlDumper
except ImportError:
    from yaml import SafeLoader as _YamlLoader, SafeDumper as _YamlDumper

# ---------- 预编译正则 ----------
PATTERN_FRONTMATTER = re.compile(r'^---\n(.*?)\n---', re.DOTALL | re.MULTILINE)
PATTERN_DOI = re.compile(r'10\.\d{4,9}/[-A-Za-z0-9._;()/:]+', re.IGNORECASE)
PATTERN_SAFE_DOI = re.compile(r'^10\.\d{4,9}￥[-A-Za-z0-9._;()/:]+', re.IGNORECASE)
PATTERN_DOI_REPAIR = re.compile(
    r'(10\.\d{4,9}/[-A-Za-z0-9._;()/:]*?)[ \t]+(?=[-A-Za-z0-9._;()/:]*\d)([-A-Za-z0-9._;()/:]+)',
    re.IGNORECASE
)
PATTERN_BRACKET_LINKS = re.compile(r'((?<!!)\[(?!!)[^\]]+\]\([^)]+\)|\[\[[^\]]+\]\])')
PATTERN_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]*)\)', re.IGNORECASE)
PATTERN_WRONG_CLICKABLE_IMAGE = re.compile(
    r'\[\s*((?:!\[[^\]]*\]\([^)]+\)|!\([^)]+\))[^\]]*?)\]\s*\(([^)]+)\)',
    re.IGNORECASE
)
COMBINED_LINK_PATTERN = re.compile(
    r'(?P<clean>\s*(?<!!)(?<![\\])\[(?!!)(?:[^\]]*?)\]\((?:(?:[^)]*?(?:login|article|md5=|journal|author)[^)]*)|(?:\#.*?))\)\s*)'
    r'|(?P<link>\s*(?<!!)\[(?!!)(?P<text>[^\]]*)\]\((?P<url>[^)]+)\)\s*)',
    re.IGNORECASE | re.DOTALL
)
PATTERN_TAIL_PARENS = re.compile(r'[)）].*')
PATTERN_FS_INVALID = re.compile(r'[\\:*?"<>|]')
PATTERN_COLLAPSE = re.compile(r'[￥_\s]+')
UNICODE_DASH_TABLE = str.maketrans('\u2010\u2011\u2013\u2014', '----')
ARTIFACT_TAGS = re.compile(r'</?(?:lcel|nl)>', re.IGNORECASE)
NORMAL_END_CHARS = '。,， \t\n;：:'
OPEN_PARENS = '（('


def _repair_doi_text(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = PATTERN_DOI_REPAIR.sub(r'\1\2', text)
    return text


def _fix_img(m: re.Match) -> str:
    alt, link = m.group(1), m.group(2).strip()
    link = f'https://{link[2:]}' if link.startswith('//') else link
    return f'![{alt}]({link})' if link.startswith(('images/', 'https://', 'C:/')) else f'!({link})'


def _handle_combined_link(m: re.Match) -> str:
    if m.lastgroup == 'clean':
        return m.group(0).replace('[', '(', 1).replace(']', ')', 1)
    doi_in_text = PATTERN_DOI.search(m.group('text'))
    if doi_in_text:
        return f' {m.group("text")} '
    doi_in_url = PATTERN_DOI.search(m.group('url'))
    return f' {doi_in_url.group(0)} ' if doi_in_url else m.group(0)


# ---------- 核心函数 ----------
@lru_cache(maxsize=4096)
def process_doi(doi_raw: str) -> Tuple[str, str]:
    doi_clean = doi_raw.strip().rstrip(NORMAL_END_CHARS)
    doi_clean = re.sub(r'\.+$', '', doi_clean)
    doi_clean = re.sub(r'PMID:?\s*\d+$', '', doi_clean, flags=re.IGNORECASE)
    if not any(p in doi_clean for p in OPEN_PARENS):
        doi_clean = PATTERN_TAIL_PARENS.sub('', doi_clean)
    doi_safe = PATTERN_FS_INVALID.sub('', doi_clean.replace('/', '￥'))
    doi_safe = PATTERN_COLLAPSE.sub('￥', doi_safe).strip('￥-_ ')
    safe_filename = doi_safe[:200] if len(doi_safe) > 200 else doi_safe
    safe_filename = safe_filename or f'doi-{str(hash(doi_clean))[-8:]}'
    return doi_clean, safe_filename


def _update_doi_map(display_doi: str, safe_name: str, name_part: str,
                    unique_map: Dict[str, Tuple[str, int, Optional[str]]]) -> Tuple[str, bool]:
    is_special = not PATTERN_SAFE_DOI.match(name_part)
    if display_doi in unique_map:
        stored_safe, cnt, spec = unique_map[display_doi]
        used_name = spec if spec else safe_name
        unique_map[display_doi] = (stored_safe, cnt + 1, spec or (name_part if is_special else None))
    else:
        used_name = name_part if is_special else safe_name
        unique_map[display_doi] = (safe_name, 1, name_part if is_special else None)
    return used_name, is_special


def process_references(
        refs: List, unique_map: Dict[str, Tuple[str, int, Optional[str]]],
        is_existing: bool = True
) -> Tuple[List[str], int]:
    if not refs:
        return [], 0

    special_count = 0
    seen = set()
    result = []

    for item in refs:
        if is_existing:
            ref = item.strip()
            if not ref:
                continue
            is_piped_wiki = ref.startswith('[[') and ref.endswith(']]') and '|' in ref
            if not is_piped_wiki:
                key = ref.lower()
                if key not in seen:
                    seen.add(key)
                    result.append(ref)
                continue
            inner = ref[2:-2]
            name_part, display_doi = map(str.strip, inner.split('|', 1))
            display_doi, safe_name = process_doi(display_doi)
        else:
            display_doi, safe_name = item
            name_part = safe_name

        used_name, is_special = _update_doi_map(display_doi, safe_name, name_part, unique_map)
        if is_special:
            special_count += 1
        dedup_key = display_doi.lower()
        if dedup_key not in seen:
            seen.add(dedup_key)
            result.append(f'[[{used_name}|{display_doi}]]')

    return result, special_count


def process_unhandled_file(
        file: Path, content: str, fm: Dict, rest: str,
        unique_map: Dict[str, Tuple[str, int, Optional[str]]]
) -> Tuple[Dict, str]:
    if not isinstance(fm, dict):
        print(f"    ⚠️  {file.name} 的 frontmatter 非字典类型，已重置为空字典")
        fm = {}

    rest = ARTIFACT_TAGS.sub('', rest)
    rest = PATTERN_IMAGE.sub(_fix_img, rest)
    rest = PATTERN_WRONG_CLICKABLE_IMAGE.sub(r'\1(\2)', rest)
    rest = COMBINED_LINK_PATTERN.sub(_handle_combined_link, rest)
    removed = [k for k in ['author', 'published'] if fm.pop(k, None) is not None]
    if removed:
        print(f"    🗑️  删除 {file.name} 字段：{','.join(removed)}")
    rest = PATTERN_BRACKET_LINKS.sub(
        lambda m: m.group(0)[1:-1] if m.group(0).startswith('[[') else m.group(0).replace('[', '(', 1).replace(']', ')', 1),
        rest
    )
    unique_dois = list({doi.lower(): doi for doi in PATTERN_DOI.findall(_repair_doi_text(content))}.values())
    doi_refs = [process_doi(doi) for doi in unique_dois]
    refs, special_count = process_references(doi_refs, unique_map, is_existing=False)
    if refs:
        fm["reference"] = refs
        print(f"    ✅ 添加 {len(refs)} 个DOI")
    fm["aliases"] = []
    fm["特殊引用数"] = special_count
    return fm, rest


def _extract_self_doi(file_stem: str, refs: List[str]) -> Optional[str]:
    for ref in refs:
        if ref.startswith('[[') and ref.endswith(']]') and '|' in (ref[2:-2]):
            name_part, doi_part = ref[2:-2].split('|', 1)
            if name_part.strip() == file_stem:
                m = PATTERN_DOI.search(doi_part)
                if m:
                    return process_doi(m.group(0))[0]
    return None


def _find_first_doi(refs: List[str]) -> Optional[str]:
    if not refs:
        return None
    first = refs[0]
    inner = first[2:-2] if (first.startswith('[[') and first.endswith(']]')) else first
    doi_part = inner.split('|', 1)[-1] if '|' in inner else inner
    m = PATTERN_DOI.search(doi_part)
    return process_doi(m.group(0))[0] if m else None


# ---------- 主程序 ----------
def main():
    parser = argparse.ArgumentParser(description='批量处理MD文件，清理链接并建立DOI引用图谱')
    parser.add_argument('--path', type=str, required=True, help='MD文件目录路径')
    args = parser.parse_args()
    target = Path(args.path)
    if not target.exists():
        print(f"错误：目录不存在 → {target}")
        return

    md_files = sorted(target.rglob("*.md"))
    print(f"找到 {len(md_files)} 个MD文件，开始处理...\n")

    unique_map: Dict[str, Tuple[str, int, Optional[str]]] = {}
    files_data: List[Tuple[Path, Dict, str]] = []

    for file in md_files:
        try:
            content = file.read_text(encoding='utf-8').translate(UNICODE_DASH_TABLE)
        except Exception as e:
            print(f"  警告：读取文件 {file.name} 失败，跳过 → {str(e)}")
            continue
        fm_match = PATTERN_FRONTMATTER.search(content)
        if fm_match:
            try:
                loaded = yaml.load(fm_match.group(1), Loader=_YamlLoader)
                fm = loaded if isinstance(loaded, dict) else {}
            except Exception:
                fm = {}
            rest = content[fm_match.end():].lstrip('\n')
        else:
            fm, rest = {}, content

        # "aliases" in fm → 已被本脚本处理过，reference 列表格式正确，直接去重即可
        # "reference" in fm → CROSSREF 产物（仅有 reference 无 aliases），走同一路径以保留 [[stem|DOI]] 自引用硬链接
        if "aliases" in fm or "reference" in fm:
            refs_in = fm.get("reference", [])
            processed_refs, special_count = process_references(refs_in, unique_map, is_existing=True)
            fm["reference"] = processed_refs
            fm["特殊引用数"] = special_count
            ref_count = sum(1 for r in fm.get('reference', []) if '|' in r)
            print(f"  ✅ {file.name} 收集到 {ref_count} 个DOI映射，已去重")
        else:
            # 无 aliases 且无 reference → 真正的新文件，全量清理并重建引用
            print(f"处理未处理文件：{file.name}")
            fm, rest = process_unhandled_file(file, content, fm, rest, unique_map)
            print(f"  ✅ {file.name} 处理完成")
        files_data.append((file, fm, rest))

    print(f"\n已收集到 {len(unique_map)} 个全局DOI标题映射")
    print("\n开始计算被引数和引用情况并保存文件...")

    for file, fm, rest in files_data:
        refs = fm.get("reference", [])
        self_doi = _extract_self_doi(file.stem, refs) or _find_first_doi(refs)

        cited_count = unique_map[self_doi][1] if (self_doi and self_doi in unique_map) else 0
        fm["被引数"] = cited_count
        fm["tags"] = ["正向" if (cited_count - fm.get("特殊引用数", 0)) > 0 else "负向"]
        fm.pop("引用情况", None)

        try:
            out = f'---\n{yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False, Dumper=_YamlDumper).rstrip("\n")}\n---\n{rest}' if fm else rest
            file.write_text(out, encoding='utf-8')
            print(f"  ✅ {file.name} 更新完成：被引数={cited_count}, 标签={fm['tags'][0]}")
        except Exception as e:
            print(f"  ❌ {file.name} 保存失败 → {str(e)}")

    print("\n🎉 全部处理完成！")
    missing = [(doi, cnt) for doi, (_, cnt, spec) in unique_map.items() if spec is None]
    if missing:
        doi, cnt = max(missing, key=lambda x: x[1])
        print(f"\n🏆 引用最多的目前不存在的DOI：{doi} （被引 {cnt} 次）")
    else:
        print("\n未找到符合条件的目前不存在的DOI")


if __name__ == "__main__":
    main()
