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

## 扩展词典

编辑 `i18n/zh-cn.dict.json`（`"英文": "中文"`），重新运行 `install_zh.py` 即可。
动态文案的规则在 `i18n/zh-cn.engine.js` 的 `RULES` 中（如 `12 files`、`3 minutes ago`）。

翻译范围有意避开了聊天正文、代码块、输入框内容（`pre`、`code`、`.markdown-body`、
`contenteditable`），避免误翻用户内容。

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
python copilot_l10n.py restore
```

## 注意

- 修改后 **Authenticode 签名失效**，Windows SmartScreen 可能提示；应用本身不校验自身签名，可正常运行。
- 仅适用于当前 PE 布局（PE32+、Brotli、描述表格式）。应用大版本改架构后脚本会报"asset not found"，
  不会写入错误数据。
- 界面文案是运行时替换，首屏可能出现极短暂的英文闪现。
- 词典只覆盖常见 UI 文案；未命中的长句会保持英文。
