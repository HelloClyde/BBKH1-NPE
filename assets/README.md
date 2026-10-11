# NPE 应用素材

## 中文菜单字体

暂停菜单和底部触摸栏使用 Noto Sans CJK SC Regular，按 OFL 1.1 分发。
字体固定于 [noto-cjk 提交 f8d1575](https://github.com/notofonts/noto-cjk/tree/f8d157532fbfaeda587e826d4cd5b21a49186f7c)，
文件为 `Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf`，SHA256：
`2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b`。
许可证见 `licenses/NotoSansCJK-OFL.txt`。

`src/platform/menu_font.h` 是 18 像素字体的 18×21 单色字形子集，保留实际字宽。
修改中文文案后，使用固定版本 Pillow 和上述字体执行：

```powershell
python tools/generate_menu_font.py --font 'NotoSansCJKsc-Regular.otf'
```

生成器核对字体摘要，并收录平台源码中的中文及 ASCII 字符；普通构建只消费已生成的头文件。

## 应用图标

`npe-icon.png` 使用内置 imagegen 工具生成，是构建直接消费的正方形 RGBA 原图。
主体参考本机 `np560/scripts/web/assets/np560plus-open-cutout.png` 中的诺亚舟 NP560+：
银色机身、绿色液晶屏、两侧圆形方向控制和黑色滑出键盘。照片只用于观察设备特征，未作为贴图复制。
视觉参考 H1 V1.41 原生桌面和本地 GBA 应用图标：圆角底板、明亮渐变、上方高光和立体主体。
橙金色底板呼应诺亚舟的橙色品牌元素，屏幕中的 NPE 用于小尺寸识别。

## H1 资源格式

构建器使用固定版本 SDK 的 `build_icon_resources()`，保持比例并居中：

| 资源 | 尺寸 | 编码 |
| --- | --- | --- |
| 0 | 45×45 | RGB565 little-endian + 8-bit alpha |
| 1 | 57×57 | RGB565 little-endian + 8-bit alpha |
| 2 | 49×60 | RGB565 little-endian，透明部分合成黑色 |
| 3 | 49×60 | RGB565 little-endian，透明部分合成黑色，尾部补零 |

外轮廓保留透明边缘。格式依据 SDK 的 `docs/verified/custom_icon_build.md` 和
`reverse/docs/menu_icon_resources.md`；视觉风格依据原生图标观察，不声称存在单独的官方视觉规范。

`python tools/check_app_icon.py` 复核 BDA、四份资源、透明度、资源尾部、元数据和安装 ZIP，
输出 `build/icon-design/packed-icons-preview.png`。
加 `--baseline 旧版.bda` 可逐字节确认可执行载荷不变，头部仅允许名称及其校验和变化。

## 生成提示词

```text
Use case: stylized-concept.
Asset type: one finished square raster application icon for the BBK H1 NPE emulator.
Input images: Image 1 is a subject reference: genuine silver Noah NP560+ learning machine with green LCD and black slide-out keyboard; Image 2 is the H1 native desktop icon style reference; Image 3 is a compatible custom H1 icon, only a style reference. Do not copy any existing icon artwork.
Primary request: Design a recognizable miniature Noah learning machine icon fitting the early-2000s BBK H1 glossy icon family. Use the NP560+ silhouette: broad silver main panel, central green monochrome LCD, narrow side buttons with small circular direction controls on both sides, and a visibly extended dark keyboard underneath. Simplify the keyboard to three crisp broad rows of dark keys and the side buttons to bold simple shapes so it reads at 45x45 pixels. Machine nearly frontal with slight dimensional tilt, contained within the tile, filling most of it. Use exact bold text "NPE" centered on the green LCD in very dark ink, no other text.
Style/medium: polished compact 3D pictogram with softly bevelled silver housing, broad highlights, clean outlines, restrained detail. Match the H1 icons' glossy rounded-square tile, bright gradient, dimensional subject and upper-left white sheen. Background tile warm amber/gold to differentiate Noah's familiar orange accent, subject silver-white with dark charcoal keyboard and sage-green LCD. Tight soft internal shadow, crisp bright silhouette.
Composition: single icon, tile fills about 90% of square canvas; genuinely transparent margin outside rounded perimeter. All device parts contained inside tile. Strong legibility at 45x45. No tiny key labels or small logos, no photographic detail, no extra objects, no checkerboard baked into image, no scene or icon grid, no watermark, no label outside tile. Output a square RGBA PNG.
```
