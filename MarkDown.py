import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
import yaml

# ---------- Precompiled Regular Expressions ----------
PATTERN_FRONTMATTER = re.compile(r'^---\n(.*?)\n---', re.DOTALL | re.MULTILINE)
PATTERN_DOI = re.compile(r'10\.\d{4,9}/[-A-Za-z0-9._;()/:]+', re.IGNORECASE)
PATTERN_SAFE_DOI = re.compile(r'^10\.\d{4,9}￥[-A-Za-z0-9._;()/:]+', re.IGNORECASE)
PATTERN_LINK = re.compile(r'\s*(?<!!)\[(?!!)([^\]]*)\]\(([^)]+)\)\s*', re.IGNORECASE)
PATTERN_BRACKET_LINKS = re.compile(r'((?<!!)\[(?!!)[^\]]+\]\([^)]+\)|\[\[[^\]]+\]\])')
PATTERN_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]*)\)', re.IGNORECASE)
PATTERN_WRONG_CLICKABLE_IMAGE = re.compile(
    r'\[\s*((?:!\[[^\]]*\]\([^)]+\)|!\([^)]+\))[^\]]*?)\]\s*\(([^)]+)\)',
    re.IGNORECASE
)
CLEAN_LINK_PATTERN = re.compile(
    r'\s*(?<!!)(?<![\\])\[(?!!)(?:[^\]]*?)\]\((?:(?:[^)]*?(?:login|article|md5=|journal|author)[^)]*)|(?:\#.*?))\)\s*',
    re.IGNORECASE | re.DOTALL
)


# ---------- Helper Functions ----------
def process_doi(doi_raw: str) -> Tuple[str, str]:
    """Return display DOI and safe filename"""
    NORMAL_END_CHARS = '.。,， \t\n;：:'
    OPEN_PARENS = '（('
    doi_clean = doi_raw.strip().rstrip(NORMAL_END_CHARS).strip()
    if not any(p in doi_clean for p in OPEN_PARENS):
        doi_clean = re.sub(r'[)）].*', '', doi_clean)
    display_doi = doi_clean
    doi_safe = re.sub(r'[\\/:*?"<>|]', '', display_doi.replace('/', '￥'))
    doi_safe = re.sub(r'[￥_\s]+', '￥', doi_safe).strip('￥-_ ')
    if len(doi_safe) > 200:
        doi_safe = doi_safe[:200]
    safe_filename = doi_safe or f'doi-{str(hash(display_doi))[-8:]}'
    return display_doi, safe_filename


def extract_self_doi(fm: Dict, content: str) -> Optional[str]:
    """Extract first DOI from frontmatter or content, return standardized display DOI"""
    fm_doi = fm.get('doi')
    if fm_doi:
        if isinstance(fm_doi, list):
            fm_doi = fm_doi[0] if fm_doi else None
        if isinstance(fm_doi, str):
            doi_match = PATTERN_DOI.search(fm_doi)
            if doi_match:
                return process_doi(doi_match.group(0))[0]
    doi_match = PATTERN_DOI.search(content)
    return process_doi(doi_match.group(0))[0] if doi_match else None


def _update_doi_map(display_doi: str, safe_name: str, name_part: str,
                    unique_map: Dict[str, Tuple[str, int, Optional[str]]]) -> Tuple[str, bool]:
    """Update global mapping and return used reference name and whether it's a special reference"""
    is_special = not PATTERN_SAFE_DOI.match(name_part)
    if display_doi in unique_map:
        stored_safe, cnt, spec = unique_map[display_doi]
        used_name = spec if spec else safe_name
        unique_map[display_doi] = (stored_safe, cnt + 1, spec or (name_part if is_special else None))
    else:
        used_name = name_part if is_special else safe_name
        unique_map[display_doi] = (safe_name, 1, name_part if is_special else None)
    return used_name, is_special


def _dedup_refs(refs: List[str]) -> List[str]:
    """Case-insensitive deduplication of reference list"""
    final, seen = [], set()
    for r in refs:
        key = r.lower()
        if key not in seen:
            seen.add(key)
            final.append(r)
    return final


def process_references(
        refs: List[Union[str, Tuple[str, str]]],
        unique_map: Dict[str, Tuple[str, int, Optional[str]]],
        is_existing: bool = True
) -> Tuple[List[str], int]:
    """Unified processing of reference list, update unique_map. Return (deduplicated refs, special ref count)"""
    if not refs:
        return [], 0

    special_count = 0
    processed = []
    seen_keys = set()

    if is_existing:
        for item in refs:
            ref = item.strip()
            if not ref:
                continue
            if not (ref.startswith('[[') and ref.endswith(']]') and '|' in ref):
                formatted = ref
            else:
                inner = ref[2:-2]
                name_part, display_doi = map(str.strip, inner.split('|', 1))
                _, safe_name = process_doi(display_doi)
                used_name, is_special = _update_doi_map(display_doi, safe_name, name_part, unique_map)
                formatted = f'[[{used_name}|{display_doi}]]'
                if is_special:
                    special_count += 1
            key = (formatted if '|' not in formatted else formatted.split('|', 1)[1]).lower()
            if key not in seen_keys:
                seen_keys.add(key)
                processed.append(formatted)
    else:
        for display_doi, safe_name in refs:
            used_name, is_special = _update_doi_map(display_doi, safe_name, safe_name, unique_map)
            ref_str = f'[[{used_name}|{display_doi}]]'
            if display_doi.lower() not in seen_keys:
                seen_keys.add(display_doi.lower())
                processed.append(ref_str)
            if is_special:
                special_count += 1

    return _dedup_refs(processed), special_count


def save_file(file: Path, fm: Dict, rest: str) -> bool:
    """Save processed file, return success status"""
    try:
        if not fm:
            content = rest
        else:
            s = yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip('\n')
            content = f'---\n{s}\n---\n{rest}'
        file.write_text(content, encoding='utf-8')
        return True
    except Exception as e:
        print(f"  ❌ Failed to save {file.name} → {str(e)}")
        return False


def _parse_md_file(file: Path) -> Tuple[Dict, str, str]:
    """Read and parse frontmatter and content of MD file, return (fm, rest, content)"""
    content = file.read_text(encoding='utf-8')
    fm_match = PATTERN_FRONTMATTER.search(content)
    if not fm_match:
        return {}, content, content
    try:
        loaded = yaml.safe_load(fm_match.group(1))
        fm = loaded if isinstance(loaded, dict) else {}
    except Exception:
        fm = {}
    rest = content[fm_match.end():].lstrip('\n')
    return fm, rest, content


def process_unhandled_file(
        file: Path, content: str, fm: Dict, rest: str,
        unique_map: Dict[str, Tuple[str, int, Optional[str]]]
) -> Tuple[Dict, str]:
    """Process unmarked files, clean format, extract DOI, generate reference list"""
    if not isinstance(fm, dict):
        print(f"    ⚠️  Frontmatter of {file.name} is not a dictionary, reset to empty dict")
        fm = {}

    # Fix image links
    rest = PATTERN_IMAGE.sub(
        lambda m: m.group(0) if m.group(2).strip().startswith(('images/', 'https://')) else f'!({m.group(2).strip()})',
        rest
    )
    rest = PATTERN_WRONG_CLICKABLE_IMAGE.sub(r'\1(\2)', rest)
    # Clean useless links
    rest = CLEAN_LINK_PATTERN.sub(
        lambda m: m.group(0).replace('[', '(', 1).replace(']', ')', 1),
        rest
    )
    # Remove useless fields
    removed = [k for k in ['author', 'published'] if fm.pop(k, None) is not None]
    if removed:
        print(f"    🗑️  Removed fields from {file.name}: {','.join(removed)}")
    # DOI extraction and link replacement
    rest = PATTERN_LINK.sub(
        lambda m: f' {m.group(1)} ' if (doi := PATTERN_DOI.search(m.group(1))) else
        (f' {doi.group(0)} ' if (doi := PATTERN_DOI.search(m.group(2))) else m.group(0)),
        rest
    )
    # Process bracket links
    rest = PATTERN_BRACKET_LINKS.sub(
        lambda m: m.group(0)[1:-1] if m.group(0).startswith('[[') else m.group(0).replace('[', '(', 1).replace(']', ')',
                                                                                                               1),
        rest
    )
    # Generate reference list
    unique_dois = list({doi.lower(): doi for doi in PATTERN_DOI.findall(content)}.values())
    doi_refs = [process_doi(doi) for doi in unique_dois]
    refs, special_count = process_references(doi_refs, unique_map, is_existing=False)
    if refs:
        fm["reference"] = refs
        print(f"    ✅ Added {len(refs)} DOIs")
    fm["aliases"] = []
    fm["special_reference_count"] = special_count
    return fm, rest


# ---------- Main Program ----------
def main():
    parser = argparse.ArgumentParser(description='Batch process MD files, clean links and build DOI reference graph')
    parser.add_argument('--path', type=str, required=True, help='Directory path of MD files')
    args = parser.parse_args()
    target = Path(args.path)
    if not target.exists():
        print(f"Error: Directory does not exist → {target}")
        return

    md_files = sorted(target.rglob("*.md"), key=lambda x: x.stat().st_mtime)
    print(f"Found {len(md_files)} MD files, starting processing after sorting by modification time...\n")

    unique_map: Dict[str, Tuple[str, int, Optional[str]]] = {}
    file_cache: Dict[Path, Tuple[Dict, str, str]] = {}

    # ---------- Phase 1: Collect DOI mappings and process files ----------
    for file in md_files:
        try:
            fm, rest, content = _parse_md_file(file)
        except Exception as e:
            print(f"  Warning: Failed to read file {file.name}, skipped → {str(e)}")
            continue

        if "aliases" in fm:  # Processed files
            refs = fm.get("reference", [])
            processed_refs, special_count = process_references(refs, unique_map, is_existing=True)
            fm["reference"] = processed_refs
            fm["special_reference_count"] = special_count
            ref_count = sum(1 for r in fm.get('reference', []) if '|' in r)
            save_ok = save_file(file, fm, rest)
            if save_ok:
                print(f"  ✅ {file.name} collected {ref_count} DOI mappings, deduplicated")
                file_cache[file] = (fm, rest, content)
        else:  # Unprocessed files
            print(f"Processing unhandled file: {file.name}")
            fm, rest = process_unhandled_file(file, content, fm, rest, unique_map)
            save_ok = save_file(file, fm, rest)
            if save_ok:
                print(f"  ✅ {file.name} processed successfully")
                file_cache[file] = (fm, rest, content)

    print(f"\nCollected {len(unique_map)} global DOI title mappings")
    print("\nStarting to calculate citation counts and reference status...")

    # ---------- Phase 2: Update citation counts and tags ----------
    for file in md_files:
        if file not in file_cache:
            continue
        fm, rest, content = file_cache[file]
        self_doi = extract_self_doi(fm, content)
        cited_count = unique_map[self_doi][1] if (self_doi and self_doi in unique_map) else 0

        fm["citation_count"] = cited_count
        fm["tags"] = ["positive" if (cited_count - fm.get("special_reference_count", 0)) > 0 else "negative"]
        fm.pop("reference_status", None)

        if save_file(file, fm, rest):
            print(f"  ✅ {file.name} updated successfully: citation_count={cited_count}, tag={fm['tags'][0]}")

    print("\n🎉 All processing completed!")
    # Filter entries where Optional[str] is None, find DOI with maximum count
    max_item = max(((doi, val) for doi, val in unique_map.items() if val[2] is None),
                   key=lambda x: x[1][1], default=None)
    if max_item:
        target_doi, (safe_name, max_count, _) = max_item
        print(f"\n🏆 Most cited non-existent DOI: {target_doi} (cited {max_count} times)")
    else:
        print("\nNo non-existent DOIs matching criteria found")


if __name__ == "__main__":
    main()