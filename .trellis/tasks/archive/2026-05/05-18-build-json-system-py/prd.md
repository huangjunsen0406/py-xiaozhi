# build.json 从 system.py 动态生成 + 发版自动同步版本号

## Goal

以 `system.py` 为唯一版本/名称真相源，发版时自动更新版本号并生成 `build.json`。二开开发者只需改 `system.py` 即可完成自定义品牌/名称。替代当前无法使用的 `release.js`（依赖不存在的 package.json）。

## What I already know

- `system.py`: `APP_NAME="py-xiaozhi"`, `APP_DISPLAY_NAME="py-xiaozhi"`, `APP_VERSION="2.0.3"`
- `build.json`: `name="xiaozhi"`, `display_name="小智"`, `version="1.1.9"` — 与 system.py 不同步
- `release.js`: 用 `pnpm version` 但项目没有 `package.json`，跑不通
- `release.yml`: 监听 `v*.*.*` tag，用 release-drafter 创建 GitHub Release
- `build.json` 是 unifypy 打包器的配置文件
- 中文 `bundle_identifier: "com.company.小智"` 会导致问题，需改为 ASCII
- `APP_NAME` 通过 `platformdirs` 用于生成用户数据目录路径

## Requirements

1. **新建 `release.py`** 替代 `release.js`：
   - 交互式选择版本类型（patch/minor/major/prepatch/prerelease）
   - 读取 `system.py` 当前 `APP_VERSION` → 计算新版本号
   - 写回 `system.py` 的 `APP_VERSION`
   - 从 `system.py` 常量生成 `build.json`
   - git commit + git tag + git push --follow-tags

2. **`system.py` 名称修正**：
   - `APP_NAME = "xiaozhi"`（纯 ASCII，用于路径/bundle_id/数据目录）
   - `APP_DISPLAY_NAME = "小智"`（Unicode，用于窗口标题/Launchpad/安装器 UI）

3. **`build.json` 生成逻辑**：
   - `name` ← `APP_NAME`
   - `display_name` ← `APP_DISPLAY_NAME`
   - `version` ← `APP_VERSION`
   - `bundle_identifier` ← `com.{APP_NAME}.app`（ASCII）
   - 其余字段（pyinstaller/platforms 配置）保持为 build.json 模板中的值

4. **用户数据目录迁移**：
   - `resource_finder.py` 的 `get_user_data_dir()` 中检测旧目录 `py-xiaozhi`
   - 如果旧目录存在且新目录不存在，自动重命名迁移
   - 迁移后 log 提示

5. **删除 `release.js`**

## Acceptance Criteria

- [ ] `python release.py` 交互式选择版本后自动更新 system.py + 生成 build.json + commit + tag + push
- [ ] build.json 的 version/name/display_name 与 system.py 一致
- [ ] bundle_identifier 为纯 ASCII
- [ ] release.yml 无需改动（仍监听 v* tag）
- [ ] APP_NAME 改名后所有引用正常（platformdirs 路径、窗口标题等）
- [ ] 旧用户升级后数据目录自动迁移，config/logs/cache 不丢失

## Definition of Done

- Lint / typecheck green
- 手动测试 `python release.py` dry-run 模式
- 确认 APP_NAME 全局引用无副作用

## Out of Scope

- CI/CD workflow 改动（release.yml 不动）
- unifypy 打包器本身的改动

## Technical Approach

1. 修正 `system.py`：`APP_NAME="xiaozhi"`, `APP_DISPLAY_NAME="小智"`
2. `resource_finder.py` 的 `get_user_data_dir()` 加旧目录迁移逻辑
3. 新建 `release.py`（项目根目录），手写 semver 计算（避免额外依赖）
4. `release.py` 内嵌 `build.json` 模板，从 `system.py` import 常量填充并写入
5. 全局搜索 `APP_NAME`/`APP_DISPLAY_NAME` 引用确认改名无副作用
6. 删除 `release.js`
