#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Blog Editor — 本地 Web 编辑器服务端（仅标准库，零依赖）

提供:
  - static/ 静态页面服务
  - API: 博客发现 / 创建 / 文章读写 / git 同步
  - API: 图片库 / 图片上传
  - API: front matter 提取与更新
"""
import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

from blog_manager import BlogManager, Blog
from site_builder import build_blog_site


STATIC_DIR = Path(__file__).resolve().parent / 'static'
TEMPLATES_DIR = Path(__file__).resolve().parent / 'templates'


MIME = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.md': 'text/markdown; charset=utf-8',
    '.yml': 'text/yaml; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
    '.woff2': 'font/woff2',
    '.map': 'application/json; charset=utf-8',
}

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'}


def parse_front_matter(content: str) -> tuple[dict, str]:
    """从 Markdown 内容里提取 front matter (---...---)，返回 (metadata, body)"""
    if not content.startswith('---'):
        return {}, content
    # 找第二个 ---
    end = content.find('\n---', 3)
    if end == -1:
        return {}, content
    yaml_block = content[4:end].strip()
    body = content[end + 4:].lstrip('\n')
    metadata = _parse_simple_yaml(yaml_block)
    return metadata, body


def _parse_simple_yaml(text: str) -> dict:
    """极简 YAML 解析（复用 blog_manager 逻辑但独立一份避免循环导入）"""
    result = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith('#'):
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$', line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        if val.startswith('[') and val.endswith(']'):
            inner = val[1:-1].strip()
            val = [v.strip().strip('"').strip("'") for v in inner.split(',')] if inner else []
        elif val == '' or val.lower() == 'null':
            val = None
        result[key] = val
    return result


def update_front_matter(content: str, metadata: dict) -> str:
    """用新的 metadata 替换 Markdown 里的 front matter"""
    _, body = parse_front_matter(content)
    lines = ['---']
    for k, v in metadata.items():
        if v is None:
            lines.append(f'{k}:')
        elif isinstance(v, list):
            lines.append(f'{k}: [{", ".join(str(x) for x in v)}]')
        elif isinstance(v, str) and (':' in v or v.startswith(' ')):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f'{k}: {v}')
    lines.append('---')
    lines.append('')
    return '\n'.join(lines) + body


class Handler(BaseHTTPRequestHandler):
    server_version = 'BlogEditor/0.2'

    def __init__(self, *args, **kwargs):
        self.blog_manager = kwargs.pop('blog_manager')
        super().__init__(*args, **kwargs)

    def log_message(self, fmt, *args):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body: bytes, ct: str):
        self.send_response(200)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(n) if n else b''

    def read_text(self):
        data = self.read_body()
        try:
            return data.decode('utf-8')
        except Exception:
            return data.decode('utf-8', errors='replace')

    def send_static(self, rel):
        base = STATIC_DIR
        target = (base / rel).resolve()
        if not str(target).startswith(str(base.resolve())) or not target.is_file():
            self.send_json({'error': 'not found'}, 404)
            return
        self.send_bytes(target.read_bytes(), MIME.get(target.suffix.lower(), 'application/octet-stream'))

    # ── 路径安全 ──
    def _blog_resolve(self, blog_name: str, rel: str) -> tuple[Blog | None, Path | None]:
        blog = self._find_blog(blog_name)
        if blog is None:
            return None, None
        fp = (blog.path / rel).resolve()
        if not str(fp).startswith(str(blog.path.resolve())):
            return blog, None
        return blog, fp

    # ── GET ──
    def do_GET(self):
        u = urlparse(self.path)
        path = u.path

        # 静态
        if path == '/' or path == '/index.html':
            return self.send_static('index.html')
        if path.startswith('/static/'):
            return self.send_static(path[len('/static/'):])

        # /api/blogs
        if path == '/api/blogs':
            blogs = self.blog_manager.discover_blogs()
            return self.send_json({
                'blogs': [
                    {
                        'name': b.blog_name,
                        'dir': b.path.name,
                        'path': str(b.path),
                        'repo_url': b.repo_url,
                        'content_dir': b.content_dir,
                        'image_dir': b.image_dir,
                        'post_count': len(b.list_posts()),
                    }
                    for b in blogs
                ],
                'parent_dir': str(self.blog_manager.parent_dir),
            })

        # /api/info
        if path == '/api/info':
            return self.send_json({
                'editor_dir': str(self.blog_manager.editor_dir),
                'parent_dir': str(self.blog_manager.parent_dir),
            })

        # /api/blog/<name>/posts
        m = re.match(r'^/api/blog/([^/]+)/posts$', path)
        if m:
            blog = self._find_blog(unquote(m.group(1)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            return self.send_json({'posts': blog.list_posts(), 'blog': blog.blog_name})

        # /api/blog/<name>/post/<rel>
        m = re.match(r'^/api/blog/([^/]+)/post/(.+)$', path)
        if m:
            blog, fp = self._blog_resolve(unquote(m.group(1)), unquote(m.group(2)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            if fp is None or not fp.is_file():
                return self.send_json({'error': '文件不存在'}, 404)
            content = fp.read_text(encoding='utf-8')
            metadata, body = parse_front_matter(content)
            return self.send_json({
                'content': content,
                'name': fp.name,
                'path': str(fp.relative_to(blog.path)),
                'metadata': metadata,
                'body': body,
            })

        # /api/blog/<name>/images — 列出图片
        m = re.match(r'^/api/blog/([^/]+)/images$', path)
        if m:
            blog = self._find_blog(unquote(m.group(1)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            return self.send_json({'images': blog.list_images(), 'blog': blog.blog_name})

        # /api/blog/<name>/image/<rel> — 直接渲染图片（预览用）
        m = re.match(r'^/api/blog/([^/]+)/image/(.+)$', path)
        if m:
            blog, fp = self._blog_resolve(unquote(m.group(1)), unquote(m.group(2)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            if fp is None or not fp.is_file():
                return self.send_json({'error': '文件不存在'}, 404)
            return self.send_bytes(fp.read_bytes(), MIME.get(fp.suffix.lower(), 'application/octet-stream'))

        return self.send_json({'error': 'unknown api'}, 404)

    # ── PUT ──
    def do_PUT(self):
        u = urlparse(self.path)

        # /api/blog/<name>/post/<rel> — 保存文章
        m = re.match(r'^/api/blog/([^/]+)/post/(.+)$', u.path)
        if m:
            blog, fp = self._blog_resolve(unquote(m.group(1)), unquote(m.group(2)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            if fp is None:
                return self.send_json({'error': '路径越界'}, 403)
            data = self.read_body()
            try:
                payload = json.loads(data)
                content = payload.get('content', '')
            except Exception:
                content = data.decode('utf-8', errors='replace')
            if '\x00' in content:
                return self.send_json({'error': '非法内容'}, 400)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding='utf-8')
            return self.send_json({'ok': True, 'size': fp.stat().st_size})

        # /api/blog/<name>/frontmatter/<rel> — 更新 front matter
        m = re.match(r'^/api/blog/([^/]+)/frontmatter/(.+)$', u.path)
        if m:
            blog, fp = self._blog_resolve(unquote(m.group(1)), unquote(m.group(2)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            if fp is None or not fp.is_file():
                return self.send_json({'error': '文件不存在'}, 404)
            data = self.read_body()
            try:
                metadata = json.loads(data)
            except Exception:
                return self.send_json({'error': '无效 JSON'}, 400)
            content = fp.read_text(encoding='utf-8')
            new_content = update_front_matter(content, metadata)
            fp.write_text(new_content, encoding='utf-8')
            return self.send_json({'ok': True})

        return self.send_json({'error': 'forbidden'}, 403)

    # ── POST ──
    def do_POST(self):
        u = urlparse(self.path)
        body = self.read_text()

        # 创建博客
        if u.path == '/api/create-blog':
            try:
                data = json.loads(body)
            except Exception:
                return self.send_json({'error': '无效 JSON'}, 400)
            dir_name = data.get('dir_name', '').strip()
            blog_name = data.get('blog_name', '').strip() or dir_name
            repo_url = data.get('repo_url', '').strip()
            if not dir_name:
                return self.send_json({'error': '缺少 dir_name'}, 400)
            try:
                blog = self.blog_manager.create_blog(dir_name, blog_name, repo_url)
            except FileNotFoundError as e:
                return self.send_json({'error': str(e)}, 404)
            except RuntimeError as e:
                return self.send_json({'error': str(e)}, 400)
            return self.send_json({'ok': True, 'blog': blog.blog_name, 'path': str(blog.path)})

        # 生成静态站点（GitHub Pages 用）
        m = re.match(r'^/api/blog/([^/]+)/build$', u.path)
        if m:
            blog = self._find_blog(unquote(m.group(1)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            try:
                return self.send_json(build_blog_site(blog))
            except OSError as e:
                return self.send_json({'error': str(e)}, 500)

        # git pull
        m = re.match(r'^/api/blog/([^/]+)/pull$', u.path)
        if m:
            blog = self._find_blog(unquote(m.group(1)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            return self.send_json(self.blog_manager.git_pull(blog))

        # git push
        m = re.match(r'^/api/blog/([^/]+)/push$', u.path)
        if m:
            blog = self._find_blog(unquote(m.group(1)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            msg = 'update'
            try:
                msg = json.loads(body).get('message', 'update')
            except Exception:
                pass
            return self.send_json(self.blog_manager.git_push(blog, message=msg or 'update'))

        # 新建文章
        m = re.match(r'^/api/blog/([^/]+)/new-post$', u.path)
        if m:
            blog = self._find_blog(unquote(m.group(1)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            import datetime
            title = data.get('title', '新文章')
            slug = (data.get('slug') or '').strip() or re.sub(r'[^A-Za-z0-9\u4e00-\u9fff-]+', '-', title).strip('-').lower() or 'post'
            date_str = data.get('date') or datetime.datetime.now().strftime('%Y-%m-%d')
            tags = data.get('tags', [])
            fname = f'{date_str}-{slug}.md'
            fp = blog.abs_content_dir / fname
            if fp.is_file():
                return self.send_json({'error': '文件已存在'}, 409)
            frontmatter = update_front_matter(f'# {title}\n\n正文内容...\n', {
                'title': title,
                'date': date_str,
                'tags': tags if isinstance(tags, list) else [tags] if tags else [],
            })
            blog.abs_content_dir.mkdir(parents=True, exist_ok=True)
            fp.write_text(frontmatter, encoding='utf-8')
            return self.send_json({'ok': True, 'path': str(fp.relative_to(blog.path))})

        # 上传图片 (multipart 不方便，用 base64 JSON)
        m = re.match(r'^/api/blog/([^/]+)/upload-image$', u.path)
        if m:
            blog = self._find_blog(unquote(m.group(1)))
            if blog is None:
                return self.send_json({'error': '博客不存在'}, 404)
            try:
                data = json.loads(body)
            except Exception:
                return self.send_json({'error': '无效 JSON'}, 400)
            filename = (data.get('filename') or 'image.png').strip()
            base64_data = data.get('data', '')
            if not filename or not base64_data:
                return self.send_json({'error': '缺少 filename 或 data'}, 400)
            # 安全: 只允许图片扩展名
            ext = Path(filename).suffix.lower()
            if ext not in IMAGE_EXTS:
                return self.send_json({'error': '不支持的文件类型'}, 400)
            # 安全: 禁止路径穿越
            if '/' in filename or '\\' in filename or '..' in filename:
                return self.send_json({'error': '非法文件名'}, 400)
            try:
                raw = base64.b64decode(base64_data)
            except Exception:
                return self.send_json({'error': '无效 base64'}, 400)
            blog.abs_image_dir.mkdir(parents=True, exist_ok=True)
            # 如果同名，加后缀
            target = blog.abs_image_dir / filename
            n = 1
            while target.is_file():
                target = blog.abs_image_dir / f'{Path(filename).stem}-{n}{ext}'
                n += 1
            target.write_bytes(raw)
            rel = str(target.relative_to(blog.path)).replace('\\', '/')
            return self.send_json({'ok': True, 'path': rel, 'size': len(raw)})

        return self.send_json({'error': 'unknown api'}, 404)

    # ── 辅助 ──
    def _find_blog(self, name: str) -> Blog | None:
        for b in self.blog_manager.discover_blogs():
            if b.blog_name == name or b.path.name == name:
                return b
        return None


def main():
    ap = argparse.ArgumentParser(description='Blog Editor — 本地 Web 编辑器')
    ap.add_argument('--port', type=int, default=9176)
    args = ap.parse_args()

    bm = BlogManager()
    handler = lambda *a, **kw: Handler(*a, blog_manager=bm, **kw)

    # SO_REUSEADDR: 避免重启时 TIME_WAIT 占用端口
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    print(f'[blog-editor] 已启动: http://127.0.0.1:{args.port}/')
    print(f'[blog-editor] 父目录: {bm.parent_dir}')
    blogs = bm.discover_blogs()
    if blogs:
        print(f'[blog-editor] 发现 {len(blogs)} 个博客:')
        for b in blogs:
            print(f'  • {b.blog_name} → {b.path}')
    else:
        print(f'[blog-editor] 暂未发现博客 — 在同级目录下创建带 .blog.yaml 的 git 仓库即可')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n[blog-editor] 已停止')


if __name__ == '__main__':
    main()
