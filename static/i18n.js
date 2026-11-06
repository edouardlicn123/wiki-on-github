// i18n.js — 前端中英文字典（极简实现，覆盖所有 UI 文案）
// 使用方式: <span data-i18n="key">默认值</span>
//   调用 applyI18n() 遍历 DOM，用字典覆盖 textContent/placeholder/title

const I18N = {
  zh: {
    'lang.label': '博客',
    'lang.choose': '选择博客',
    'lang.refresh': '重新扫描同级目录',
    'lang.create': '+ 创建博客',
    'lang.save': '保存',
    'lang.newPost': '+ 新建文章',
    'lang.pull': 'Pull',
    'lang.push': 'Push',
    'lang.build': '转换为网页',
    'lang.building': '正在转换...',
    'lang.buildOk': '转换完成',
    'lang.buildFail': '转换失败',
    'lang.buildDirty': '当前有未保存的改动，仍要转换？',
    'lang.postsUnit': '篇文章',
    'lang.noBlog': '暂无博客',
    'lang.noBlogHint': '在同级目录下 git clone 仓库，然后点「创建博客」。',
    'lang.blog': '博客',
    'lang.repo': '仓库',
    'lang.path': '路径',
    'lang.postList': '文章列表',
    'lang.search': '搜索…',
    'lang.sort': '排序',
    'lang.sortNameAsc': '名称 A→Z',
    'lang.sortNameDesc': '名称 Z→A',
    'lang.sortDateDesc': '修改时间 新→旧',
    'lang.sortDateAsc': '修改时间 旧→新',
    'lang.noMatch': '没有匹配的文章',
    'lang.meta': '文章元数据',
    'lang.title': '标题',
    'lang.titlePh': '文章标题',
    'lang.date': '日期',
    'lang.tags': '标签（逗号分隔）',
    'lang.tagsPh': '标签1, 标签2',
    'lang.apply': '应用到文章',
    'lang.imgLib': '图片库',
    'lang.upload': '上传',
    'lang.uploadTitle': '上传图片',
    'lang.noImg': '暂无图片<br>点「⬆ 上传」添加',
    'lang.choosePost': '— 选择一篇文章开始编辑 —',
    'lang.dirty': '● 未保存',
    'lang.reload': '重新从磁盘加载（丢弃未保存改动）',
    'lang.reloadConfirm': '当前有未保存的改动，重新加载将丢弃它们，继续？',
    'lang.reloaded': '已重新加载',
    'lang.edit': '编辑',
    'lang.preview': '预览',
    'lang.mdPh': 'Markdown 内容...',
    'lang.preview2': '预览',
    'lang.ready': '就绪',
    'lang.createBlogTitle': '创建博客',
    'lang.createBlogHint': '目标目录必须已 <code>git clone</code> 好',
    'lang.localDir': '本地目录名',
    'lang.localDirPh': '如 travel-blog',
    'lang.blogName': '博客显示名',
    'lang.blogNamePh': '如 旅行笔记',
    'lang.repoUrl': 'GitHub 仓库地址',
    'lang.cancel': '取消',
    'lang.writeTpl': '写入模板',
    'lang.pushTitle': 'Push 到 GitHub',
    'lang.commitMsg': 'Commit message',
    'lang.commitMsgPh': 'update',
    'lang.commitPush': 'Commit + Push',
    'lang.newPostTitle': '新建文章',
    'lang.tagsOptional': '可选',
    'lang.create': '创建',
    'lang.refreshBlogs': '扫描中...',
    'lang.noPost': '(没有文章)',
  },
  en: {
    'lang.label': 'Blog',
    'lang.choose': 'Select a blog',
    'lang.refresh': 'Rescan sibling directories',
    'lang.create': '+ New Blog',
    'lang.save': 'Save',
    'lang.newPost': '+ New Post',
    'lang.pull': 'Pull',
    'lang.push': 'Push',
    'lang.build': 'Convert to HTML',
    'lang.building': 'Converting...',
    'lang.buildOk': 'Converted',
    'lang.buildFail': 'Conversion failed',
    'lang.buildDirty': 'You have unsaved changes. Convert anyway?',
    'lang.postsUnit': 'posts',
    'lang.noBlog': 'No blogs yet',
    'lang.noBlogHint': 'git clone a repo in a sibling directory, then click "New Blog".',
    'lang.blog': 'Blog',
    'lang.repo': 'Repo',
    'lang.path': 'Path',
    'lang.postList': 'Posts',
    'lang.search': 'Search…',
    'lang.sort': 'Sort',
    'lang.sortNameAsc': 'Name A→Z',
    'lang.sortNameDesc': 'Name Z→A',
    'lang.sortDateDesc': 'Modified newest',
    'lang.sortDateAsc': 'Modified oldest',
    'lang.noMatch': 'No matching posts',
    'lang.meta': 'Post Metadata',
    'lang.title': 'Title',
    'lang.titlePh': 'Post title',
    'lang.date': 'Date',
    'lang.tags': 'Tags (comma separated)',
    'lang.tagsPh': 'tag1, tag2',
    'lang.apply': 'Apply to Post',
    'lang.imgLib': 'Images',
    'lang.upload': 'Upload',
    'lang.uploadTitle': 'Upload image',
    'lang.noImg': 'No images yet<br>Click "⬆ Upload" to add',
    'lang.choosePost': '— Select a post to start editing —',
    'lang.dirty': '● Unsaved',
    'lang.edit': 'Edit',
    'lang.preview': 'Preview',
    'lang.mdPh': 'Markdown content...',
    'lang.preview2': 'Preview',
    'lang.ready': 'Ready',
    'lang.createBlogTitle': 'Create Blog',
    'lang.createBlogHint': 'Target directory must already be <code>git clone</code>d',
    'lang.localDir': 'Local directory',
    'lang.localDirPh': 'e.g. travel-blog',
    'lang.blogName': 'Blog display name',
    'lang.blogNamePh': 'e.g. Travel Journal',
    'lang.repoUrl': 'GitHub repo URL',
    'lang.cancel': 'Cancel',
    'lang.writeTpl': 'Write Templates',
    'lang.pushTitle': 'Push to GitHub',
    'lang.commitMsg': 'Commit message',
    'lang.commitMsgPh': 'update',
    'lang.commitPush': 'Commit + Push',
    'lang.newPostTitle': 'New Post',
    'lang.tagsOptional': 'optional',
    'lang.create': 'Create',
    'lang.refreshBlogs': 'Scanning...',
    'lang.noPost': '(no posts)',
  },
};

// 当前语言，localStorage 持久化
function getLang() {
  let lang = localStorage.getItem('editor-lang');
  if (!lang) {
    lang = navigator.language.startsWith('zh') ? 'zh' : 'en';
  }
  return I18N[lang] ? lang : 'zh';
}
function setLang(lang) {
  if (!I18N[lang]) return;
  localStorage.setItem('editor-lang', lang);
  applyI18n();
}
function t(key, fallback) {
  const dict = I18N[getLang()];
  return dict[key] !== undefined ? dict[key] : (fallback || key);
}

function applyI18n() {
  const lang = getLang();
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';

  // data-i18n: 替换 textContent/innerHTML
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const dict = I18N[lang];
    if (dict[key] === undefined) return;
    if (el.hasAttribute('title') && el.childElementCount === 0 && el.tagName !== 'INPUT') {
      // 有 title 的按钮：保留 innerHTML 结构，只替换文本节点
      el.innerHTML = dict[key];
    } else {
      el.innerHTML = dict[key];
    }
  });

  // data-i18n-title: 替换 title
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    if (I18N[lang][key] !== undefined) el.setAttribute('title', I18N[lang][key]);
  });

  // data-i18n-placeholder: 替换 placeholder
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (I18N[lang][key] !== undefined) el.setAttribute('placeholder', I18N[lang][key]);
  });

  // 刷新 CodeMirror placeholder
  if (typeof cm !== 'undefined' && cm && cm.setOption) {
    cm.setOption('placeholder', t('lang.mdPh'));
  }

  // 回调通知 app.js
  if (typeof window._i18nCallbacks === 'object') {
    for (const cb of window._i18nCallbacks) cb();
  }
}
