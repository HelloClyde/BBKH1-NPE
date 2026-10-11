# 来源

本仓库原创 H1 适配层（`src/`）、构建/打包脚本（`tools/`）与测试（`tests/`）
采用 GNU GPL version 2，完整文本见根目录 `LICENSE`。
从 BBKH1-GBA 改编的代码保留 GPL-2.0 来源；此许可不覆盖下列各自授权的第三方内容。

- NPE 引擎：HelloClyde/noah-npe-engine，提交 `942b645ba26693db43c32375f28d53d32d1da099`。
  保持原始子模块，不修改上游。上游当前未授予源码开源许可证。
- H1 运行时、freestanding libc、PCM、按键矩阵、触摸及诊断代码参考/改编自
  HelloClyde/BBKH1-GBA（GPL-2.0），硬件接口在提交
  `e73848f295508d92f45488b354735a35c9722477` 核对。对应许可证见 `assets/licenses/GPL-2.0.txt`。
- H1 BDA SDK：MrDefinition1999/bbk-h1-bda-sdk，提交
  `067fe072477861dfc8949d7b1a55279fb92d2548`，Apache-2.0，许可证保留在子模块内。
- 暂停菜单和触摸栏字形：Noto Sans CJK SC 子集，SIL OFL 1.1，
  `assets/licenses/NotoSansCJK-OFL.txt`。
- 游戏内字体按上游 `npe-sdl/assets/FONT-LICENSE.txt` 和 `FONT-PROVENANCE.txt` 保留来源说明。
- 应用图标：内置 imagegen 生成的学习机插画，设计与提示词见 `assets/README.md`。
  诺亚舟 NP560+ 外观和 H1 原生图标仅作为主体/风格参考；未直接复制照片或原机图标资源。
- `assets/screenshots/` 为独立 H1 V1.41 固件模拟器的实测帧缓冲，
  记录见 `docs/evidence/`；其中原生桌面资源和《天降风云》画面归原权利人。

本地移植不代表取得 NPE 源码的再许可权，也未包含、发布 NPE 游戏或原机固件。
