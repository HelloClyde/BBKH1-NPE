# H1 NPE 引擎移植

将 [noah-npe-engine](https://github.com/HelloClyde/noah-npe-engine) 移植到步步高 H1 / Y100 原生 BDA。
硬件平台参考 [BBKH1-GBA](https://github.com/HelloClyde/BBKH1-GBA)。这是独立的 H1 移植项目。
项目仓库：[HelloClyde/BBKH1-NPE](https://github.com/HelloClyde/BBKH1-NPE)。

H1 桌面和应用列表显示名称为 **诺亚舟NPE**；安装文件名为 `H1NPE.bda`。

## 安装

解压 `dist/H1NPE-install.zip`，将 `应用` 和 `NPE` 两个文件夹合并到 H1 的 A 盘：

```text
A:\应用\程序\H1NPE.bda
A:\NPE\assets\gbk12-native.bin
A:\NPE\assets\gbk16-native.bin
```

保留这两个字体文件。将自己的 `.npe` 游戏放到 `A:\NPE\` 或其他目录，
启动 `H1NPE.bda` 后通过系统文件选择器选取游戏。取消选择会退出。
存档保存在所选 NPE 所在目录，使用上游按游戏指纹区分的三个 `.npes` 文件。
存档通过游戏内菜单手动保存，退出前请先存档；不会在任意剧情或战斗状态下自动存档。

## 操作

| H1 操作 | 功能 |
| --- | --- |
| 方向键 / I J L M | 移动、选择 |
| 确认 / Enter / Z / K | 确认、调查 |
| 空格 | 对话、翻页 |
| 返回 / X | 游戏菜单、取消（原 F4） |
| P / 触摸底栏 MENU | 暂停，声音、1x/2x显示、换游戏、退出 |
| Escape | 退出应用 |
| 触摸底栏 | 左、右、上、下、确认、对话、返回、暂停菜单 |

问答模式保留字母输入，包括 Z/X/P；Shift 接入大写输入。方向键长按可重复移动。
默认显示原始 240×120 画面的 2 倍版本 480×240，底部 32 像素为触摸操作栏。
暂停菜单停止游戏时钟和 PCM，继续后恢复；关闭声音仍推进音频服务的剧情回调。
中文路径直接使用 H1 的 GBK 字节，目录解析避开 GBK 尾字节中的反斜杠。

## 构建

需要 Python 3.10+、Pillow、Git 和 `mipsel-none-elf-gcc` / `objcopy`。

```powershell
git submodule update --init --recursive
python -m pip install Pillow
$env:H1_GNU_BIN = 'C:\tools\mipsel-none-elf\bin'
python tools/build.py
python tools/build.py --debug
python tools/check_app_icon.py
```

MIPS 自动测试需要 `tests/requirements.txt` 中的依赖和自己提供的 NPE：

```powershell
python -m pip install -r tests/requirements.txt
python tests/mips_smoke.py --game '你的游戏.npe'
python tests/error_paths.py --game '你的游戏.npe'
python tools/build.py --test-new-game
python tests/mips_smoke.py --game '你的游戏.npe' --bda dist/H1NPE-test-new-game.bda --gameplay
python tools/build.py --test-storage
python tests/mips_smoke.py --game '你的游戏.npe' --bda dist/H1NPE-test-storage.bda --storage
```

`--gameplay` 的菜单序列按《天降风云》初始化状态验证，其他游戏可能需要不同输入。
测试 BDA 会跳过开场或执行存储探针，请使用正式 `H1NPE.bda` 安装包游玩。

依赖锁定于 `.gitmodules` 和构建脚本中的提交；构建器拒绝修改过的依赖。
SDL2 本身不参与 H1 编译。`src/platform/SDL.h` 仅实现本引擎所需的小型 API 子集，
上游前端和音频调度在构建副本中使用 H1 显示、文件、时钟、按键和 PCM 服务。
源码入口为 `src/app.c`；适配层为 `src/platform/sdl_h1.c`。
运行错误及加载过程记录在 `A:\NPE\h1npe.log`。

应用图标使用诺亚舟学习机元素和 H1 高光圆角风格，原图与生成提示词见 `assets/README.md`。
构建会生成 H1 的全部四份菜单图标资源；更新图标不需要在构建时调用图像生成服务。

## 验证状态

交叉编译、BDA 格式校验和运行测试的结果见 `docs/verification.md`。
尚未进行 H1 真机验证；模拟服务和完整固件模拟器的证据分别记录。
游戏兼容性仍受上游引擎实现范围限制。

## 来源与许可

见 `NOTICE.md`。NPE 上游目前未授予项目源码开源许可证，此移植没有改变其授权状态。
安装包不包含游戏资源。
