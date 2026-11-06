# Blog Editor 开发计划

> 最后更新: 2026-11-06
> 状态: 设计冻结，待开工

## 一、项目定位

一个 Python 本地 Web 编辑器，用于管理多个独立的 Markdown 博客仓库，每个博客部署在 GitHub Pages。

**核心约束**:
- 编辑器与博客仓库是**同级目录**（同一个父目录下的兄弟目录）
- 用户自己在 GitHub 创建仓库并 `git clone`，编辑器只负责写入模板文件、扫描发现、编辑、同步
- 编辑器是独立项目，不与任何博客仓库混放

---

## 二、完整目录结构

```
~/workspace/                          ← 父目录（任意位置）
│
├── wiki-on-github/                   ← 编辑器（本项目）
│   ├── server.py                     ← Python http.server，标准库零依赖
│   ├── blog_manager.py               ← 同级扫描 / 创建博客 / 切换 / git 操作
│   ├── site_builder.py               ← md → html 转换（GitHub Pages）
│   ├── tools/
│   │   └── dw_import.py              ← DokuWiki 数据目录 → Markdown 导入
│   ├── templates/
│   │   ├── .blog.yaml                ← 标识文件模板
│   │   ├── post.md                   ← 新文章模板（含 front matter）
│   │   ├── .gitignore
│   │   └── .nojekyll
│   ├── static/
│   │   ├── index.html                ← Web 界面（三栏布局）
│   │   ├── app.js                    ← 前端逻辑
│   │   ├── style.css
│   │   └── vendor/
│   │       ├── codemirror.min.js     ← 代码编辑器
│   │       ├── codemirror.min.css
│   │       ├── markdown.min.js        ← CodeMirror Markdown mode
│   │       └── marked.min.js          ← Markdown 实时预览
│   ├── devdocs/                      ← 本目录
│   └── agent.md
│
├── travel-blog/                      ← 博客 A（用户自己 clone 的）
│   ├── README.md                     ← 仓库介绍（基本信息 + 跳 md/index.md 的链接）
│   ├── .blog.yaml                    ← 编辑器写入的标识文件
│   ├── index.html                    ← 重定向页（→ html/index.html）
│   ├── .nojekyll                     ← 禁用 Jekyll
│   ├── md/                           ← 所有文章 .md（含 index.md 首页）
│   ├── html/                         ← site_builder 转换产物（含 index.html）
│   └── images/
│
├── food-blog/                        ← 博客 B
└── tech-notes/                       ← 博客 C
```

---

## 三、博客仓库规范

### 3.1 `.blog.yaml` 标识文件（格式冻结）

```yaml
schema_version: 1
blog_name: 旅行笔记
description: 我的旅行记录
repo_url: https://github.com/xxx/travel-blog
repo_branch: main
content_dir: md/
image_dir: images/
pages_url: https://xxx.github.io/travel-blog
```

### 3.2 Markdown 文章规范

所有文章放在 `md/` 目录下，文件名推荐 `YYYY-MM-DD-slug.md`，必须带 front matter:

```markdown
---
title: 2025 年北海道行记
date: 2025-01-15
tags: [旅行, 日本, 北海道]
---

# 第一天：札幌

正文内容...

![小樽夜景](./images/otaru-night.jpg)
```

### 3.3 目录约定

| 路径 | 说明 |
|------|------|
| `.blog.yaml` | 标识文件，编辑器靠它识别博客 |
| `README.md` | 仓库说明，含博客首页可点击链接 |
| `md/` | 所有 Markdown 文章（编辑器只改这里） |
| `html/` | 转换产物：`<文章名>.html` + `assets/site.css` |
| `index.html` | 转换生成的首页（根部唯一网页） |
| `images/` | 图片，md 与 html 里都用 `../images/xxx.jpg` 引用 |
| `.nojekyll` | 空文件，告诉 GitHub Pages 跳过 Jekyll |

---

## 四、blog_manager.py 核心逻辑

```python
class BlogManager:
    def __init__(self):
        self.editor_dir = Path(__file__).resolve().parent
        # 同级兄弟目录 = 所有可能是博客的目录
        self.sibling_dirs = [
            d for d in self.editor_dir.parent.iterdir()
            if d.is_dir() and d != self.editor_dir
            and not d.name.startswith('.')
        ]

    def discover_blogs(self) -> list[Blog]:
        """扫描同级目录，找到所有有 .blog.yaml 的"""
        blogs = []
        for d in self.sibling_dirs:
            yaml_path = d / ".blog.yaml"
            if yaml_path.is_file():
                blogs.append(Blog.from_yaml(yaml_path, path=d))
        return sorted(blogs, key=lambda b: b.blog_name.lower())

    def create_blog(self, dir_name, blog_name, repo_url):
        """向同级目录下的空 git 仓库写入模板文件"""
        target = self.editor_dir.parent / dir_name
        assert target.is_dir() and (target / ".git").is_dir(), \
            f"目标目录 {target} 不存在或不是 git 仓库"
        # 写入 .blog.yaml / README.md / md/ / images/ / .gitignore / .nojekyll

    def git_pull(self, blog):
        subprocess.run(["git", "-C", str(blog.path), "pull"])

    def git_push(self, blog):
        subprocess.run(["git", "-C", str(blog.path), "add", "."])
        subprocess.run(["git", "-C", str(blog.path), "commit", "-m", "update"])
        subprocess.run(["git", "-C", str(blog.path), "push"])
```

---

## 五、Web 界面设计（参考 naiz-studio 模式）

复用 `/home/edo/naiz-studio` 的技术栈:
- 后端: `http.server.ThreadingHTTPServer`（Python 标准库，零依赖）
- 前端: CodeMirror + marked.js（本地 vendor，无需构建）

### 5.1 三栏布局

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📝 Blog Editor                                                      │
│ [博客: 旅行笔记 ▼]  [+ 创建博客]   [保存] [Pull] [Push]             │
├─────────────┬────────────────────────────────────────────────────────┤
│ 文章列表     │           CodeMirror Markdown 编辑器                  │
│             │  （右 Tab: 编辑 / 实时预览 via marked.js）              │
│ 📄 md/   │                                                        │
│ 🖼 images/  │                                                        │
│ [+ 新建]    │                                                        │
│             │                                                        │
├─────────────┴────────────────────────────────────────────────────────┤
│ 就绪 | 博客: travel-blog | 分支: main | 未保存: 0                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 与 naiz-studio 的差异

| naiz-studio | blog-editor | 原因 |
|-------------|-------------|------|
| 项目切换（扫描 ROOT/projects） | 博客切换（扫描同级兄弟目录） | 数据源不同 |
| 构建/打包/启动任务 | Git Pull/Push 按钮 | 博客不需要编译 |
| 素材预览面板 | Markdown 图片通过 marked.js 直接渲染 | 简化 |
| 无创建按钮 | + 创建博客（写入模板） | 核心功能 |

### 5.3 后端 API 路由

```
GET  /api/blogs              → discover_blogs()
GET  /api/blog/{name}/posts  → 列出该博客的 md/*.md
GET  /api/post/{name}        → 读取 .md 内容
PUT  /api/post/{name}        → 保存 .md 内容
POST /api/create-blog        → 写入模板文件
POST /api/git/pull/{name}    → subprocess git pull
POST /api/git/push/{name}    → subprocess git add/commit/push
POST /api/new-post/{name}    → 在 md/ 下生成带 front matter 的 .md
```

---

## 六、GitHub Pages 渲染方案

**选择: `.nojekyll` + 编辑器侧预生成 HTML（`site_builder.py`）**

- 在博客仓库根目录放一个空的 `.nojekyll` 文件
- GitHub Pages 只做文件托管，不触发 Jekyll 构建
- 编辑器把 `md/*.md` 转换成 `html/*.html`，并生成根部 `index.html` 列表页
- 优点: 零依赖、纯静态、本地与线上完全一致；缺点是每次改文章要点一次「转换为网页」

---

## 七、开发里程碑

### M1: 骨架跑通
- [x] `server.py` 启动，浏览器能打开界面
- [x] `blog_manager.py` 的 `discover_blogs()` 能扫到同级博客
- [x] 顶部下拉显示扫描到的博客列表
- [x] 切换下拉 → 文章列表联动

### M2: 创建博客 + 编辑 + 预览
- [x] [+ 创建博客] 按钮 → 弹窗 → 写入模板文件（含 README 首页链接）
- [x] CodeMirror 编辑器（Markdown mode）
- [x] marked.js 右侧实时预览
- [x] 保存按钮 → 写回 .md 文件

### M3: Git 同步 + 新文章
- [x] Pull / Push 按钮（subprocess 调 git）
- [x] 新建文章按钮 → 生成带 front matter 的 .md
- [x] 脏标记（未保存提醒）

### M4: dw_to_md 迁移工具（独立，不阻塞主流程）
- [x] 转换器（`tools/dw_import.py`，覆盖常见 DokuWiki 语法）
- [x] 媒体文件搬运: `data/media/` → `blog/images/`
- [ ] XML-RPC 远程入口（当前只支持直接读 data/ 目录）

### M5: 静态站点生成（GitHub Pages）
- [x] `site_builder.py` 把 md/*.md 渲染成 index.html + html/<文章>.html + html/assets/site.css
- [x] 站内 .md 链接改写为 .html，中文路径 URL 编码
- [x] 前端「转换为网页」按钮 + `POST /api/blog/<name>/build`
- [ ] 分页 / 标签归档页 / RSS（按需再做）

---

## 八、技术选型

| 组件 | 选择 | 原因 |
|------|------|------|
| 后端 | Python `http.server` 标准库 | 零依赖，启动即用 |
| 前端编辑器 | CodeMirror 5 | naiz-studio 已在用，稳定 |
| Markdown 渲染 | marked.js | 轻量，实时预览够用 |
| YAML 解析 | Python `yaml` 或手写简单解析器 | `.blog.yaml` 格式固定，极简 |
| Git 操作 | subprocess 调用本地 `git` | 简单直接，无需 API |
| DokuWiki 迁移 | 自己写正则转换器 | 无现成 Python 库 |
