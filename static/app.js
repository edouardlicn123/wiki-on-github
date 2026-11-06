// Blog Editor — 前端逻辑 v0.3 + i18n

const api = {
  async blogs() { const r = await fetch('/api/blogs'); return r.json(); },
  async posts(blogName) {
    const r = await fetch(`/api/blog/${encodeURIComponent(blogName)}/posts`); return r.json();
  },
  async post(blogName, relPath) {
    const r = await fetch(`/api/blog/${encodeURIComponent(blogName)}/post/${encodeURIComponent(relPath)}`);
    return r.json();
  },
  async savePost(blogName, relPath, content) {
    const r = await fetch(`/api/blog/${encodeURIComponent(blogName)}/post/${encodeURIComponent(relPath)}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }),
    });
    return r.json();
  },
  async createBlog(payload) {
    const r = await fetch('/api/create-blog', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    return r.json();
  },
  async pull(blogName) {
    const r = await fetch(`/api/blog/${encodeURIComponent(blogName)}/pull`, { method: 'POST' }); return r.json();
  },
  async build(blogName) {
    const r = await fetch(`/api/blog/${encodeURIComponent(blogName)}/build`, { method: 'POST' }); return r.json();
  },
  async push(blogName, msg) {
    const r = await fetch(`/api/blog/${encodeURIComponent(blogName)}/push`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }),
    });
    return r.json();
  },
  async newPost(blogName, payload) {
    const r = await fetch(`/api/blog/${encodeURIComponent(blogName)}/new-post`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    return r.json();
  },
  async images(blogName) {
    const r = await fetch(`/api/blog/${encodeURIComponent(blogName)}/images`); return r.json();
  },
  async uploadImage(blogName, filename, base64Data) {
    const r = await fetch(`/api/blog/${encodeURIComponent(blogName)}/upload-image`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, data: base64Data }),
    });
    return r.json();
  },
};

let state = {
  blogs: [],
  currentBlog: null,
  currentPost: null,
  dirty: false,
  allPosts: [],
};
let cm = null;
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', async () => {
  cm = CodeMirror.fromTextArea($('#editor-textarea'), {
    mode: 'markdown', theme: 'default',
    lineNumbers: true, lineWrapping: true,
    tabSize: 2, indentUnit: 2,
  });
  cm.on('change', () => {
    state.dirty = true;
    $('#dirty-mark').classList.remove('hidden');
    if ($('#tab-preview').classList.contains('active')) renderPreview();
  });

  // 先应用语言（覆盖 HTML 里的默认文案）
  applyI18n();
  updateLangBtn();

  await refreshBlogs();
  bindEvents();
});

// ── 事件绑定 ──
function bindEvents() {
  $('#btn-lang').addEventListener('click', () => {
    toggleLang();
    // 预览内容是渲染结果，不会被 applyI18n 重写，但切换语言后重新渲染一遍更稳
    if ($('#tab-preview').classList.contains('active')) renderPreview();
  });
  $('#btn-refresh').addEventListener('click', refreshBlogs);
  $('#blog-select').addEventListener('change', onBlogChange);
  $('#btn-save').addEventListener('click', saveCurrentPost);
  $('#btn-new-post').addEventListener('click', openNewPostModal);
  $('#btn-new-post-side').addEventListener('click', openNewPostModal);
  $('#btn-reload').addEventListener('click', reloadCurrentPost);
  $('#post-search').addEventListener('input', renderFilteredPostList);
  $('#post-sort').addEventListener('change', renderFilteredPostList);
  $('#btn-create').addEventListener('click', () => $('#create-modal').classList.remove('hidden'));

  $('#btn-pull').addEventListener('click', async () => {
    if (!state.currentBlog) return toast(t('lang.chooseBlogFirst', '请先选择博客'), 'error');
    toast(t('lang.pulling', 'Pulling...'));
    const r = await api.pull(state.currentBlog);
    toast(r.ok ? t('lang.pullOk', 'Pull 成功') : t('lang.pullFail', 'Pull 失败') + ': ' + (r.stderr || r.stdout || 'unknown'), r.ok ? 'success' : 'error');
    if (r.ok) reloadCurrentBlog();
  });
  $('#btn-push').addEventListener('click', () => {
    if (!state.currentBlog) return toast(t('lang.chooseBlogFirst', '请先选择博客'), 'error');
    $('#push-modal').classList.remove('hidden');
    $('#push-msg').value = 'update';
    setTimeout(() => $('#push-msg').focus(), 50);
  });

  $('#btn-build').addEventListener('click', async () => {
    if (!state.currentBlog) return toast(t('lang.chooseBlogFirst', '请先选择博客'), 'error');
    if (state.dirty && state.currentPost && !confirm(t('lang.buildDirty', '当前有未保存的改动，仍要转换？'))) return;
    const btn = $('#btn-build');
    const label = btn.textContent;
    const started = performance.now();
    btn.disabled = true;
    btn.classList.add('busy');
    btn.textContent = t('lang.building', '正在转换...');
    progressStart();
    toast(t('lang.building', '正在转换...'));
    try {
      const r = await api.build(state.currentBlog);
      if (r.ok) {
        toast(t('lang.buildOk', '转换完成') + ' · ' + r.pages + ' ' + t('lang.postsUnit', '篇文章'), 'success', 3500);
      } else {
        toast(t('lang.buildFail', '转换失败') + ': ' + (r.error || 'unknown'), 'error');
      }
    } catch (err) {
      toast(t('lang.buildFail', '转换失败') + ': ' + err, 'error');
    } finally {
      // 转换通常不到 1 秒，保证进度条至少可见 400ms，避免一闪而过
      const remain = Math.max(0, 400 - (performance.now() - started));
      if (remain) await new Promise(r => setTimeout(r, remain));
      progressStop();
      btn.classList.remove('busy');
      btn.textContent = label;
      btn.disabled = false;
    }
  });

  $$('#editor-tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const name = tab.dataset.tab;
      $$('#editor-tabs .tab').forEach(t => t.classList.toggle('active', t === tab));
      $$('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `tab-${name}`));
      if (name === 'preview') renderPreview();
    });
  });

  $('#cm-cancel').addEventListener('click', () => $('#create-modal').classList.add('hidden'));
  $('.modal-backdrop').addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-backdrop')) e.target.parentElement.classList.add('hidden');
  });
  $('#cm-ok').addEventListener('click', async () => {
    const dir = $('#cm-dir').value.trim();
    const name = $('#cm-name').value.trim() || dir;
    const url = $('#cm-url').value.trim();
    if (!dir) return toast(t('lang.fillDir', '请填写目录名'), 'error');
    const r = await api.createBlog({ dir_name: dir, blog_name: name, repo_url: url });
    $('#create-modal').classList.add('hidden');
    if (r.ok) {
      toast(t('lang.tplWritten', '模板写入成功！请 commit + push 到 GitHub'), 'success', 3000);
      await refreshBlogs();
      $('#blog-select').value = r.blog;
      await onBlogChange();
    } else {
      toast(t('lang.createFail', '创建失败') + ': ' + (r.error || 'unknown'), 'error');
    }
  });

  $('#push-cancel').addEventListener('click', () => $('#push-modal').classList.add('hidden'));
  $('#push-ok').addEventListener('click', async () => {
    const msg = $('#push-msg').value.trim() || 'update';
    $('#push-modal').classList.add('hidden');
    toast(t('lang.pushing', 'Pushing...'));
    const r = await api.push(state.currentBlog, msg);
    toast(r.ok ? t('lang.pushOk', 'Push 成功') : t('lang.pushFail', 'Push 失败'), r.ok ? 'success' : 'error');
  });

  $('#np-cancel').addEventListener('click', () => $('#newpost-modal').classList.add('hidden'));
  $('#np-ok').addEventListener('click', async () => {
    const title = $('#np-title').value.trim();
    const date = $('#np-date').value || new Date().toISOString().slice(0, 10);
    const tags = $('#np-tags').value.split(',').map(t => t.trim()).filter(Boolean);
    if (!title) return toast(t('lang.fillTitle', '请填写标题'), 'error');
    $('#newpost-modal').classList.add('hidden');
    const r = await api.newPost(state.currentBlog, { title, date, tags });
    if (r.ok) {
      toast(t('lang.postCreated', '文章已创建') + ': ' + r.path, 'success');
      await reloadCurrentBlog();
    } else {
      toast(t('lang.createFail', '创建失败') + ': ' + (r.error || 'unknown'), 'error');
    }
  });

  $('#fm-apply').addEventListener('click', applyFrontMatterToEditor);
  $('#btn-upload-img').addEventListener('click', () => $('#img-file-input').click());
  $('#img-file-input').addEventListener('change', handleImageUpload);

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault(); saveCurrentPost();
    }
    if (e.key === 'Escape') {
      $$('.modal').forEach(m => m.classList.add('hidden'));
    }
  });
}

// ── 语言切换 ──
function toggleLang() {
  setLang(getLang() === 'zh' ? 'en' : 'zh');
  updateLangBtn();
  // 刷新 UI 中的动态文案
  if (state.currentBlog) {
    renderImageGallery($('#img-gallery').dataset.empty ? [] : []);  // 占位
  }
}
function updateLangBtn() {
  $('#btn-lang').textContent = getLang() === 'zh' ? '中文 / EN' : 'EN / 中文';
}

// ── 博客列表 ──
async function refreshBlogs() {
  $('#sb-status').textContent = t('lang.refreshBlogs');
  const r = await api.blogs();
  state.blogs = r.blogs;
  const sel = $('#blog-select');
  sel.innerHTML = '';
  if (state.blogs.length === 0) {
    sel.innerHTML = `<option value="">— ${t('lang.noBlog')} —</option>`;
    showNoBlogHint();
    return;
  }
  showBlogPanel();
  state.blogs.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b.name;
    opt.textContent = `${b.name}  (${b.post_count})`;
    sel.appendChild(opt);
  });
  if (state.currentBlog) sel.value = state.currentBlog;
  await onBlogChange();
}

function showNoBlogHint() {
  $('#no-blog-hint').classList.remove('hidden');
  $('#blog-info').classList.add('hidden');
  $('#post-list-group').classList.add('hidden');
  $('#fm-group').classList.add('hidden');
  $('#meta-pane').classList.add('hidden');
  $('#post-search').value = '';
  $('#post-sort').value = 'date-desc';
  state.allPosts = [];
  renderFilteredPostList();
  $('#img-group').classList.add('hidden');
  state.currentBlog = null;
  state.currentPost = null;
  cm.setValue('');
  state.dirty = false;
  $('#dirty-mark').classList.add('hidden');
  $('#sb-status').textContent = t('lang.ready');
  // 禁用所有依赖当前博客的按钮
  setBlogButtonsEnabled(false);
}
function showBlogPanel() {
  $('#no-blog-hint').classList.add('hidden');
  $('#blog-info').classList.remove('hidden');
  $('#post-list-group').classList.remove('hidden');
  $('#fm-group').classList.remove('hidden');
  $('#meta-pane').classList.remove('hidden');
  $('#img-group').classList.remove('hidden');
  // 选中博客后启用按钮
  setBlogButtonsEnabled(true);
}

function setBlogButtonsEnabled(enabled) {
  [
    '#btn-save', '#btn-new-post', '#btn-new-post-side',
    '#btn-pull', '#btn-push', '#btn-build',
    '#fm-apply', '#btn-upload-img', '#btn-reload',
  ].forEach(sel => { const el = $(sel); if (el) el.disabled = !enabled; });
}

async function onBlogChange() {
  const name = $('#blog-select').value;
  if (!name) { showNoBlogHint(); return; }
  $('#post-search').value = '';
  $('#post-sort').value = 'date-desc';
  if (state.dirty && state.currentPost) {
    if (!confirm(t('lang.switchConfirm', '当前有未保存的改动，确定切换？'))) {
      $('#blog-select').value = state.currentBlog; return;
    }
  }
  state.currentBlog = name;
  const blog = state.blogs.find(b => b.name === name);
  if (blog) {
    $('#info-name').textContent = blog.name;
    $('#info-url').textContent = blog.repo_url || t('lang.notSet', '未设置');
    $('#info-path').textContent = blog.path;
  }
  await reloadCurrentBlog();
}

async function reloadCurrentBlog() {
  if (!state.currentBlog) return;
  const [postsR, imgR] = await Promise.all([api.posts(state.currentBlog), api.images(state.currentBlog)]);
  renderPostList(postsR.posts);
  renderImageGallery(imgR.images || []);
  if (postsR.posts.length > 0) {
    await loadPost(postsR.posts[0]);
  } else {
    cm.setValue('# 暂无文章\n\n点击「+ 新建文章」来创建第一篇。\n');
    $('#current-file').textContent = t('lang.noPost');
    state.currentPost = null; state.dirty = false;
    $('#dirty-mark').classList.add('hidden');
    clearFrontMatterForm();
  }
  $('#sb-status').textContent = `${t('lang.blog')}: ${state.currentBlog}`;
}

function renderPostList(posts) {
  state.allPosts = posts;
  renderFilteredPostList();
}

function renderFilteredPostList() {
  const q = ($('#post-search').value || '').trim().toLowerCase();
  let posts = q
    ? (state.allPosts || []).filter(p => p.name.toLowerCase().includes(q))
    : (state.allPosts || []);
  const sortKey = $('#post-sort').value || 'date-desc';
  const dir = sortKey.endsWith('-desc') ? -1 : 1;
  const key = sortKey.startsWith('name') ? 'name' : 'mtime';
  posts = [...posts].sort((a, b) => {
    if (key === 'name') return dir * a.name.localeCompare(b.name, 'zh');
    return dir * ((a.mtime || 0) - (b.mtime || 0));
  });
  $('#post-count').textContent = posts.length;
  const ul = $('#post-list');
  ul.innerHTML = '';
  if (q && posts.length === 0) {
    ul.innerHTML = `<li class="empty">${t('lang.noMatch', '没有匹配的文章')}</li>`;
    return;
  }
  posts.forEach(p => {
    const li = document.createElement('li');
    li.innerHTML = `<span>📄 ${p.name}</span><span class="meta">${formatSize(p.size)}</span>`;
    li.addEventListener('click', () => loadPost(p, li));
    ul.appendChild(li);
  });
}

function renderImageGallery(images) {
  $('#img-count').textContent = images.length;
  const wrap = $('#img-gallery');
  wrap.innerHTML = '';
  if (images.length === 0) {
    wrap.innerHTML = `<div class="img-empty">${t('lang.noImg')}</div>`;
    return;
  }
  images.forEach(img => {
    const div = document.createElement('div');
    div.className = 'img-item';
    div.title = `${img.name} (${formatSize(img.size)})`;
    div.innerHTML = `<img src="/api/blog/${encodeURIComponent(state.currentBlog)}/image/${encodeURIComponent(img.path)}" alt="${img.name}">`;
    div.addEventListener('click', () => insertImageMarkdown(img.path));
    wrap.appendChild(div);
  });
}

function insertImageMarkdown(imgRelPath) {
  if (!cm) return;
  const mdPath = '../' + imgRelPath;
  cm.replaceSelection(`\n![${imgRelPath.split('/').pop()}](${mdPath})\n`, 'end');
  cm.focus();
  toast(t('lang.imgInserted', '已插入图片引用'), 'success', 1000);
}

async function handleImageUpload(e) {
  const file = e.target.files?.[0];
  e.target.value = '';
  if (!file) return;
  if (!state.currentBlog) return toast(t('lang.chooseBlogFirst', '请先选择博客'), 'error');
  toast(t('lang.uploading', '上传中...'));
  const buf = await file.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  const r = await api.uploadImage(state.currentBlog, file.name, btoa(binary));
  if (r.ok) {
    toast(t('lang.uploadOk', '上传成功') + ': ' + r.path, 'success');
    renderImageGallery((await api.images(state.currentBlog)).images || []);
    insertImageMarkdown(r.path);
  } else {
    toast(t('lang.uploadFail', '上传失败') + ': ' + (r.error || 'unknown'), 'error');
  }
}

async function loadPost(post, liEl) {
  if (state.dirty && state.currentPost) {
    if (!confirm(t('lang.switchConfirm', '当前有未保存的改动，确定切换？'))) return;
  }
  const r = await api.post(state.currentBlog, post.path);
  if (r.error) { toast(r.error, 'error'); return; }
  cm.setValue(r.content); cm.refresh();
  state.currentPost = { name: r.name, path: r.path, content: r.content, metadata: r.metadata };
  state.dirty = false;
  $('#dirty-mark').classList.add('hidden');
  $('#current-file').textContent = r.name;
  fillFrontMatterForm(r.metadata);
  $$('#post-list li').forEach(li => li.classList.remove('active'));
  if (liEl) liEl.classList.add('active');
  if ($('#tab-preview').classList.contains('active')) renderPreview();
}

async function reloadCurrentPost() {
  if (!state.currentPost) return;
  if (state.dirty) {
    if (!confirm(t('lang.reloadConfirm', '当前有未保存的改动，重新加载将丢弃它们，继续？'))) return;
  }
  const r = await api.post(state.currentBlog, state.currentPost.path);
  if (r.error) { toast(r.error, 'error'); return; }
  cm.setValue(r.content); cm.refresh();
  state.currentPost.content = r.content;
  state.currentPost.metadata = r.metadata;
  state.dirty = false;
  $('#dirty-mark').classList.add('hidden');
  fillFrontMatterForm(r.metadata);
  if ($('#tab-preview').classList.contains('active')) renderPreview();
  toast(t('lang.reloaded', '已重新加载'));
}

function fillFrontMatterForm(meta) {
  meta = meta || {};
  $('#fm-title').value = meta.title || '';
  $('#fm-date').value = meta.date || '';
  const tags = meta.tags;
  $('#fm-tags').value = Array.isArray(tags) ? tags.join(', ') : (tags || '');
}
function clearFrontMatterForm() {
  $('#fm-title').value = ''; $('#fm-date').value = ''; $('#fm-tags').value = '';
}

function applyFrontMatterToEditor() {
  if (!state.currentBlog || !state.currentPost) {
    toast(t('lang.choosePostFirst', '请先选择一篇文章'), 'error'); return;
  }
  const title = $('#fm-title').value.trim();
  const date = $('#fm-date').value.trim();
  const tags = $('#fm-tags').value.split(',').map(t => t.trim()).filter(Boolean);
  let content = cm.getValue();
  const match = content.match(/^---\n([\s\S]*?)\n---\n/);
  let body = content;
  let existing = {};
  if (match) { body = content.slice(match[0].length); existing = parseFm(match[1]); }
  const merged = { ...existing };
  if (title) merged.title = title;
  if (date) merged.date = date;
  merged.tags = tags;
  const lines = ['---'];
  for (const [k, v] of Object.entries(merged)) {
    if (Array.isArray(v)) lines.push(`${k}: [${v.join(', ')}]`);
    else if (v !== undefined && v !== null) lines.push(`${k}: ${v}`);
  }
  lines.push('---', '');
  cm.setValue(lines.join('\n') + body);
  state.dirty = true;
  $('#dirty-mark').classList.remove('hidden');
  toast(t('lang.fmUpdated', '已更新 front matter（记得保存）'), 'success', 1500);
}

function parseFm(text) {
  const result = {};
  for (const raw of text.splitlines()) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const m = line.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$/);
    if (!m) continue;
    let val = m[2].trim();
    if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
    if (val.startsWith('[') && val.endsWith(']')) {
      val = val.slice(1, -1).split(',').map(s => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
    }
    result[m[1]] = val;
  }
  return result;
}

async function saveCurrentPost() {
  if (!state.currentBlog || !state.currentPost) {
    toast(t('lang.noPostToSave', '没有可保存的文章'), 'error'); return;
  }
  const content = cm.getValue();
  const r = await api.savePost(state.currentBlog, state.currentPost.path, content);
  if (r.ok) {
    state.dirty = false; $('#dirty-mark').classList.add('hidden');
    state.currentPost.content = content;
    toast(t('lang.saved', '已保存') + ` ${r.size} B`, 'success', 1500);
  } else {
    toast(t('lang.saveFail', '保存失败') + ': ' + (r.error || 'unknown'), 'error');
  }
}

function renderPreview() {
  if (!cm) return;
  // md 在 md/ 子目录，图片用 ../images/，预览时换成服务端图片地址
  let raw = cm.getValue().replace(
    /!\[([^\]]*)\]\((?:\.\.\/)?(?:\.\/)?images\/([^)\s]+)\)/g,
    (_m, alt, rel) => `![${alt}](/api/blog/${encodeURIComponent(state.currentBlog)}/image/${encodeURIComponent('images/' + rel)})`
  );
  // site_builder 动态区块：成对边界注释之间的内容是真实 md 列表
  // site_builder 已跑过 → 边界之间有真实内容，marked.js 直接渲染（什么都不做）
  // 还没跑过 → 边界之间是占位符，前端兜底替换
  if (/<!--\s*site_builder:start/.test(raw) && /<!--\s*site_builder:end/.test(raw)) {
    const hasRealList = /\[[^\]]+\]\([^)]+\.md\)/.test(
      raw.match(/<!--\s*site_builder:start[^>]*-->(.*?)<!--\s*site_builder:end/s)?.[1] || ''
    );
    if (!hasRealList && state.allPosts?.length) {
      const items = state.allPosts
        .slice()
        .sort((a, b) => {
          if (a.date && b.date) return a.date < b.date ? 1 : -1;
          return a.name.localeCompare(b.name, 'zh');
        })
        .filter(p => p.name !== 'index.md')
        .map(p => {
          const title = (p.title || p.name.replace(/\.md$/, '')).replace(/"/g, '&quot;');
          const date = p.date ? p.date : '';
          const slug = p.name.replace(/\.md$/, '');
          return `- ${date ? '**' + date + '** ' : ''}[${title}](./${p.name})`;
        })
        .join('\n');
      raw = raw.replace(
        /<!--\s*site_builder:start([^>]*)-->(.*?)<!--\s*site_builder:end/s,
        `<!-- site_builder:start$1 -->\n\n${items}\n\n<!-- site_builder:end -->`,
      );
    }
  }
  $('#preview-content').innerHTML = marked.parse(raw);
}

// 预览面板里点击 .md 内部链接 → 在编辑器里切换到对应文章（场景②）
document.addEventListener('click', (e) => {
  const a = e.target.closest('#preview-content a[href]');
  if (!a || a.target === '_blank') return;
  const href = a.getAttribute('href') || '';
  // 相对 .md 链接才拦截（http/../images/index.html 等都不拦）
  if (!href.endsWith('.md') || /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(href)) return;
  e.preventDefault();
  const name = href.split('/').pop();
  const target = state.allPosts?.find(p => p.name === name);
  if (target) {
    loadPost(target);
    $('#tab-edit').classList.add('active');
    $('#tab-preview').classList.remove('active');
  }
});

function openNewPostModal() {
  if (!state.currentBlog) { toast(t('lang.chooseBlogFirst', '请先选择博客'), 'error'); return; }
  $('#np-title').value = '';
  $('#np-date').value = new Date().toISOString().slice(0, 10);
  $('#np-tags').value = '';
  $('#newpost-modal').classList.remove('hidden');
  setTimeout(() => $('#np-title').focus(), 50);
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

let toastTimer;
function toast(msg, type = 'info', duration = 2000) {
  const sb = $('#sb-msg');
  sb.textContent = msg;
  sb.style.color = type === 'success' ? '#4ade80' : type === 'error' ? '#f87171' : '#9ba1a9';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { sb.textContent = ''; }, duration);
}

function progressStart() {
  $('#progress').classList.remove('hidden');
}

function progressStop() {
  $('#progress').classList.add('hidden');
}
