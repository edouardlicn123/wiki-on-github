#!/usr/bin/env python3
"""静态站点生成器：博客仓库 md/*.md → html/*.html（GitHub Pages 托管）

只依赖 Python 标准库。渲染范围覆盖项目导入/编辑产生的 Markdown 子集：
标题、代码块、行内代码、粗体/斜体、链接、图片、列表（含嵌套）、表格、
引用、分隔线、段落，以及原样透传的内联 HTML（如 <u>）。

博客仓库布局（由 agent.md 冻结，所有博客必须遵守）：
    blog-repo/
    ├── index.html              ← 根目录重定向（meta refresh + JS）→ html/index.html
    ├── .blog.yaml              ← 仓库标识文件（编辑器靠它发现博客）
    ├── .nojekyll               ← 关 Jekyll，Pages 按静态文件服务
    ├── README.md               ← 仓库介绍（不承担首页职责）
    ├── md/                     ← 所有文章 Markdown 源文件
    │   ├── index.md            ← 博客网站首页（front matter + 动态区块）
    │   └── *.md                ← 各篇文章
    ├── html/                   ← site_builder 渲染产物
    │   ├── index.html          ← 博客首页（由 md/index.md 渲染）
    │   ├── *.html              ← 各篇文章
    │   └── assets/site.css
    └── images/                 ← 图片（md 里统一写 ../images/xxx.png）

site_builder 每次构建做三件事（循环构建不产生重复）：
    1) 读 md/index.md → 正则替换 <!-- site_builder:start/end --> 边界内内容为最新 Markdown 列表
    2) 渲染 md/*.md → html/*.html（内部 .md 链接自动改 .html）
    3) 回写 md/index.md（让源文件在 GitHub 上打开也能直接看到完整列表）

作者写文章的两个约定（render_inline 会自动处理）：
    - 内部链接一律写 [x](目标文件名.md)，渲染时自动改成 .html
    - 图片一律写 ../images/xxx.png（md/ → html/，往上一层 = images/）
"""

from __future__ import annotations

import html
import re
import shutil
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from blog_manager import Blog  # noqa: E402

FENCE_RE = re.compile(r'^```([\w+-]*)\s*$')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
LIST_RE = re.compile(r'^(\s*)(-|\d+\.)\s+(.*)$')
TABLE_RE = re.compile(r'^\s*\|')
QUOTE_RE = re.compile(r'^\s*>\s?')

LINK_RE = re.compile(r'!?\[([^\]]*)\]\(([^)\s]+)\)')
TAG_RE = re.compile(r'<[/!]?[a-zA-Z][^>]*>')


@dataclass
class Post:
    slug: str
    title: str
    date: str
    tags: list[str]
    body: str


def split_front_matter(raw: str) -> tuple[dict, str]:
    """拆出 YAML front matter（只支持本项目用到的扁平整/列表字段）"""
    if not raw.startswith('---'):
        return {}, raw
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?', raw, re.S)
    if not m:
        return {}, raw
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        k, v = k.strip(), v.strip().strip('"\'')
        if v.startswith('[') and v.endswith(']'):
            items = [x.strip().strip('"\'') for x in v[1:-1].split(',')]
            meta[k] = [x for x in items if x]
        else:
            meta[k] = v
    return meta, raw[m.end():]


def post_href(slug: str) -> str:
    return urllib.parse.quote(slug + '.html')


# ───────────────────────────── 行内渲染 ─────────────────────────────
def render_inline(text: str) -> str:
    """渲染行内元素（所有调用均为 html/ 目录下的文章页，无需参数）

    自动处理的两个约定：
        - 站内 .md 链接 → 去掉 .md 后缀、剥掉任意路径前缀（md/、../md/、./ 等）、加 .html
        - 图片 ../images/xxx.png → 原样保留（html/ 往上一层恰好 = images/）
    """
    def repl(m: re.Match) -> str:
        alt, url = m.group(1), m.group(2)
        is_img = m.group(0).startswith('!')
        # 站内 .md 链接 → .html
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', url) and url.endswith('.md'):
            stripped = urllib.parse.unquote(url[:-3])
            stripped = stripped.replace('../', '').replace('./', '')
            if '/' in stripped:
                stripped = stripped.rsplit('/', 1)[-1]   # 剥掉任意层级目录，只留文件名
            url = post_href(stripped)
        if is_img:
            return f'<img src="{html.escape(url)}" alt="{html.escape(alt)}">'
        return f'<a href="{html.escape(url)}">{html.escape(alt)}</a>'

    # 先把链接整体替换成占位符，避免内部 * / ` 被后续规则误伤
    holders: list[str] = []

    def hold(h: str) -> str:
        holders.append(h)
        return f'\x01{len(holders) - 1}\x01'

    text = LINK_RE.sub(lambda m: hold(repl(m)), text)
    text = re.sub(r'`([^`]+)`', lambda m: hold(f'<code>{html.escape(m.group(1))}</code>'), text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<![\w*])\*([^*\n]+?)\*(?![\w*])', r'<em>\1</em>', text)
    text = re.sub(r'\x01(\d+)\x01', lambda m: holders[int(m.group(1))], text)
    return text


# ───────────────────────────── 块级渲染 ─────────────────────────────
def render_markdown(text: str) -> str:
    """渲染 Markdown 正文（所有调用均为 html/ 目录下的文章页，无需参数）"""
    def inline(s: str) -> str:
        return render_inline(s)

    lines = text.replace('\r\n', '\n').split('\n')
    out: list[str] = []
    i, n = 0, len(lines)

    def is_block_start(s: str) -> bool:
        return bool(FENCE_RE.match(s) or HEADING_RE.match(s) or TABLE_RE.match(s)
                    or QUOTE_RE.match(s) or LIST_RE.match(s) or re.match(r'^---+$', s.strip()))

    while i < n:
        line = lines[i]

        fence = FENCE_RE.match(line)
        if fence:
            lang = fence.group(1)
            i += 1
            buf = []
            while i < n and not FENCE_RE.match(lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="lang-{html.escape(lang)}"' if lang else ''
            out.append(f'<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>')
            continue

        m = HEADING_RE.match(line)
        if m:
            lv = len(m.group(1))
            out.append(f'<h{lv}>{inline(m.group(2).strip())}</h{lv}>')
            i += 1
            continue

        if re.match(r'^---+\s*$', line.strip()):
            out.append('<hr>')
            i += 1
            continue

        if TABLE_RE.match(line):
            rows = []
            while i < n and TABLE_RE.match(lines[i]):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                rows.append(cells)
                i += 1
            header = rows[0] if rows else []
            is_sep = lambda r: all(set(c) <= set('-: ') and c for c in r) and all('-' in c for c in r)
            body_rows = [r for r in rows[1:] if not is_sep(r)]
            t = ['<table>']
            if header and rows[1:2] and is_sep(rows[1]):
                t.append('<thead><tr>')
                t.append(''.join(f'<th>{inline(c)}</th>' for c in header))
                t.append('</tr></thead>')
            t.append('<tbody>')
            for r in body_rows:
                t.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>')
            t.append('</tbody></table>')
            out.append(''.join(t))
            continue

        if QUOTE_RE.match(line):
            buf = []
            while i < n and QUOTE_RE.match(lines[i]):
                buf.append(QUOTE_RE.sub('', lines[i]))
                i += 1
            out.append(f'<blockquote>{inline(chr(10).join(buf))}</blockquote>')
            continue

        if LIST_RE.match(line):
            html_list, i = render_list(lines, i, inline)
            out.append(html_list)
            continue

        if not line.strip():
            i += 1
            continue

        # 段落
        buf = []
        while i < n and lines[i].strip() and not is_block_start(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        # 行尾两个空格 + 换行 = <br>
        para = '\n'.join(buf)
        para = re.sub(r'  +\n', '<br>', para)
        out.append(f'<p>{inline(para)}</p>')

    return '\n'.join(out)


def render_list(lines: list[str], start: int, inline) -> tuple[str, int]:
    """把连续的 - / 1. 行转成（可嵌套的）列表"""
    i, n = start, len(lines)
    stack: list[tuple[int, str]] = []   # (indent, 'ul'|'ol')
    parts: list[str] = []

    def open_list(indent: int, kind: str) -> None:
        stack.append((indent, kind))
        parts.append(f'<{kind}>')

    def close_until(indent: int) -> None:
        while stack and stack[-1][0] > indent:
            parts.append(f'</{stack.pop()[1]}>')

    while i < n:
        m = LIST_RE.match(lines[i])
        if not m:
            break
        indent = len(m.group(1).expandtabs(2))
        kind = 'ul' if m.group(2) == '-' else 'ol'
        close_until(indent)

        if not stack:
            open_list(indent, kind)
        elif stack[-1][1] != kind:
            parts.append(f'</{stack.pop()[1]}>')
            open_list(indent, kind)
        elif stack[-1][0] < indent:
            open_list(indent, kind)

        parts.append(f'<li>{inline(m.group(3).strip())}</li>')
        i += 1

        # 列表项后续的缩进续行，并入当前条目
        while i < n and lines[i].strip() and not LIST_RE.match(lines[i]) \
                and not is_other_block(lines[i]):
            parts[-1] = parts[-1][:-5] + ' ' + inline(lines[i].strip()) + '</li>'
            i += 1

    close_until(-1)
    return ''.join(parts), i


def is_other_block(line: str) -> bool:
    return bool(FENCE_RE.match(line) or HEADING_RE.match(line) or TABLE_RE.match(line)
                or QUOTE_RE.match(line))


# ───────────────────────────── 页面模板 ─────────────────────────────
SITE_CSS = """\
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0 auto; max-width: 860px; padding: 32px 20px 80px;
  font: 16px/1.75 -apple-system, "Segoe UI", "Noto Sans SC", sans-serif;
  color: #1f2328; background: #fff;
}
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
header.site { border-bottom: 1px solid #d8dee4; padding-bottom: 12px; margin-bottom: 28px; }
header.site a { font-size: 18px; font-weight: 600; }
h1, h2, h3, h4, h5, h6 { line-height: 1.35; margin: 28px 0 12px; }
.meta { color: #6e7781; font-size: 13px; margin-bottom: 24px; }
.meta .tag { display: inline-block; margin-left: 6px; padding: 1px 8px;
  border-radius: 999px; background: #eff2f5; color: #57606a; }
pre { background: #f6f8fa; padding: 14px 16px; border-radius: 8px; overflow: auto; }
code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 13.5px; }
:not(pre) > code { background: #eff2f5; padding: 2px 5px; border-radius: 4px; }
img { max-width: 100%; height: auto; border-radius: 6px; }
table { border-collapse: collapse; margin: 16px 0; width: 100%; }
th, td { border: 1px solid #d8dee4; padding: 7px 12px; text-align: left; }
th { background: #f6f8fa; }
blockquote { margin: 16px 0; padding: 2px 16px; border-left: 3px solid #d8dee4; color: #57606a; }
hr { border: 0; border-top: 1px solid #d8dee4; margin: 28px 0; }
ul.posts { list-style: none; padding: 0; }
ul.posts li { padding: 10px 0; border-bottom: 1px solid #eaeef2; }
ul.posts .date { color: #6e7781; font-size: 13px; margin-right: 12px;
  font-family: ui-monospace, monospace; }
footer.site { margin-top: 60px; padding-top: 16px; border-top: 1px solid #d8dee4;
  color: #6e7781; font-size: 13px; }
@media (prefers-color-scheme: dark) {
  body { color: #e6edf3; background: #0d1117; }
  a { color: #4493f8; }
  header.site, footer.site, ul.posts li, hr { border-color: #30363d; }
  pre, th { background: #161b22; }
  :not(pre) > code, .meta .tag { background: #21262d; color: #8b949e; }
  th, td { border-color: #30363d; }
  .meta { color: #8b949e; }
  blockquote { border-color: #3d444d; color: #8b949e; }
  footer.site { color: #8b949e; }
}
"""


def page(title: str, blog_name: str, content: str, css_href: str, home_href: str,
         extra_head: str = '') -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
{extra_head}
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<header class="site"><a href="{home_href}">{html.escape(blog_name)}</a></header>
{content}
<footer class="site">Generated by wiki-on-github</footer>
</body>
</html>
"""


def build_blog_site(blog: Blog) -> dict:
    """渲染整个博客站点，返回统计信息

    输出布局：
        index.html          仓库根 → 极简重定向（跳 html/index.html）
        html/index.html     博客首页（由 md/index.md 渲染而来）
        html/<文章名>.html  每篇文章
        html/assets/site.css
    """
    content_dir = blog.abs_content_dir
    out_dir = blog.path / 'html'
    out_dir.mkdir(exist_ok=True)
    posts: list[Post] = []

    for md in sorted(content_dir.glob('*.md')):
        raw = md.read_text(encoding='utf-8', errors='replace')
        meta, body = split_front_matter(raw)
        title = str(meta.get('title') or md.stem)
        tags = meta.get('tags') or []
        if isinstance(tags, str):
            tags = [tags]
        posts.append(Post(
            slug=md.stem,
            title=title,
            date=str(meta.get('date') or ''),
            tags=[str(t) for t in tags],
            body=render_markdown(body),
        ))

    # 找出首页和普通文章
    index_post = next((p for p in posts if p.slug == 'index'), None)
    regular_posts = [p for p in posts if p.slug != 'index']
    regular_posts.sort(key=lambda p: (p.date, p.slug), reverse=True)

    # 文章页 → html/（所有文章、首页都在一起，相对路径统一）
    for p in posts:
        meta_bits = []
        if p.date:
            meta_bits.append(html.escape(p.date))
        meta_bits += [f'<span class="tag">{html.escape(t)}</span>' for t in p.tags]
        meta_html = f'<div class="meta">{" ".join(meta_bits)}</div>' if meta_bits else ''
        content = f'<main>\n<h1>{html.escape(p.title)}</h1>\n{meta_html}\n{p.body}\n</main>'
        home_href = 'index.html' if p.slug == 'index' else '../index.html'
        (out_dir / f'{p.slug}.html').write_text(
            page(f'{p.title} · {blog.blog_name}', blog.blog_name, content,
                 css_href='assets/site.css', home_href=home_href),
            encoding='utf-8',
        )

    # 首页专属：生成 Markdown 格式的文章列表，替换进 md/index.md 并渲染成 html/index.html
    # Markdown 格式的好处是：
    #   - md/index.md 本身在 GitHub 上能直接浏览（不需要任何 JS）
    #   - site_builder 可以反复替换边界内的内容，循环构建不产生重复
    # 链接一律写成 .md 结尾，site_builder 渲染成 html 时 render_markdown 会自动改 .html
    md_items = '\n'.join(
        '- %s [%s](%s.md)%s' % (
            (f'**{p.date}** ' if p.date else ''),
            html.escape(p.title),
            post_href(p.slug).removesuffix('.html'),   # 还原成 md 名
            ''.join(f' `{html.escape(t)}`' for t in p.tags),
        )
        for p in regular_posts
    )
    md_list = md_items if regular_posts else '_（暂无文章）_'

    if index_post:
        raw = (content_dir / 'index.md').read_text(encoding='utf-8', errors='replace')
        meta, body = split_front_matter(raw)
        home_title = str(meta.get('title') or blog.blog_name)
        desc_html = (
            f'<meta name="description" content="{html.escape(str(meta.get("description") or blog.description or ""))}">'
        )
        # 先清理正文中已有的"最近文章"区块（包括用户手写列表 + site_builder 边界注释），
        # 避免 dw_import 等场景残留用户自己的旧列表导致渲染重复
        body = re.sub(
            r'\n##\s+最近文章\s*\n?(.*?)(?=\n#{1,6}\s|\Z)',
            '\n', body, count=1, flags=re.DOTALL,
        )
        # 注入干净的新块
        body = (body.rstrip() + '\n\n## 最近文章\n\n'
                + '<!-- site_builder:start 以下列表由 site_builder 自动生成，不要手动编辑 -->\n\n' + md_list
                + '\n\n<!-- site_builder:end -->')
        # 回写 md/index.md（让源文件在 GitHub 上也直接可见）
        front_lines = ['---']
        for k, v in meta.items():
            if k == 'tags' and isinstance(v, list): v = '[' + ', '.join(str(x) for x in v) + ']'
            front_lines += [f'{k}: {v}']
        front_lines += ['---', '']
        (content_dir / 'index.md').write_text('\n'.join(front_lines) + body.lstrip('\n'),
                                              encoding='utf-8')
        home_body_html = render_markdown(body)
    else:
        home_title = blog.blog_name
        desc_html = ''
        desc = f'<p>{html.escape(blog.description)}</p>' if blog.description else ''
        # 没有 md/index.md 就动态拼一个（不写回，只用于这次渲染）
        fallback = (
            f'# {blog.blog_name}\n\n'
            + (f'{blog.description}\n\n' if blog.description else '')
            + '## 最近文章\n\n'
            + '<!-- site_builder:start 以下列表由 site_builder 自动生成，不要手动编辑 -->\n\n' + md_list
            + '\n\n<!-- site_builder:end -->'
        )
        home_body_html = render_markdown(fallback)
        # 首次没有 index.md，主动写一份（让下次循环构建能跑）
        blog.write_index_md()

    index_content = f'<main>\n{home_body_html}\n</main>'
    (out_dir / 'index.html').write_text(
        page(home_title, blog.blog_name, index_content,
             css_href='assets/site.css', home_href='index.html',
             extra_head=desc_html),
        encoding='utf-8',
    )

    # 根目录 index.html → 重定向到 html/index.html（GitHub Pages 访问根路径时生效）
    root_redirect = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=html/index.html">
<title>{html.escape(blog.blog_name)}</title>
<script>window.location.replace('html/index.html');</script>
</head>
<body><p><a href="html/index.html">进入博客首页</a></p></body>
</html>
"""
    (blog.path / 'index.html').write_text(root_redirect, encoding='utf-8')

    assets = out_dir / 'assets'
    assets.mkdir(exist_ok=True)
    (assets / 'site.css').write_text(SITE_CSS, encoding='utf-8')

    # 清理旧布局残留：根目录的文章页、根目录的 assets/、html/ 里已删除文章的页面
    slugs = {p.slug for p in posts}
    for old in blog.path.glob('*.html'):
        if old.name != 'index.html' and old.stem in slugs:
            old.unlink()
    for old in out_dir.glob('*.html'):
        if old.stem not in slugs:
            old.unlink()
    legacy_assets = blog.path / 'assets'
    if (legacy_assets / 'site.css').is_file():
        shutil.rmtree(legacy_assets)

    return {
        'ok': True,
        'pages': len(posts),
        'homepage': blog.homepage_url,
        'files': [f'html/{p.slug}.html' for p in posts[:5]],
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description='把博客的 posts/*.md 渲染成静态站点')
    ap.add_argument('blog_dir', help='博客仓库目录（需含 .blog.yaml）')
    args = ap.parse_args()

    blog_dir = Path(args.blog_dir).expanduser().resolve()
    yaml_path = blog_dir / '.blog.yaml'
    if not yaml_path.is_file():
        print(f'错误: {blog_dir} 缺少 .blog.yaml', file=sys.stderr)
        return 1

    blog = Blog.from_yaml(yaml_path, path=blog_dir)
    report = build_blog_site(blog)
    print(f'站点已生成: {report["pages"]} 篇文章 → {blog_dir}')
    print(f'首页: {blog_dir / "index.html"}')
    if report['homepage']:
        print(f'在线地址: {report["homepage"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
