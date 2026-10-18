# copilot-l10n

把 GitHub Copilot 桌面应用的界面改成本地化（当前提供简体中文）的工具。

> 适用版本：`github.exe` 1.1.30（CLI 1.0.99-2），Tauri/PE32+ 单文件应用。
> 应用更新后资源文件名会变，脚本通常仍可用，必要时用 `find` 重新定位注入点。

## 原理

1. 应用前端资源以 **Brotli** 压缩后内嵌在 PE 的 `.rdata` 段里。
2. 每个资源在 `.rdata` 中有一份 `(绝对指针, 压缩长度)` 描述（16 字节）。
3. 用 Brotli `quality=11` 重新压缩通常比构建时更小，因此可以在**原位置**改写资源，
   同时更新描述表中的长度。空间不够时脚本会报错并拒绝写入，不会破坏文件。
4. 注入的 JS 是一层运行时翻译器：遍历 DOM 文本节点与 `placeholder/title/aria-label/alt`
   等属性，按词典替换，并用 `MutationObserver` 处理后续渲染。

不修改任何逻辑代码，不改 CSP，不需要开发者模式。

## 环境

仓库内已包含 `.venv`（Python 3.13 + brotli）。重新建立：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 备份与基线（重要）

- 首次安装会把原版 exe 复制为 `github.exe.l10n-bak`，**之后永不覆盖**。
- 每次打补丁前，脚本都会先把目标资源**还原成备份里的原版字节**，再应用补丁。
  因此重复安装不会叠加补丁，`status` 里 `payload x1` 才代表正常。
- 若备份丢失而 exe 已经打过补丁，脚本会**拒绝执行**（无法还原干净基线），
  此时需重装应用。
- 应用升级后 exe 大小会与备份不同，脚本会提示；确认新版本是干净的后，用
  `rebaseline` 把它采纳为新基线：

```powershell
.\.venv\Scripts\python.exe copilot_l10n.py status
.\.venv\Scripts\python.exe copilot_l10n.py rebaseline "/assets/App-<新哈希>.js" index.html
```

## 安装（应用运行中无法写入 exe）

双击 `install_zh.cmd`，或在外部 PowerShell 中运行：

```powershell
cd C:\Users\long1\copilot-l10n
.\.venv\Scripts\python.exe install_zh.py
```

脚本会：

1. 检测 `github.exe` 是否被占用；若占用，提示你**完全退出 Copilot**（含托盘），
   每 2 秒轮询，退出后自动继续；
2. 备份到 `github.exe.l10n-bak`（仅首次）；
3. 把翻译载荷追加到启动时加载的 `assets/App-*.js`，并把 `index.html` 改为 `lang="zh-CN"`；
   **两处修改在同一次文件打开中完成**，避免应用中途被重新拉起导致只改了一半；
4. 若写入瞬间仍被占用，自动重新等待并重试（默认 5 次）；
5. 重新读取校验，输出 `STATE: INSTALLED`；
6. 启动应用。

安装是**幂等**的：已经打过补丁的分块会被跳过，只补齐缺失的部分，所以中途失败后
直接重跑即可。

常用参数：

```powershell
--dry-run        只计算大小，不写文件
--no-launch      打完补丁不自动启动
--asset PATH     指定注入的启动分块（默认 /assets/App-DxoK3vc2.js）
--exe PATH       非默认安装路径
--timeout 600    等待应用退出的秒数
--attempts 5     写入被占用时的重试次数
```

检查当前状态：

```powershell
.\.venv\Scripts\python.exe copilot_l10n.py status
```

## 回滚

应用退出后：

```powershell
.\.venv\Scripts\python.exe copilot_l10n.py restore
```

`restore` 会把 `github.exe.l10n-bak` 覆盖回原文件。

## 先在副本上验证

```powershell
# 复制并打补丁到 build\github-zh.exe（不影响正在运行的应用）
.\.venv\Scripts\python.exe apply_zh.py --copy build\github-zh.exe
# 校验
.\.venv\Scripts\python.exe copilot_l10n.py --exe build\github-zh.exe verify "/assets/App-DxoK3vc2.js" index.html
```

## 更新应用之后

```powershell
# 1. 找到新的启动分块（通常选 raw 最大且 headroom 足够的 App-*.js）
.\.venv\Scripts\python.exe copilot_l10n.py find App-

# 2. 重新安装
.\.venv\Scripts\python.exe install_zh.py --asset "/assets/App-<新哈希>.js"
```

应用更新会把 exe 覆盖回英文，需要重新执行一次。

## 缺少控制台怎么办

应用是 Tauri 打包的发布版，默认没有开发者工具入口。两种办法：

1. **不用控制台**（推荐）：在应用里按 <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>L</kbd>，
   会把你当前界面上**未能翻译**的英文复制到剪贴板，右上角会有提示；
   直接粘贴给我即可补词典。按 <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>U</kbd> 可重新扫描当前页面。
2. **开远程调试**：先完全退出应用，再运行 `launch_debug.cmd`，
   然后浏览器打开 <http://127.0.0.1:9222> 即可用完整 DevTools；
   控制台里可执行 `__COPILOT_L10N_MISSES__()`。

## 抓取未翻译文案（自动）

不需要控制台也能从包体里提取英文原文：

```powershell
.\.venv\Scripts\python.exe tools\harvest_strings.py --missing
```

输出 `build/ui-strings.txt`（`次数<TAB>原文`）。把需要翻译的条目写进
`i18n/*.extra.json`（格式 `"English": "中文"`），重新运行 `install_zh.py` 即可；
`i18n/` 下的所有 `*.extra.json` 会在构建时合并进主词典。

## 扩展词典

编辑 `i18n/zh-cn.dict.json`（`"英文": "中文"`），重新运行 `install_zh.py` 即可。
动态文案的规则在 `i18n/zh-cn.engine.js` 的 `RULES` 中（如 `12 files`、`3 minutes ago`）。

检查词典：

```powershell
.\.venv\Scripts\python.exe tools\check_dict.py            # 重复键 / 空值
.\.venv\Scripts\python.exe tools\dedupe_dict.py           # 自动去重
```

查看界面上仍然残留的英文（需要 DevTools 控制台，或用上面的快捷键）：

```js
__COPILOT_L10N_MISSES__()   // 返回当前未命中的文本
```

把返回结果补进 `zh-cn.dict.json` 再重装即可。

翻译范围有意避开了聊天正文、代码块、输入框内容（`pre`、`code`、`.markdown-body`、
`contenteditable`），避免误翻用户内容。React 把 `{count} files` 渲染成两个文本节点，
引擎会合并相邻文本节点后再匹配，因此 `12 files` 这类文案也能翻译。

运行时临时关闭（需要 DevTools）：

```js
localStorage.setItem('copilot-l10n', 'off'); location.reload();
```

## 底层命令

```powershell
python copilot_l10n.py stat    "/assets/App-DxoK3vc2.js"   # 尺寸与 headroom
python copilot_l10n.py find    App-                        # 按子串找资源
python copilot_l10n.py status                              # 是否已安装
python copilot_l10n.py extract "/assets/App-DxoK3vc2.js" out.mjs
python copilot_l10n.py patch   "/assets/App-DxoK3vc2.js" payload.js
python copilot_l10n.py replace index.html map.json         # { "old": "new" }
python copilot_l10n.py verify  "/assets/App-DxoK3vc2.js"
python copilot_l10n.py baseline "/assets/App-DxoK3vc2.js" index.html
python copilot_l10n.py rebaseline "/assets/App-DxoK3vc2.js" index.html
python copilot_l10n.py restore
```

## 注意

- 修改后 **Authenticode 签名失效**，Windows SmartScreen 可能提示；应用本身不校验自身签名，可正常运行。
- 仅适用于当前 PE 布局（PE32+、Brotli、描述表格式）。应用大版本改架构后脚本会报"asset not found"，
  不会写入错误数据。
- 界面文案是运行时替换，首屏可能出现极短暂的英文闪现。
- 词典只覆盖常见 UI 文案；未命中的长句会保持英文。
