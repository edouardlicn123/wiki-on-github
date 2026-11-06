# agent.md — Blog Editor 项目上下文件

> 给 AI agent 的项目工作指南。每次开始任务前先读取本文件。

## 项目目标

Python 本地 Web 编辑器，管理多个独立 Markdown 博客仓库（每个部署到 GitHub Pages）。

## 仓库位置

```
/home/edo/wiki-on-github/     ← 本项目（编辑器）
```

**编辑器与博客仓库必须同级** — 都在同一个父目录下，编辑器启动时扫描兄弟目录来发现博客。

## 关键约束

1. **零第三方依赖（后端）** — 只用 Python 标准库，`http.server.ThreadingHTTPServer`
2. **前端 vendor 本地化** — CodeMirror、marked.js 等 JS 库下载到 `static/vendor/`，不通过 CDN
3. **博客仓库标识文件 `.blog.yaml`** — 编辑器靠这个文件识别目录是不是博客
4. **用户自己操作 GitHub** — clone、push/pull 走本地 git 命令（subprocess），不写 GitHub API 集成
5. **不自动创建 git 仓库** — 只往已 clone 好的空仓库里写模板文件

## 目录规范

```
wiki-on-github/
├── server.py              ← HTTP 服务入口
├── server_manager.py      ← 启停/状态管理（start/stop/restart/status）
├── blog_manager.py        ← 核心类: 扫描 / 创建 / git 同步
├── site_builder.py        ← 静态站点生成（md → HTML，GitHub Pages 托管）
├── start.sh / .bat / .ps1 ← 三平台启动入口（菜单 + 命令分发）
├── tools/                 ← 独立命令行工具（不参与 server 运行时）
│   └── dw_import.py       ← DokuWiki 数据目录 → Markdown 导入器
├── templates/             ← 博客模板文件
│   ├── .blog.yaml
│   ├── index.md
│   ├── post.md
│   ├── .gitignore
│   └── .nojekyll
├── static/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── i18n.js            ← 中英文切换
│   └── vendor/            ← CodeMirror + marked.js 等
└── devdocs/
    └── plan.md            ← 完整开发计划
```

**约定**：所有离线命令行工具一律放 `tools/`，以 `python3 tools/xxx.py` 方式运行；工具可 `sys.path.insert(0, 项目根)` 复用 `blog_manager`。

## 内置工具 (tools/)

### tools/dw_import.py — DokuWiki → Markdown 导入

把 DokuWiki 的 `data/` 目录整批转成 Markdown 文章，写入目标博客仓库的 `content_dir`。
不依赖运行中的 DokuWiki，直接读 `data/pages/**/*.txt` 与 `data/meta/**/*.changes`。

```bash
python3 tools/dw_import.py <dokuwiki_data目录> <博客目录> [选项]

选项:
  --dry-run            只统计不写文件
  --force              覆盖已存在的 md
  --include-defaults   连 wiki:/playground: 命名空间一起导入（默认跳过）
```

行为要点（改动此工具时必须保持）：

- 磁盘上的页面文件名是 **URL 编码** 的（`%E4%B8%AD%E6%96%87.txt`），读取前必须 `urllib.parse.unquote`
- 转换前先把 `<code>` / `<html>` / `<php>` / `<nowiki>` 抽成占位符，再做行级与行内替换，最后还原；否则代码内容会被样式规则误伤
- 内部链接 `[[页面名]]` 用 cleanID 规则（小写 + 特殊字符折叠为 `_`）匹配，匹配不到再用 loose key 兜底；仍未命中的只保留文字并计入「未解析链接」报告
- `date` 取 `meta/*.changes` 最早时间戳（不是文件 mtime）；`tags` 从 `start.txt` 分类段落继承
- Git 不跟踪空目录：`md/`、`images/` 里必须留 `.gitkeep`

## 博客仓库布局

所有博客仓库统一为下面结构。**README.md 与博客首页彻底解耦**——README 只做 GitHub 仓库介绍，博客首页独立为 `md/index.md`（Markdown 源文件）+ `html/index.html`（site_builder 渲染后的静态页）。

```
blog-repo/
├── README.md          ← 仓库介绍（基本信息 + 跳 md/index.md 的链接）
├── .blog.yaml         ← 标识文件
├── .nojekyll          ← 关闭 Jekyll，Pages 直接按静态文件服务
├── index.html         ← 重定向页（meta refresh + JS）→ html/index.html
├── md/                ← 所有文章 .md（编辑器只改这里）
│   ├── index.md       ← 博客网站首页（带 front matter + 成对边界列表）
│   ├── .gitkeep
│   └── *.md
├── html/              ← site_builder 转换产物
│   ├── index.html     ← 博客首页（由 md/index.md 渲染）
│   ├── *.html
│   └── assets/site.css
└── images/            ← 图片
```

### 图片引用约定

| md 写的 | 谁写的 | 从哪渲染 | 正确基准 |
|---|---|---|---|
| `../images/x.png` | 作者写文章 | html/*.html（在 html/ 下） | ✅ html/ 往上一层 = images/ |
| `../images/x.png` | 作者写 index.md | 直接在 md/index.md 里看（GitHub 渲染） | ❌ 根目录往上一层不存在 |

**site_builder 渲染 `md/index.md`（成 html/index.html，都在 html/ 下）** 时，图片基准统一了，所以作者写文章和写 index.md 里图片都用 `../images/xxx.png` 就行。

### 内部链接约定

所有 `.md` 内部链接**一律写 `.md` 结尾**，不要写 `.html`。site_builder 渲染时会自动改写：
- md/index.md 里写 `[obs](./obs杂项问题解决.md)` → site_builder 渲染成 `obs杂项问题解决.html`
- 文章之间同理。推荐写法：`[目标](./目标文件名.md)`（都在 md/ 同目录）

### md/index.md 动态区块

site_builder 往 `md/index.md` 里注入/替换文章列表时，用**成对边界注释**包住，保证循环构建不产生重复：

```markdown
## 最近文章

<!-- site_builder:start -->

- **2025-05-27**  [obs杂项问题解决](obs杂项问题解决.md) `其它`
- **2025-04-24**  [git代理方案](git代理方案.md) `其它`
<!-- site_builder:end -->
```

**site_builder 每次构建做三件事**：
1. 读 md/index.md → 用正则替换边界之间内容为最新 Markdown 列表
2. 渲染成 html/index.html（`render_markdown(body)` 会把 `.md` 链接自动改 `.html`）
3. **回写 md/index.md** —— 让源文件本身在 GitHub 上打开也能直接看到完整列表（零 JS）

**边界注释内的内容不要手动编辑**，下次 site_builder 会整体替换。但**边界之外的正文**（标题、欢迎语、自定义段落）作者可以自由修改，不会被覆盖。

### DokuWiki 迁移的对应关系

| DokuWiki | 落点 |
|---|---|
| `start.txt`（站点首页） | `md/index.md`（带边界注释） |
| 其他 `xxx.txt` | `md/xxx.md` |
| `data/media/**` | `images/` |

## 站点生成 (site_builder.py)

```
md/index.md   →  html/index.html（+ 回写 md/index.md 注入最新列表）
md/*.md       →  html/*.html
               +  html/assets/site.css
               +  仓库根 index.html（重定向到 html/index.html）
```

- CLI：`python3 site_builder.py <博客目录>`
- API：`POST /api/blog/<博客名>/build`，前端顶部「转换为网页」按钮触发
- 渲染器只覆盖项目产生的 Markdown 子集（标题/代码块/行内代码/粗斜体/链接/图片/列表嵌套/表格/引用/分隔线/段落），**不引入第三方 Markdown 库**
- 站内 `.md` 链接自动改写为 `.html`：`render_inline` / `render_markdown` 接受 `link_prefix` / `image_rebase` 参数，对不同基准目录（根、html/）统一处理
- 自动清理旧布局残留：根目录的旧文章 html、根目录旧 `assets/`、`html/` 中已删除文章的页面
- 仓库根有 `.nojekyll`，Pages 直接按静态文件服务，不做 Jekyll 构建
- `html/index.html` 渲染 `md/index.md`（成对边界之间是最新 Markdown 列表），**仓库根 index.html 只是极简重定向**，避免 Pages 直接渲染 md 文件看到源码

## 关键约束（补充）

- **前端预览兜底**：编辑器打开 md/index.md → marked.js 直接渲染。如果成对边界之间还没有真实列表（首次未跑 site_builder），JS 用当前 state.allPosts 兜底生成一份。有真实列表则什么都不做，让 marked 直接渲染。
- **三个场景统一**：GitHub 仓库界面（GitHub 原生 md 渲染）、编辑器预览（marked.js）、GitHub Pages（site_builder 生成 html），作者只需一份写法：`[x](目标.md)` / `![x](../images/x.png)`

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Python `http.server` 标准库 |
| 前端 | CodeMirror 5（编辑器） + marked.js（MD 渲染） |
| Git | subprocess 调本地 `git` 命令 |
| YAML | 手写极简解析或 `yaml` 库按需引入 |

## 开发参考

- **naiz-studio** (`/home/edo/naiz-studio`) — 本项目直接复用它的 server.py + CodeMirror 前端模式，参考它的 http.server 路由写法
- **DokuWiki 源码** (`/home/edo/Downloads/dokuwiki-2026-07-14c/`) — `tools/dw_import.py` 的语法与存储模型依据（cleanID、`data/pages` 布局、`<code>` 语法）

## 博客仓库模板 (`.blog.yaml`)

```yaml
schema_version: 1
blog_name: 显示名
repo_url: https://github.com/user/repo
repo_branch: main
content_dir: md/
image_dir: images/
pages_url: https://user.github.io/repo
```

## 工作流程

1. 用户在 GitHub 创建仓库 → `git clone` 到编辑器同级目录
2. 编辑器点「创建博客」→ 填入目录名、显示名、repo_url → 写入模板
3. 之后每次启动编辑器，自动扫描同级目录识别所有博客
4. 切换下拉 → 加载该博客文章列表 → 编辑 → 保存 → git push

## 注意事项

- 扫描兄弟目录时要跳过以 `.` 开头的隐藏目录和 `node_modules` 等无关目录
- `.blog.yaml` 里的路径字段都是**相对 repo 根**的
- Markdown 图片引用统一用 `./images/xxx.jpg`
- 编辑器只操作本地 clone，不调用 GitHub API
- **创建博客时自动写 README.md** — `_write_templates()` 调用 `Blog.write_readme()`，把博客网站的实际首页链接（`pages_url`，为空则用 `derive_pages_url(repo_url)` 推导）以可点击形式写进 README
- Pages 地址推导规则：仓库名 `<owner>.github.io` → `https://<owner>.github.io/`；其他仓库 → `https://<owner>.github.io/<repo>/`
