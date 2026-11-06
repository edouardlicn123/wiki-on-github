#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blog_manager.py — 博客仓库的发现、识别、模板写入、git 同步

核心约束:
- 与博客仓库同级（编辑器父目录的兄弟目录）
- 博客仓库靠根目录的 .blog.yaml 标识
- 用户自己操作 GitHub clone，这里只做本地操作
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ───────────────────────────── GitHub Pages 地址推导 ─────────────────────────────
def derive_pages_url(repo_url: str) -> str:
    """
    从 GitHub 仓库地址推导 Pages 实际首页地址:
      https://github.com/user/user.github.io  → https://user.github.io/
      https://github.com/user/blog            → https://user.github.io/blog/
      git@github.com:user/blog.git            → https://user.github.io/blog/
    """
    if not repo_url:
        return ''
    m = re.search(r'github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$', repo_url.strip())
    if not m:
        return ''
    owner, repo = m.group(1), m.group(2)
    if repo.lower() == f'{owner.lower()}.github.io':
        return f'https://{owner}.github.io/'
    return f'https://{owner}.github.io/{repo}/'


# ───────────────────────────── .blog.yaml 极简解析器 ─────────────────────────────
def parse_simple_yaml(text: str) -> dict:
    """
    极简 YAML 解析器 — 只处理我们 .blog.yaml 里用到的几种格式:
      key: value
      key: "quoted value"
      key: [a, b, c]           # 简单数组
    不支持嵌套对象 / 多行字符串等，够用就行。
    """
    result = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith('#'):
            continue
        # 注释剥离
        if '#' in line:
            # 但要小心引号里的 # — 简单起见只处理非引号场景
            stripped = re.sub(r'"[^"]*"', '', line)
            if '#' in stripped:
                line = line[:stripped.index('#')].rstrip()
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$', line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        # 去掉引号
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        # 数组 [a, b, c]
        if val.startswith('[') and val.endswith(']'):
            inner = val[1:-1].strip()
            val = [v.strip().strip('"').strip("'") for v in inner.split(',')] if inner else []
        elif val == '' or val.lower() == 'null':
            val = None
        result[key] = val
    return result


def render_simple_yaml(data: dict) -> str:
    """反向: dict → .blog.yaml 文本（输出我们支持的格式）"""
    lines = []
    for k, v in data.items():
        if v is None:
            lines.append(f'{k}:')
        elif isinstance(v, list):
            joined = ', '.join(str(x) for x in v)
            lines.append(f'{k}: [{joined}]')
        elif isinstance(v, str):
            if any(c in v for c in [':', '#', '"']) or v.startswith(' '):
                lines.append(f'{k}: "{v}"')
            else:
                lines.append(f'{k}: {v}')
        else:
            lines.append(f'{k}: {v}')
    return '\n'.join(lines) + '\n'


# ───────────────────────────── Blog 数据类 ─────────────────────────────
@dataclass
class Blog:
    """一个博客仓库"""
    blog_name: str
    path: Path                          # 仓库本地路径
    repo_url: str = ''
    repo_branch: str = 'main'
    content_dir: str = 'md/'
    image_dir: str = 'images/'
    pages_url: str = ''
    description: str = ''
    schema_version: int = 1

    # 计算属性
    @property
    def yaml_path(self) -> Path:
        return self.path / '.blog.yaml'

    @property
    def abs_content_dir(self) -> Path:
        return self.path / self.content_dir

    @property
    def abs_image_dir(self) -> Path:
        return self.path / self.image_dir

    @property
    def homepage_url(self) -> str:
        """博客网站的实际首页地址（.blog.yaml 未填时从 repo_url 推导）"""
        return self.pages_url or derive_pages_url(self.repo_url)

    @classmethod
    def from_yaml(cls, yaml_path: Path, path: Optional[Path] = None) -> 'Blog':
        raw = yaml_path.read_text(encoding='utf-8')
        data = parse_simple_yaml(raw)
        return cls(
            blog_name=data.get('blog_name', yaml_path.parent.name),
            path=path or yaml_path.parent,
            repo_url=data.get('repo_url', ''),
            repo_branch=data.get('repo_branch', 'main') or 'main',
            content_dir=data.get('content_dir', 'md/') or 'md/',
            image_dir=data.get('image_dir', 'images/') or 'images/',
            pages_url=data.get('pages_url', ''),
            description=data.get('description', ''),
            schema_version=int(data.get('schema_version', 1) or 1),
        )

    def to_yaml(self) -> str:
        data = {
            'schema_version': self.schema_version,
            'blog_name': self.blog_name,
            'description': self.description,
            'repo_url': self.repo_url,
            'repo_branch': self.repo_branch,
            'content_dir': self.content_dir,
            'image_dir': self.image_dir,
            'pages_url': self.pages_url,
        }
        return render_simple_yaml(data)

    def write_yaml(self) -> None:
        self.yaml_path.write_text(self.to_yaml(), encoding='utf-8')

    def write_readme(self) -> None:
        """写 README.md — 仓库介绍（只承担 GitHub 仓库首页展示的角色）

        博客网站首页已独立为 md/index.md，README 只写基本信息和跳转链接。
        """
        url = self.homepage_url or ''
        lines = [f'# {self.blog_name}', '']
        if self.description:
            lines += [self.description, '']
        lines += [
            '## 博客地址', '',
            f'在线浏览：[{url or "(未配置)"}]({url})', '',
            '## 博客首页', '',
            '博客网站首页是 [md/index.md](./md/index.md)，它会被自动渲染成静态首页。', '',
            '## 源码仓库', '',
            f'[{self.repo_url or "(未配置)"}]({self.repo_url})', '',
        ]
        (self.path / 'README.md').write_text('\n'.join(lines), encoding='utf-8')

    def write_index_md(self) -> None:
        """写 md/index.md — 博客网站首页（带 front matter + site_builder 动态区块）

        这是博客网站首页的 Markdown 源文件，site_builder 每次构建时：
          1) 读 md/index.md → 把 <!-- site_builder:start/end --> 之间的旧列表换成新的
          2) 渲染成 html/index.html
          3) 回写 md/index.md（让源文件本身在 GitHub 上也可直接浏览）

        DokuWiki 迁移时，源站的 start.txt（首页）会直接转成本文件。
        """
        url = self.homepage_url or ''
        cdir = self.abs_content_dir
        cdir.mkdir(parents=True, exist_ok=True)
        lines = ['---']
        lines += [f'title: {self.blog_name}']
        if self.description:
            lines += [f'description: {self.description}']
        if url:
            lines += [f'homepage: {url}']
        if self.repo_url:
            lines += [f'repo_url: {self.repo_url}']
        lines += ['---', '', f'# {self.blog_name}', '']
        if self.description:
            lines += [self.description, '']
        lines += [
            '## 最近文章', '',
            '<!-- site_builder:start 以下列表由 site_builder 自动生成，不要手动编辑 -->', '',
            '_（尚未生成，请先运行 site_builder）_', '',
            '<!-- site_builder:end -->', '',
        ]
        (cdir / 'index.md').write_text('\n'.join(lines), encoding='utf-8')

    def list_posts(self) -> list[dict]:
        """列出 content_dir 下所有 .md 文件"""
        cdir = self.abs_content_dir
        if not cdir.is_dir():
            return []
        posts = []
        for p in sorted(cdir.glob('*.md')):
            stat = p.stat()
            posts.append({
                'name': p.name,
                'path': str(p.relative_to(self.path)),
                'size': stat.st_size,
                'mtime': int(stat.st_mtime),
            })
        return posts

    def list_images(self) -> list[dict]:
        """列出 image_dir 下所有图片（递归扫描子目录）"""
        idir = self.abs_image_dir
        if not idir.is_dir():
            return []
        exts = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'}
        images = []
        for p in sorted(idir.rglob('*')):
            if not p.is_file():
                continue
            if p.suffix.lower() not in exts:
                continue
            stat = p.stat()
            images.append({
                'name': p.name,
                'path': str(p.relative_to(self.path)).replace('\\', '/'),
                'size': stat.st_size,
                'mtime': int(stat.st_mtime),
                'ext': p.suffix.lower(),
            })
        return images


# ───────────────────────────── BlogManager ─────────────────────────────
SKIP_DIRS = {
    '.git', '.hg', '.svn', '.idea', '.vscode', '__pycache__',
    'node_modules', '.cache', '.local',
}


class BlogManager:
    """
    扫描编辑器同级目录下的所有博客仓库，并提供管理操作。
    """

    def __init__(self, editor_dir: Optional[Path] = None):
        self.editor_dir = (editor_dir or Path(__file__).resolve().parent).resolve()
        self.parent_dir = self.editor_dir.parent
        self.sibling_dirs = self._scan_siblings()
        self.current_blog: Optional[Blog] = None

    def _scan_siblings(self) -> list[Path]:
        """返回编辑器的所有兄弟目录（过滤掉隐藏/无关）"""
        dirs = []
        for entry in self.parent_dir.iterdir():
            if not entry.is_dir():
                continue
            if entry == self.editor_dir:
                continue
            if entry.name.startswith('.'):
                continue
            if entry.name in SKIP_DIRS:
                continue
            dirs.append(entry)
        return sorted(dirs, key=lambda p: p.name.lower())

    # ── 发现 ──
    def discover_blogs(self) -> list[Blog]:
        """扫描同级目录，找到所有带 .blog.yaml 的（每次调用都重新扫描）"""
        # 每次重新扫描，因为用户可能随时 clone 新仓库或删除旧仓库
        self.sibling_dirs = self._scan_siblings()
        blogs = []
        for d in self.sibling_dirs:
            yaml_path = d / '.blog.yaml'
            if yaml_path.is_file():
                try:
                    blogs.append(Blog.from_yaml(yaml_path, path=d))
                except Exception:
                    # 解析失败就跳过，不影响其他
                    pass
        return sorted(blogs, key=lambda b: b.blog_name.lower())

    # ── 创建 ──
    def create_blog(
        self,
        dir_name: str,
        blog_name: str,
        repo_url: str = '',
    ) -> Blog:
        """
        向同级目录下一个已存在的空 git 仓库写入模板文件。
        目标目录必须已存在且含 .git。
        """
        target = self.parent_dir / dir_name
        if not target.is_dir():
            raise FileNotFoundError(f'目录不存在: {target}')
        if not (target / '.git').is_dir():
            raise RuntimeError(f'目录不是 git 仓库（请先 git clone）: {target}')

        blog = Blog(
            blog_name=blog_name,
            path=target,
            repo_url=repo_url,
            pages_url=derive_pages_url(repo_url),
        )

        # 写入模板
        self._write_templates(blog)
        return blog

    def _write_templates(self, blog: Blog) -> None:
        """向博客仓库写入初始模板文件"""
        # .blog.yaml — 用 Blog.to_yaml 写
        blog.write_yaml()

        # 创建目录
        blog.abs_content_dir.mkdir(parents=True, exist_ok=True)
        blog.abs_image_dir.mkdir(parents=True, exist_ok=True)

        # Git 不跟踪空目录 — 塞 .gitkeep 占位
        posts_keep = blog.abs_content_dir / '.gitkeep'
        if not posts_keep.is_file():
            posts_keep.write_text('', encoding='utf-8')
        images_keep = blog.abs_image_dir / '.gitkeep'
        if not images_keep.is_file():
            images_keep.write_text('', encoding='utf-8')

        # md/index.md — 博客网站首页（由 site_builder 渲染成 html/index.html）
        # README.md 只做仓库介绍，不再承担首页职责
        blog.write_index_md()

        # .nojekyll — 告诉 GitHub Pages 跳过 Jekyll
        nojekyll = blog.path / '.nojekyll'
        if not nojekyll.is_file():
            nojekyll.write_text('', encoding='utf-8')

        # .gitignore
        gitignore = blog.path / '.gitignore'
        if not gitignore.is_file():
            gitignore.write_text(
                '.DS_Store\n*.swp\n',
                encoding='utf-8'
            )

        # README.md — 记录博客网站的实际首页链接
        blog.write_readme()

    # ── Git 操作 ──
    def git(self, blog: Blog, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """在博客仓库里执行 git 命令"""
        cmd = ['git', '-C', str(blog.path), *args]
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def git_pull(self, blog: Blog) -> dict:
        r = self.git(blog, 'pull', check=False)
        return {'ok': r.returncode == 0, 'stdout': r.stdout, 'stderr': r.stderr}

    def git_push(self, blog: Blog, message: str = 'update') -> dict:
        # add all → commit (only if has changes) → push
        r_add = self.git(blog, 'add', '.', check=False)
        r_status = self.git(blog, 'status', '--porcelain', check=False)
        if r_status.stdout.strip():
            r_commit = self.git(blog, 'commit', '-m', message, check=False)
        else:
            r_commit = subprocess.CompletedProcess(args=[], returncode=0, stdout='(nothing to commit)', stderr='')
        r_push = self.git(blog, 'push', check=False)
        return {
            'ok': r_push.returncode == 0,
            'add_ok': r_add.returncode == 0,
            'commit_ok': r_commit.returncode == 0,
            'commit_stdout': r_commit.stdout,
            'push_stdout': r_push.stdout,
            'push_stderr': r_push.stderr,
        }


# ───────────────────────────── CLI 入口（方便快速验证） ─────────────────────────────
if __name__ == '__main__':
    import json
    bm = BlogManager()
    blogs = bm.discover_blogs()
    print(f'编辑器: {bm.editor_dir}')
    print(f'父目录: {bm.parent_dir}')
    print(f'兄弟目录: {[d.name for d in bm.sibling_dirs]}')
    print(f'发现博客: {len(blogs)}')
    for b in blogs:
        print(f'  - {b.blog_name} → {b.path}')
        for p in b.list_posts():
            print(f'    📄 {p["name"]}')
