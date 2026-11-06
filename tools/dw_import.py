#!/usr/bin/env python3
"""DokuWiki 数据目录 → Markdown 博客导入器

位置: tools/dw_import.py（属于 wiki-on-github 项目的一部分）

用法:
    python3 tools/dw_import.py <dokuwiki_data_dir> <blog_dir> [--dry-run] [--force] [--include-defaults]

它不依赖运行中的 DokuWiki，直接解析 data/pages/*.txt 与 data/meta/*.changes。
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# 复用项目根目录的 blog_manager（.blog.yaml 解析）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blog_manager import Blog  # noqa: E402

# DokuWiki 命名空间：默认跳过官方文档与示例页
DEFAULT_SKIP_NAMESPACES = {'wiki', 'playground'}

# DokuWiki 代码块语言 → Markdown 语言
LANG_MAP = {
    'text': 'text', 'c': 'c', 'cpp': 'cpp', 'css': 'css', 'd': 'd',
    'diff': 'diff', 'dokuwiki': 'text', 'html': 'html', 'java': 'java',
    'javascript': 'javascript', 'js': 'javascript', 'json': 'json',
    'lua': 'lua', 'makefile': 'makefile', 'perl': 'perl', 'php': 'php',
    'powershell': 'powershell', 'ps1': 'powershell', 'python': 'python',
    'py': 'python', 'ruby': 'ruby', 'sql': 'sql', 'ts': 'typescript',
    'xml': 'xml', 'bash': 'bash', 'shell': 'bash', 'sh': 'bash',
    'yaml': 'yaml', 'yml': 'yaml', 'toml': 'toml', 'ini': 'ini',
    'conf': 'ini', 'powershell': 'powershell',
}

BLOCK_RE = re.compile(
    r'<(code|html|php|nowiki)(?:[ \t]+([^>]*))?\s*>(.*?)</\1\s*>',
    re.S | re.I,
)
HEADING_RE = re.compile(r'^(={2,6})\s*(.+?)\s*(=+)\s*$')
LIST_RE = re.compile(r'^(\s*)([*\-])(\s+)(.+)$')
TOKEN_RE = re.compile(r'\x00(\d+)\x00')


class TokenStore:
    """把已转换片段暂存为占位符，避免后续正则误伤"""

    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, text: str) -> str:
        self.items.append(text)
        return f'\x00{len(self.items) - 1}\x00'

    def restore(self, text: str) -> str:
        def _sub(m: re.Match) -> str:
            idx = int(m.group(1))
            return self.items[idx] if idx < len(self.items) else m.group(0)

        # 占位符可能被换行拆开，反复替换直到稳定
        for _ in range(3):
            new = TOKEN_RE.sub(_sub, text)
            if new == text:
                break
            text = new
        return text


def clean_id(raw: str) -> str:
    """近似 DokuWiki cleanID：小写、特殊符号折叠为下划线"""
    text = raw.strip().lower()
    text = re.sub(r'[^\w\u4e00-\u9fff]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_')
    return text


def loose_key(raw: str) -> str:
    """更宽松的键：只保留字母数字与汉字，用于兜底匹配"""
    return re.sub(r'[^\w\u4e00-\u9fff]+', '', raw.lower())


def page_title(raw: str, fallback: str) -> str:
    """标题：优先一级标题（====== X ======）；否则首行非空若是整行加粗则用它；否则用文件名"""
    for line in raw.splitlines():
        m = HEADING_RE.match(line.strip())
        if m and len(m.group(1)) >= 6:
            return m.group(2).strip()
    for line in raw.splitlines():
        if not line.strip():
            continue
        # 只看第一行非空内容：整行加粗才视为标题（避免把正文中间的粗体当成标题）
        m = re.match(r'^\*\*(.+?)\*\*$', line.strip())
        if m:
            return m.group(1).strip()
        break
    return fallback


# DokuWiki start.txt 里常见的索引类区块标题，这些由 site_builder 接管，导入时删掉
_INDEX_HEADING_RE = re.compile(
    r'\n##\s+(?:最近文章|索引|目录|内容|导航|站点地图|sitemap)\s*\n?(.*?)(?=\n#{1,6}\s|\Z)',
    re.DOTALL,
)


def _cleanup_dokuwiki_index(body: str) -> str:
    """删掉 DokuWiki start.txt 转 Markdown 后残留的原生索引区块

    这些区块的职责已由 site_builder 的动态区块接管，
    留着会导致最终渲染出现双份文章列表。
    """
    return _INDEX_HEADING_RE.sub('\n', body)


@dataclass
class ImportReport:
    imported: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    unresolved_links: list[str] = field(default_factory=list)
    media_copied: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DokuWikiConverter:
    def __init__(self, page_index: dict[str, str], media_index: dict[str, str],
                 image_prefix: str = 'images'):
        self.page_index = page_index        # clean_id / loose_key → md 文件名
        self.media_index = media_index      # clean_id → images/ 下相对路径
        self.image_prefix = image_prefix

    # ---------- 内部工具 ----------
    def _resolve_page(self, target: str) -> Optional[str]:
        key = clean_id(target)
        if key in self.page_index:
            return self.page_index[key]
        loose = loose_key(target)
        for k, v in self.page_index.items():
            if loose_key(k) == loose or loose_key(v) == loose:
                return v
        return None

    def _resolve_media(self, target: str) -> Optional[str]:
        key = clean_id(target)
        if key in self.media_index:
            return self.media_index[key]
        for k, v in self.media_index.items():
            if loose_key(k) == loose_key(target):
                return v
        base = Path(target.replace(':', '/')).name
        for k, v in self.media_index.items():
            if Path(k.replace(':', '/')).name.lower() == base.lower():
                return v
        return None

    # ---------- 主流程 ----------
    def convert(self, raw: str, unresolved: list[str]) -> str:
        tokens = TokenStore()
        self.unresolved = unresolved

        text = BLOCK_RE.sub(lambda m: tokens.add(self._code_block(m)), raw)
        text = '\n'.join(self._line(line, tokens) for line in text.splitlines())
        text = self._inline(text, tokens)
        text = tokens.restore(text)
        text = re.sub(r'\n{3,}', '\n\n', text).strip() + '\n'
        return text

    def _code_block(self, m: re.Match) -> str:
        kind = m.group(1).lower()
        # 参数可能是 "python"、"python | file.py" 或 "| download"
        lang = (m.group(2) or '').split('|')[0].strip().lower()
        body = m.group(3)
        if kind == 'nowiki':
            body = body.strip('\n')
            if '\n' in body:
                return f'```text\n{body}\n```'
            fence = '`' * (max((len(x) for x in re.findall(r'`+', body)), default=0) + 1)
            return f'{fence}{body}{fence}'
        if kind == 'php':
            lang = 'php'
        elif kind == 'html':
            lang = 'html'
        lang = LANG_MAP.get(lang, 'text')
        body = body.strip('\n')
        return f'```{lang}\n{body}\n```'

    def _line(self, line: str, tokens: TokenStore) -> str:
        stripped = line.strip()

        # 标题
        m = HEADING_RE.match(stripped)
        if m:
            level = max(1, 7 - len(m.group(1)))
            return '#' * level + ' ' + m.group(2).strip()

        # 强制分隔线
        if re.match(r'^-{4,}\s*$', stripped):
            return '---'

        # 控制指令
        if re.match(r'^~~[A-Z]+~~$', stripped):
            return ''

        # 表格行
        if stripped[:1] in ('^', '|') and stripped.count('^') + stripped.count('|') >= 2 \
                and stripped[0] in '^|' and stripped[-1] in '^|':
            cells, seps = [], []
            for cm in re.finditer(r'([|^])([^|^]*)', stripped):
                seps.append(cm.group(1))
                cells.append(cm.group(2).strip())
            # 行尾分隔符会多出一个空单元格，去掉
            if cells and not cells[-1]:
                cells.pop()
            if not cells:
                return line
            seps = seps[:len(cells)]
            row = '| ' + ' | '.join(cells) + ' |'
            if all(s == '^' for s in seps):
                sep = '| ' + ' | '.join(['---'] * len(cells)) + ' |'
                return row + '\n' + sep
            return row

        # 列表
        m = LIST_RE.match(line)
        if m:
            indent, marker, _sp, body = m.group(1), m.group(2), m.group(3), m.group(4)
            md_marker = '-' if marker == '*' else '1.'
            return f'{indent}{md_marker} {body}'

        # 引用
        if re.match(r'^\s*>\s?', line):
            return re.sub(r'^\s*>\s?', '> ', line)

        return line

    def _inline(self, text: str, tokens: TokenStore) -> str:
        # 1. 链接 [[target|label]]
        def repl_link(m: re.Match) -> str:
            raw = m.group(1)
            target, _, label = raw.partition('|')
            target = target.strip()
            label = label.strip() or target
            if re.match(r'^(https?|ftp|mailto|tel):', target, re.I):
                return tokens.add(f'[{label}]({target})')
            page = self._resolve_page(target)
            if page:
                return tokens.add(f'[{label}]({page})')
            self.unresolved.append(f'{target}  (原文: {raw})')
            return tokens.add(label)

        text = re.sub(r'\[\[([^\]]+?)\]\]', repl_link, text)

        # 2. 媒体 {{target?params|alt}}
        def repl_media(m: re.Match) -> str:
            raw = m.group(1).strip()
            target, _, alt = raw.partition('|')
            target = target.split('?', 1)[0].strip()
            alt = alt.strip()
            if re.match(r'^(https?|ftp):', target, re.I):
                alt = alt or Path(urllib.parse.urlparse(target).path).name
                return tokens.add(f'![{alt}]({target})')
            rel = self._resolve_media(target)
            if rel:
                return tokens.add(f'![{alt}]({self.image_prefix}/{rel})')
            self.unresolved.append(f'media {target}')
            return tokens.add(alt or target)

        text = re.sub(r'\{\{([^}]+?)\}\}', repl_media, text)

        # 3. 行内样式（此时链接已占位，不会误伤 URL）
        text = re.sub(r"''([^'\n]+?)''", lambda m: tokens.add('`' + m.group(1).strip() + '`'), text)
        text = re.sub(r'\*\*([^*\n]+?)\*\*', lambda m: tokens.add('**' + m.group(1).strip() + '**'), text)
        text = re.sub(r'(?<![\w:])//([^/\n]+?)//', lambda m: tokens.add('*' + m.group(1).strip() + '*'), text)
        text = re.sub(r'(?<![\w])__([^_\n]+?)__', lambda m: tokens.add('<u>' + m.group(1).strip() + '</u>'), text)

        # 4. 脚注 → 行内括号（Markdown 无标准脚注，保持可读）
        text = re.sub(r'\(\(([^()\n]{1,120})\)\)', lambda m: tokens.add('(' + m.group(1).strip() + ')'), text)

        # 5. 行尾强制换行
        text = re.sub(r'\\\\\s*$', lambda m: tokens.add('  '), text)
        return text

class DokuWikiImporter:
    def __init__(self, data_dir: Path, blog: Blog,
                 include_defaults: bool = False, force: bool = False):
        self.data_dir = data_dir
        self.pages_dir = data_dir / 'pages'
        self.media_dir = data_dir / 'media'
        self.meta_dir = data_dir / 'meta'
        self.blog = blog
        self.include_defaults = include_defaults
        self.force = force
        self.report = ImportReport()
        self.page_index: dict[str, str] = {}
        self.media_index: dict[str, str] = {}
        self.categories: dict[str, str] = {}

    # ---------- 扫描 ----------
    def _should_skip(self, rel: Path) -> bool:
        parts = rel.parts
        if any(p.startswith('_') or p.startswith('.') for p in parts):
            return True
        if not self.include_defaults:
            ns = parts[0] if len(parts) > 1 else ''
            if ns in DEFAULT_SKIP_NAMESPACES:
                return True
        return False

    def _scan_pages(self) -> list[tuple[Path, str]]:
        pages = []
        for p in sorted(self.pages_dir.rglob('*.txt')):
            rel = p.relative_to(self.pages_dir)
            if self._should_skip(rel):
                self.report.skipped.append(urllib.parse.unquote(str(rel)))
                continue
            # 磁盘上的文件名是 URL 编码的（如 %E4%B8%AD%E6%96%87.txt），需解码
            stem = urllib.parse.unquote(str(rel.with_suffix(''))).replace('/', '_')
            pages.append((p, stem + '.md'))
        return pages

    def _scan_media(self) -> None:
        if not self.media_dir.is_dir():
            return
        for p in sorted(self.media_dir.rglob('*')):
            if not p.is_file() or p.name.startswith('.'):
                continue
            rel = p.relative_to(self.media_dir)
            if 'backup' in rel.parts or rel.parts[0] in DEFAULT_SKIP_NAMESPACES \
                    and not self.include_defaults:
                continue
            key = clean_id(str(rel.with_suffix('')))
            self.media_index[key] = p.name
            self.media_index[clean_id(p.name)] = p.name

    def _load_categories(self) -> None:
        """从 start.txt / index 页解析「分类 → 页面」映射，作为标签来源"""
        for candidate in ('start.txt', 'index.txt', 'welcome.txt'):
            f = self.pages_dir / candidate
            if f.is_file():
                break
        else:
            return
        current = ''
        for line in f.read_text(encoding='utf-8', errors='replace').splitlines():
            m = HEADING_RE.match(line.strip())
            if m:
                current = m.group(2).strip()
                continue
            m = re.match(r'^\s*[*\-]\s+\[\[([^\]|]+)', line)
            if m and current:
                self.categories[clean_id(m.group(1))] = current

    def _page_date(self, page: Path) -> str:
        rel = page.relative_to(self.pages_dir)
        changes = self.meta_dir / rel.parent / (rel.stem + '.changes')
        if changes.is_file():
            try:
                stamps = []
                for line in changes.read_text(encoding='utf-8', errors='replace').splitlines():
                    head = line.split('\t', 1)[0]
                    if head.isdigit():
                        stamps.append(int(head))
                if stamps:
                    return datetime.fromtimestamp(min(stamps)).strftime('%Y-%m-%d')
            except OSError:
                pass
        return datetime.fromtimestamp(page.stat().st_mtime).strftime('%Y-%m-%d')

    # ---------- 执行 ----------
    def run(self, dry_run: bool = False) -> ImportReport:
        pages = self._scan_pages()
        # DokuWiki start.txt（站点首页）→ 重命名为 index.md，作为博客网站首页
        # 如果已经有 index.md（可能用户自己创建的），则保留不覆盖
        start_idx = None
        for i, (p, name) in enumerate(pages):
            if name in ('start.md', 'index.md', 'welcome.md'):
                start_idx = i
                break
        if start_idx is not None:
            original = pages[start_idx]
            # 目标 index.md 已存在则不动
            target_index = self.blog.abs_content_dir / 'index.md'
            if target_index.is_file() and not self.force:
                start_idx = None   # 放弃重命名，继续按原名导入
            else:
                # 如果列表里本来就有另一个 index.md（用户自己写的），跳过这个 start
                if any(n == 'index.md' and j != start_idx for j, (_p, n) in enumerate(pages)):
                    start_idx = None
                else:
                    pages[start_idx] = (original[0], 'index.md')

        for _p, name in pages:
            self.page_index[clean_id(Path(name).stem)] = name
            self.page_index[loose_key(Path(name).stem)] = name

        self._scan_media()
        self._load_categories()

        converter = DokuWikiConverter(
            self.page_index, self.media_index,
            image_prefix='../' + (self.blog.image_dir.strip('/') or 'images'),
        )

        content_dir = self.blog.abs_content_dir
        image_dir = self.blog.abs_image_dir

        for page, name in pages:
            dest = content_dir / name
            is_index = name == 'index.md'
            if dest.exists() and not self.force and not is_index:
                # index.md 已有且非 force：保留作者自己写的，跳过导入
                self.report.existing.append(name)
                continue
            raw = page.read_text(encoding='utf-8', errors='replace')
            unresolved: list[str] = []
            body = converter.convert(raw, unresolved)
            # index.md：清理 DokuWiki start.txt 里的原生索引区块（站点地图/最近文章等），
            # 这些区块的职责已由 site_builder 接管，清理后避免双份列表
            if is_index:
                body = _cleanup_dokuwiki_index(body)
            if unresolved:
                self.report.unresolved_links.extend(f'{name}: {u}' for u in unresolved)

            title = page_title(raw, Path(name).stem)
            date = self._page_date(page)
            tags = []
            cat = self.categories.get(clean_id(Path(name).stem))
            if cat:
                tags = [cat]

            doc_parts = [
                '---',
                f'title: {title}',
                f'date: {date}',
                f'tags: [{", ".join(tags)}]',
                '---',
                '',
                body,
            ]
            # index.md 结尾注入 site_builder 动态区块边界占位
            if is_index:
                doc_parts += [
                    '', '<!-- site_builder:start 以下列表由 site_builder 自动生成，不要手动编辑 -->', '',
                    '_（导入后请先运行 site_builder 以生成文章列表）_', '',
                    '<!-- site_builder:end -->',
                ]
            doc = '\n'.join(doc_parts) + '\n'

            if not dry_run:
                content_dir.mkdir(parents=True, exist_ok=True)
                dest.write_text(doc, encoding='utf-8')
            self.report.imported.append(name)

        # 媒体搬运：只复制被 Markdown 引用到的文件
        if not dry_run:
            self._copy_used_media()

        return self.report

    def _copy_used_media(self) -> None:
        if not self.media_dir.is_dir():
            return
        used = set()
        for md in self.blog.abs_content_dir.glob('*.md'):
            for m in re.finditer(re.escape(self.blog.image_dir.strip('/')) + r'/([^)\s]+)', md.read_text(encoding='utf-8')):
                used.add(urllib.parse.unquote(m.group(1)))
        for name in sorted(used):
            src = None
            for p in self.media_dir.rglob(name):
                if p.is_file():
                    src = p
                    break
            if not src:
                self.report.warnings.append(f'图片源未找到: {name}')
                continue
            dest = self.blog.abs_image_dir / Path(name).name
            self.blog.abs_image_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            self.report.media_copied.append(dest.name)


def main() -> int:
    ap = argparse.ArgumentParser(description='DokuWiki 数据目录 → Markdown 博客')
    ap.add_argument('data_dir', help='DokuWiki 的 data 目录（含 pages/ media/）')
    ap.add_argument('blog_dir', help='目标博客仓库目录（需含 .blog.yaml）')
    ap.add_argument('--include-defaults', action='store_true',
                    help='同时导入 wiki:/playground: 命名空间（默认跳过）')
    ap.add_argument('--force', action='store_true', help='覆盖已存在的 Markdown 文件')
    ap.add_argument('--dry-run', action='store_true', help='只统计，不写文件')
    args = ap.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    blog_dir = Path(args.blog_dir).expanduser().resolve()

    if not (data_dir / 'pages').is_dir():
        print(f'错误: {data_dir} 下没有 pages/ 目录', file=sys.stderr)
        return 1
    yaml_path = blog_dir / '.blog.yaml'
    if not yaml_path.is_file():
        print(f'错误: {blog_dir} 不是博客仓库（缺少 .blog.yaml）', file=sys.stderr)
        return 1

    blog = Blog.from_yaml(yaml_path, path=blog_dir)
    importer = DokuWikiImporter(data_dir, blog, args.include_defaults, args.force)
    report = importer.run(dry_run=args.dry_run)

    print(f'博客: {blog.blog_name}  ({blog_dir})')
    print(f'导入: {len(report.imported)} 篇' + ('（dry-run 未写入）' if args.dry_run else ''))
    print(f'跳过命名空间: {len(report.skipped)} 个页面')
    if report.existing:
        print(f'已存在跳过: {len(report.existing)} 篇')
    if report.media_copied:
        print(f'图片复制: {len(report.media_copied)} 个 → {blog.image_dir}')
    if report.unresolved_links:
        print(f'未解析链接: {len(report.unresolved_links)} 处')
        for u in report.unresolved_links[:10]:
            print('   -', u)
    for w in report.warnings:
        print('警告:', w)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
