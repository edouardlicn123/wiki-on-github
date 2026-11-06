# wiki-on-github

一个本地运行的 Markdown 博客/Wiki 编辑器，**把多篇独立的博客仓库拉到本地同级目录，一键编辑、一键生成 GitHub Pages 可托管的静态站点**。

核心特点：

- 📝 **三栏编辑器**：文章列表 / Front Matter 元数据 / CodeMirror + marked.js 实时预览
- 🚀 **零依赖后端**：只用 Python 标准库 `http.server`，`python3 start.sh` 就能跑
- 🔧 **自己写的站点生成器**：不引第三方 Markdown 库，循环构建完全幂等
- 🔄 **DokuWiki 一键迁移**：`tools/dw_import.py` 把旧 DokuWiki 数据目录整批转过来
- 🌐 **GitHub Pages 原生部署**：生成的 HTML 直接 push 到仓库就行

---

## 目录

- [准备工作](#准备工作)
- [创建一个新博客仓库（完整流程）](#创建一个新博客仓库完整流程)
  - [第 1 步：在 GitHub 上建仓库](#第-1-步在-github-上建仓库)
  - [第 2 步：clone 到本地](#第-2-步clone-到本地)
  - [第 3 步：在编辑器里初始化](#第-3-步在编辑器里初始化)
  - [第 4 步：启动编辑器](#第-4-步启动编辑器)
  - [第 5 步：写文章](#第-5-步写文章)
  - [第 6 步：生成静态站点](#第-6-步生成静态站点)
  - [第 7 步：push 到 GitHub 并启用 Pages](#第-7-步push-到-github-并启用-pages)
- [迁移已有 DokuWiki 站点](#迁移已有-dokuwiki-站点)
- [作者写作约定](#作者写作约定)
  - [内部链接](#内部链接)
  - [图片引用](#图片引用)
  - [首页动态区块](#首页动态区块)
- [FAQ](#faq)

---

## 准备工作

- Python 3.9+（只需标准库）
- 本地已安装 `git` 并配置好 GitHub SSH key
- 编辑器目录与博客仓库**必须同级**存放（同一个父目录下）

```
/home/edo/
├── wiki-on-github/     ← 本项目（编辑器）
├── techwiki/           ← 博客仓库 1
├── wordswiki/          ← 博客仓库 2
└── ...                 ← 更多博客仓库
```

原因：编辑器启动时扫描同级目录，靠 `.blog.yaml` 识别哪些是博客。

---

## 创建一个新博客仓库（完整流程）

### 第 1 步：在 GitHub 上建仓库

1. 打开 https://github.com/new
2. Repository name 填你的博客名（比如 `myblog`）
3. **不要**勾选 "Add a README file"、".gitignore"、"license" — 保持空仓库
4. 选 Public 或 Private
5. 点 **Create repository**

### 第 2 步：clone 到本地

在**编辑器的父目录**下 clone（上面那个 `/home/edo/`）：

```bash
cd ~    # 或者 cd /home/edo，总之是 wiki-on-github 的上一级
git clone git@github.com:你的用户名/myblog.git
```

clone 下来的目录名必须和 GitHub 仓库名一致（默认就是）。

### 第 3 步：在编辑器里初始化

**两种方式，任选一种。**

#### 方式 A：Web 界面（推荐）

1. 启动编辑器（见下一步）
2. 点顶部博客下拉框 → **「创建博客」**
3. 填三个字段：
   - **目录名**：`myblog`（就是 clone 下来的那个文件夹名）
   - **显示名**：给人看的，比如「我的技术笔记」
   - **仓库 URL**：完整的 HTTPS 或 SSH 地址
4. 点确定 → 编辑器会往空仓库里写入模板文件

#### 方式 B：命令行

```bash
cd wiki-on-github
python3 -c "
from blog_manager import BlogManager
m = BlogManager()
b = m.create_blog(dir_name='myblog', blog_name='我的技术笔记', repo_url='git@github.com:你的用户名/myblog.git')
print('创建完成：', b.path)
"
```

这一步会自动生成：`.blog.yaml` / `md/` / `images/` / `md/index.md` / `.nojekyll` / `.gitignore` / `index.html`（根重定向）/ `README.md` / `.gitkeep`。

### 第 4 步：启动编辑器

```bash
cd wiki-on-github

# Linux / macOS
bash start.sh

# 三个选项：1 启动 / 2 停止 / 3 重启 / 4 查看状态
# 或者直接命令行：
bash start.sh start --port 9176
```

浏览器打开 <http://localhost:9176>。编辑器会自动扫描同级目录，刚创建的博客应该出现在顶部下拉框里。

### 第 5 步：写文章

1. 顶部下拉切到你的博客
2. 文章列表下面点 **「新建文章」**，填标题和日期
3. 开始写 Markdown，Ctrl/Cmd+S 保存
4. 写内部链接用 `[文章名](目标文件名.md)`（带 `.md` 后缀，**不要写 `.html`**）
5. 插图片用 `![描述](../images/图片名.png)`

### 第 6 步：生成静态站点

**写完一批文章后、push 之前，跑一次站点生成器。**

```bash
# 命令行
cd wiki-on-github
python3 site_builder.py ~/myblog

# 或者 Web 界面点顶部「转换为网页」按钮
```

它会做三件事：

1. 读 `md/index.md` → 注入最新文章列表到动态区块
2. `md/*.md` → 渲染成 `html/*.html`（自动把 `.md` 链接改成 `.html`）
3. 回写 `md/index.md`（让 GitHub 上打开也能看到完整列表）

### 第 7 步：push 到 GitHub 并启用 Pages

```bash
cd ~/myblog
git add -A
git commit -m "写了 3 篇新文章"
git push origin main
```

然后在 GitHub 仓库页面：

1. **Settings** → 左侧 **Pages**
2. Source 选 `Deploy from a branch`
3. Branch 选 `main`，文件夹选 **/(root)**（不是 /docs）
4. 点 Save

等一两分钟，浏览器打开 `https://你的用户名.github.io/myblog/` 就能看到博客了。

---

## 迁移已有 DokuWiki 站点

如果你手上有一个跑 DokuWiki 的老站点，编辑器自带导入器：

```bash
cd wiki-on-github

# 1. 先在 GitHub 上建一个新仓库 clone 下来（前面步骤 1-2）
# 2. 在编辑器里初始化模板（步骤 3）

# 3. 跑导入器
python3 tools/dw_import.py \
    /path/to/dokuwiki/data \    # DokuWiki 的 data/ 目录（含 pages/ media/）
    ~/myblog                    # 目标博客仓库

# 4. 生成静态站点
python3 site_builder.py ~/myblog

# 5. push
cd ~/myblog && git add -A && git commit -m "导入 DokuWiki" && git push
```

导入器做了这些事：

| DokuWiki | 落点 |
|---|---|
| `pages/start.txt` | `md/index.md`（自动注入动态区块占位 + 清掉 DokuWiki 原生索引） |
| `pages/**/*.txt` | `md/*.md`（URL 编码文件名自动解码） |
| `data/media/**` | `images/`（子目录扁平化） |
| `meta/*.changes` | 取最早时间戳作为文章 date |

迁移完成后会打印报告：成功多少篇、跳过哪些命名空间、有没有未解析链接、图片源是否齐全。

常用选项：

```bash
python3 tools/dw_import.py <data_dir> <blog_dir> --dry-run    # 只统计不写文件
python3 tools/dw_import.py <data_dir> <blog_dir> --force      # 覆盖已存在的 md
python3 tools/dw_import.py <data_dir> <blog_dir> --include-defaults   # 连 playground 命名空间也导入
```

---

## 作者写作约定

### 内部链接

**一律写 `.md` 结尾**，不要写 `.html`，也不要带目录路径。

```markdown
# ✅ 正确（都在 md/ 同目录下）
[obs 杂项笔记](obs杂项问题解决.md)

# ❌ 不要这样
[obs 杂项笔记](obs杂项问题解决.html)
[obs 杂项笔记](./obs杂项问题解决.md)
[obs 杂项笔记](md/obs杂项问题解决.md)
```

site_builder 渲染时自动把所有 `.md` 改成 `.html`，所以：
- 在 GitHub 上打开 md 文件 → 链接是 `.md` → GitHub 原生渲染正常
- 在 Pages 上打开 html 文件 → 链接是 `.html` → Pages 正常跳转
- 编辑器预览 → marked.js 直接按 `.md` 渲染 → 预览区拦截点击切回编辑器

**一份写法，三个场景通吃。**

### 图片引用

```markdown
![描述](../images/我的图片.png)
```

统一用 `../images/` 前缀。原因：HTML 渲染产物在 `html/` 子目录下，往上一层就是 `images/`。

### 首页动态区块

`md/index.md` 里有一段这样的结构：

```markdown
## 最近文章

<!-- site_builder:start 以下列表由 site_builder 自动生成，不要手动编辑 -->

- **2025-05-27**  [obs杂项问题解决](obs杂项问题解决.md) `其它`
- **2025-04-24**  [git代理方案](git代理方案.md) `其它`

<!-- site_builder:end -->

## 你自己的区块

这里想写什么写什么，不会被覆盖。
```

**规则很简单**：

- `<!-- site_builder:start -->` 和 `<!-- site_builder:end -->` 之间的内容 → site_builder 每次构建**整体替换**，不要手动编辑
- 边界之外的正文（欢迎语、自定义区块、友情链接）→ 自由修改，永远不会被覆盖

每次构建会先**整块清理**已有的 `## 最近文章` 区块（不管是用户手写的还是旧版本注入的），再注入新的干净列表，所以循环构建完全幂等（跑两次 diff 为零）。

---

## FAQ

**Q: 为什么 Pages 上打开仓库根目录不是博客首页？**

仓库根目录的 `index.html` 只是一个**重定向页**，会自动跳到 `html/index.html`。这是刻意设计——Pages 默认渲染根目录的 `index.html`，但我们不想让它直接渲染 `md/index.md` 的源码，所以用了根重定向方案。

**Q: 为什么博客仓库必须和编辑器同级？**

编辑器用 `Path(__file__).resolve().parent.parent` 扫描兄弟目录来发现博客。如果放不同层级，编辑器就找不到了。

**Q: `html/` 目录可以 gitignore 吗？**

不建议。`html/` 是 GitHub Pages 的部署产物，要 push 上去才能被 Pages 托管。如果你更希望 Pages 直接跑 site_builder，可以改成 GitHub Actions 自动构建，但目前的简单方案是直接提交。

**Q: 循环构建会产生重复内容吗？**

不会。site_builder 每次构建先整块清理 `md/index.md` 里已有的 `## 最近文章` 区块，再注入干净新块。实测跑两次 diff 为零。

**Q: 私有仓库能启用 Pages 吗？**

GitHub 免费账号的私有仓库**不能**启用 Pages。有两个选项：
1. 把博客仓库设为 Public（Settings → General → Danger Zone）
2. 升级 GitHub Pro
