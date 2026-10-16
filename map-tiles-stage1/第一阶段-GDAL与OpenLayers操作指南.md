# 第一阶段：用 GDAL 和 OpenLayers 把普通图片做成瓦片地图

## 1. 目标和实验材料

本实验把一张 **4096 × 4096** 的普通图片切成多级瓦片，再用 OpenLayers 展示，实现缩放、拖动，并观察浏览器如何请求瓦片。

实验链路：

```text
4096 × 4096 图片
       ↓ GDAL 离线切片
0～4 级、256 × 256 像素的 PNG 瓦片
       ↓ 本地 HTTP 服务
OpenLayers 按当前视野和缩放级别加载
```

这张图片使用自定义像素坐标，不需要经纬度、地图 API Key、地理配准或 GeoTIFF。这里采用 XYZ 文件编号，但它是**图片自己的瓦片网格**，不等于已经具有地理位置的全球地图瓦片。

本机已实际验证的环境：

| 项目 | 版本 / 配置 |
| --- | --- |
| 操作系统 | Windows |
| 已安装的 QGIS | 3.44.10 |
| QGIS 自带 GDAL | 3.12.4 |
| QGIS 自带 Python | 3.12.13 |
| OpenLayers | 10.11.0，使用固定版本的 CDN 文件 |
| 输入图片 | 4096 × 4096，RGB PNG |
| 输出瓦片 | 256 × 256 PNG，XYZ，0～4 级 |

### 已准备好的示例文件

本指南所在目录已经包含可运行的示例：

```text
map-tiles-stage1/
├─ 第一阶段-GDAL与OpenLayers操作指南.md
├─ prepare_image.py      # 生成测试图，或把照片裁剪为 4096 × 4096
├─ input.png             # 已生成的网格测试图
├─ index.html            # 完整 OpenLayers 页面
├─ preview.png           # 全图展示截图
└─ tiles/                # 已生成的 341 张瓦片
   ├─ 0/
   ├─ 1/
   ├─ 2/
   ├─ 3/
   └─ 4/
```

**想先看效果：完成第 3 节的环境准备，然后直接到第 7 节启动服务。**

**想亲手重做：** 复制 `prepare_image.py` 和 `index.html` 到一个新的空文件夹，按第 4～7 节操作。这样可以保留这套已运行的示例，方便对照。

## 2. 4096 × 4096 图片从哪里找

第一阶段不要求园区照片。风景照、建筑照、手绘图、游戏地图都可以，重点是辨认上下左右和细节。

### 方案 A：先用附带的网格测试图

推荐第一次使用已附带的 `input.png`。它有 16 × 16 个网格，带 `x`、`y` 编号，四角标有 `TOP LEFT`、`TOP RIGHT`、`BOTTOM LEFT`、`BOTTOM RIGHT`，便于判断方向与拼接是否正确。

这张图由附带脚本本地生成，不依赖图片网站；重做时运行第 4 节的命令即可。

### 方案 B：直接获取随机照片

[Lorem Picsum](https://picsum.photos/) 支持通过网址指定图片宽高，也支持固定种子。可以在浏览器打开下面的链接，然后另存为 `original.jpg`：

[请求一张 4096 × 4096 的固定种子照片](https://picsum.photos/seed/tile-demo/4096/4096)

如果希望换一张图片，把网址中的 `tile-demo` 改为 `park-test` 等其他文字。服务访问速度和可用性取决于网络；下载失败时，直接改用方案 A。

网址指定的是输出尺寸，不能保证底层原始照片具有同样的真实细节。下载后仍按第 4 节转换、检查尺寸。

### 方案 C：下载航空照片或使用自己的照片

想让画面更像园区地图，可以从 [Wikimedia Commons 航空照片分类](https://commons.wikimedia.org/wiki/Category:Aerial_photographs) 查找城市、校园或建筑群照片，打开具体图片页，选择原始文件下载。若用于发布或分享，按该图片页面的许可要求署名。

也可以直接用手机照片。原图不必恰好是正方形，第 4 节的脚本会**居中裁剪并缩放到 4096 × 4096**；它会裁掉一部分边缘，小图放大也不会新增细节。第一阶段固定这个尺寸，是为了方便理解瓦片数量和层级关系。

## 3. 准备 GDAL 环境

### 3.1 使用已有的 QGIS 环境

本机已经安装 QGIS，不必再安装独立的 GDAL、Python 或 Node.js。

在 Windows 开始菜单搜索并打开 **OSGeo4W Shell**。如果找不到入口，在文件资源管理器中打开：

```text
C:\Program Files\QGIS 3.44.10\OSGeo4W.bat
```

双击这个文件会打开带有 GDAL 环境的命令窗口。其他电脑的 QGIS 安装目录可能不同，请按实际路径查找。

**下文的命令都在这个窗口中执行，命令语法按 CMD 编写。不要把 Windows 路径或 `set` 命令直接混用到 PowerShell 中。**

逐条运行：

```bat
gdalinfo --version
python --version
gdal raster tile --help
python -c "from PIL import Image; print(Image.__version__)"
```

预期能够看到 GDAL、Python、Pillow 的版本，以及切片工具的帮助。

如果尚未安装 QGIS，可从 [QGIS 官方下载页](https://qgis.org/download/) 安装 Windows 版本，再使用它提供的 OSGeo4W Shell。安装后先检查上述命令，不要假定其捆绑的 GDAL 版本与本机相同。

如果你的 GDAL 没有 `gdal raster tile` 命令，查看第 11 节的传统工具写法。

### 3.2 进入实验目录

使用本指南附带的文件时，执行：

```bat
cd /d "C:\Users\AOC\Desktop\xxj\MyDiy\map-tiles-stage1"
```

如果是在新文件夹里重做，将路径替换为新文件夹的绝对路径。后面的输入文件、页面和瓦片都放在这个实验目录内。

## 4. 准备并检查图片

已有 `input.png` 的附带示例可以跳到第 5 节。

### 4.1 生成网格测试图

在新的实验目录中放入 `prepare_image.py`，然后运行：

```bat
python prepare_image.py
```

程序会生成 `input.png`。为了避免覆盖已有图片，若同名文件已存在，程序会停止；想换图时，先在资源管理器中把旧文件改名，例如 `input-grid.png`。

### 4.2 或者使用下载的照片

把照片放进实验目录，命名为 `original.jpg`，执行：

```bat
python prepare_image.py "original.jpg"
```

结果同样是 `input.png`。脚本会校正照片的 EXIF 方向，转换为 RGB，再居中裁剪和缩放。

`prepare_image.py` 完整内容如下；也可以直接使用附带的同名文件：

```python
"""Create a 4096 x 4096 tile test image, or crop a supplied photo."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


SIZE = 4096
output = Path("input.png")
if output.exists():
    raise SystemExit("input.png already exists. Rename it before running again.")

if len(sys.argv) > 2:
    raise SystemExit('Usage: python prepare_image.py ["original.jpg"]')

if len(sys.argv) == 2:
    with Image.open(sys.argv[1]) as source:
        image = ImageOps.fit(
            ImageOps.exif_transpose(source).convert("RGB"),
            (SIZE, SIZE),
            method=Image.Resampling.LANCZOS,
        )
else:
    image = Image.new("RGB", (SIZE, SIZE), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 32) if font_path.exists() else ImageFont.load_default(size=32)
    large_font = ImageFont.truetype(str(font_path), 88) if font_path.exists() else ImageFont.load_default(size=88)

    for row in range(16):
        for col in range(16):
            x, y = col * 256, row * 256
            color = (70 + col * 8, 75 + row * 8, 155)
            draw.rectangle((x, y, x + 255, y + 255), fill=color, outline="white", width=3)
            draw.text((x + 16, y + 104), f"x={col}, y={row}", font=font, fill="white")

    corners = [
        (0, 0, "TOP LEFT", "#b83232"),
        (3072, 0, "TOP RIGHT", "#256f40"),
        (0, 3840, "BOTTOM LEFT", "#275cb4"),
        (3072, 3840, "BOTTOM RIGHT", "#873ba6"),
    ]
    for x, y, label, color in corners:
        draw.rectangle((x, y, x + 1023, y + 92), fill=color)
        draw.text((x + 12, y + 4), label, font=large_font, fill="white")

image.save(output)
print(f"Saved {output.resolve()} ({image.width} x {image.height})")
```

### 4.3 检查尺寸

```bat
gdalinfo input.png
```

输出应包含：

```text
Size is 4096, 4096
```

还应看到 RGB 三个波段，类型为 `Byte`。普通图片没有真实地理坐标是正常的；这里不需要为它强行指定 EPSG:3857 或 EPSG:4326。

## 5. 用 GDAL 生成瓦片

### 5.1 执行切片

在实验目录运行下面这一整行命令：

```bat
gdal raster tile --tiling-scheme raster --convention xyz --tile-size 256 --min-zoom 0 --max-zoom 4 --resampling average --overview-resampling average --webviewer none --num-threads 1 input.png tiles
```

工具会创建 `tiles` 目录。等进度到 100%，并返回命令提示符后，再进行下一步。

参数含义：

| 参数 | 作用 |
| --- | --- |
| `--tiling-scheme raster` | 按原图片的网格切片，适用于这个无地理配准的实验 |
| `--convention xyz` | 瓦片编号从左上角开始，X 向右、Y 向下 |
| `--tile-size 256` | 每张瓦片宽高均为 256 像素 |
| `--min-zoom 0 --max-zoom 4` | 生成 0、1、2、3、4 共五级 |
| `--resampling average` | 使用平均采样 |
| `--overview-resampling average` | 缩小层级同样使用平均采样 |
| `--webviewer none` | 使用本指南自己的 OpenLayers 页面 |
| `--num-threads 1` | 这个小实验使用单任务处理，方便排错 |
| `input.png tiles` | 输入图片和输出目录 |

以上选项来自 [GDAL 官方切片文档](https://gdal.org/en/stable/programs/gdal_raster_tile.html)。

换了输入图片时，先把旧 `tiles` 目录改名，例如 `tiles-grid`，再生成新的 `tiles`。不要让两张图片的瓦片混在同一个目录里。

### 5.2 查看目录和数量

输出的文件按下面的方式组织：

```text
tiles/{z}/{x}/{y}.png
```

例如：

```text
tiles/0/0/0.png     # 第 0 级：整幅图片的缩略图
tiles/1/0/0.png     # 第 1 级：左上四分之一区域
tiles/1/1/0.png     # 第 1 级：右上四分之一区域
tiles/1/0/1.png     # 第 1 级：左下四分之一区域
tiles/1/1/1.png     # 第 1 级：右下四分之一区域
tiles/4/15/15.png   # 第 4 级：最右下角的 256 × 256 区域
```

对本实验的图片尺寸和切片配置，各级结果应为：

| 层级 z | 该层完整图片尺寸 | 横向 × 纵向瓦片数 | PNG 数量 | 分辨率：原图像素 / 屏幕 CSS 像素 |
| --- | --- | --- | --- | --- |
| 0 | 256 × 256 | 1 × 1 | 1 | 16 |
| 1 | 512 × 512 | 2 × 2 | 4 | 8 |
| 2 | 1024 × 1024 | 4 × 4 | 16 | 4 |
| 3 | 2048 × 2048 | 8 × 8 | 64 | 2 |
| 4 | 4096 × 4096 | 16 × 16 | 256 | 1 |

**总计 341 张 PNG 瓦片。** 各级的每张瓦片本身仍是 256 × 256；变化的是它覆盖的原图范围。

这里的 z=4 表示图片原始分辨率，和全球地图上的 z=4 没有直接对应关系。

## 6. 创建 OpenLayers 展示页面

将下面的内容保存为实验目录中的 `index.html`，与 `tiles` 目录同级。已有附带页面则无需重复创建。

本实验使用官方提供的开发用完整构建，通过固定版本 CDN 引入，不需要 npm 或构建工具。第一次打开页面需要能访问 CDN；参考 [OpenLayers 官方下载说明](https://openlayers.org/download/)。

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>第一阶段：图片瓦片实验</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@10.11.0/ol.css">
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font: 15px/1.6 system-ui, sans-serif; color: #203047; }
    header { padding: 12px 18px; background: #fff; border-bottom: 1px solid #d8e0e8; }
    h1 { margin: 0 0 4px; font-size: 20px; }
    button { padding: 5px 12px; cursor: pointer; }
    #map { height: calc(100dvh - 150px); min-height: 320px; background: #e5eaf0; }
    footer { padding: 10px 18px; }
    #status { margin-left: 12px; }
    #message { color: #975300; }
  </style>
</head>
<body>
  <header>
    <h1>图片瓦片实验 · GDAL + OpenLayers</h1>
    <button id="fit" type="button">显示全图</button>
    <span id="status">正在加载 OpenLayers…</span>
    <div id="message">滚轮缩放，按住鼠标拖动。点击图片可查看原图像素坐标。</div>
  </header>
  <main id="map" aria-label="可缩放和拖动的图片瓦片地图"></main>
  <footer id="point">图片尺寸：4096 × 4096；瓦片尺寸：256 × 256；层级：0～4。</footer>
  <script src="https://cdn.jsdelivr.net/npm/ol@10.11.0/dist/ol.js"></script>
  <script>
    if (typeof ol === 'undefined') {
      document.getElementById('status').textContent = 'OpenLayers 加载失败，请检查 CDN 网络连接。';
      throw new Error('OpenLayers CDN failed to load');
    }

    const imageSize = 4096;
    // OpenLayers 地图坐标：左下角为 [0, 0]，Y 向上。
    const extent = [0, 0, imageSize, imageSize];
    const resolutions = [16, 8, 4, 2, 1];
    const projection = new ol.proj.Projection({
      code: 'IMAGE-PIXELS',
      units: 'pixels',
      extent,
    });

    // 瓦片从左上角编号：X 向右、Y 向下，与 --xyz 对应。
    const tileGrid = new ol.tilegrid.TileGrid({
      extent,
      origin: [0, imageSize],
      resolutions,
      tileSize: 256,
    });

    const source = new ol.source.XYZ({
      projection,
      tileGrid,
      url: './tiles/{z}/{x}/{y}.png',
      wrapX: false,
      transition: 0,
    });

    const view = new ol.View({
      projection,
      extent,
      center: [imageSize / 2, imageSize / 2],
      resolutions,
      zoom: 0,
      constrainResolution: true,
      constrainOnlyCenter: true,
      enableRotation: false,
    });

    const map = new ol.Map({
      target: 'map',
      layers: [new ol.layer.Tile({ source, extent, preload: 0 })],
      view,
    });

    let loaded = 0;
    let failed = 0;
    function updateStatus() {
      const zoom = view.getZoom();
      document.getElementById('status').textContent =
        `层级 ${zoom.toFixed(1)} / 4 · 分辨率 ${view.getResolution().toFixed(2)} · 加载完成 ${loaded} · 失败 ${failed}`;
    }

    source.on('tileloadend', () => { loaded += 1; updateStatus(); });
    source.on('tileloaderror', () => {
      failed += 1;
      document.getElementById('message').textContent =
        '有瓦片加载失败：请检查 tiles 目录、文件路径和浏览器 Network 面板。';
      updateStatus();
    });
    view.on('change:resolution', updateStatus);

    function fitImage() {
      view.fit(extent, { size: map.getSize(), padding: [20, 20, 20, 20], nearest: false });
      updateStatus();
    }
    document.getElementById('fit').addEventListener('click', fitImage);
    map.on('singleclick', (event) => {
      const [x, mapY] = event.coordinate;
      if (x < 0 || x >= imageSize || mapY <= 0 || mapY > imageSize) return;
      const imageX = Math.floor(x);
      const imageY = Math.floor(imageSize - mapY);
      document.getElementById('point').textContent =
        `原图像素坐标（左上角为原点）：x=${imageX}, y=${imageY}；最高级瓦片：4/${Math.floor(imageX / 256)}/${Math.floor(imageY / 256)}.png`;
    });
    fitImage();
  </script>
</body>
</html>
```

### 代码里最需要理解的三个配置

1. `projection`：自定义图片坐标。`IMAGE-PIXELS` 是这个页面内部使用的名称，不是一个 EPSG 编号。
2. `tileGrid`：定义图片范围、瓦片编号起点、瓦片大小和每一级的分辨率。
3. `url: './tiles/{z}/{x}/{y}.png'`：OpenLayers 将算出的 z、x、y 填入这个模板，向服务器请求对应的小图片。

坐标要区分清楚：

| 坐标 | 原点 | Y 方向 |
| --- | --- | --- |
| 原图像素坐标 | 图片左上角 | 向下增加 |
| 本页面的 OpenLayers 地图坐标 | 图片左下角 `[0, 0]` | 向上增加 |
| XYZ 瓦片行列编号 | 瓦片网格左上角 | 行号向下增加 |

因此，瓦片网格的 `origin` 是 `[0, 4096]`，而页面点击位置转换为原图坐标时使用 `imageY = 4096 - mapY`。

分辨率数组 `[16, 8, 4, 2, 1]` 同时用于 View 和 TileGrid，使页面的缩放级别与 GDAL 输出目录保持一致。

OpenLayers 官方依据：[自定义图片投影示例](https://openlayers.org/en/latest/examples/static-image.html)、[TileGrid](https://openlayers.org/en/latest/apidoc/module-ol_tilegrid_TileGrid-TileGrid.html)、[XYZ 数据源](https://openlayers.org/en/latest/apidoc/module-ol_source_XYZ-XYZ.html)、[View](https://openlayers.org/en/latest/apidoc/module-ol_View-View.html)。

## 7. 启动服务并打开页面

在实验目录、同一个 OSGeo4W Shell 窗口中运行：

```bat
python -m http.server 8765 --bind 127.0.0.1
```

窗口会持续运行，暂时不能继续输入普通命令，这是正常现象。保持它打开，在浏览器访问：

[打开本地实验页面](http://127.0.0.1:8765/)

必须通过这个 HTTP 地址访问，不能仅双击 `index.html`。服务以实验目录为根目录，OpenLayers 才能通过相对路径找到 `tiles`。

可单独打开以下地址，检查文件是否能访问：

- [第 0 级全图瓦片](http://127.0.0.1:8765/tiles/0/0/0.png)
- [第 4 级左上角瓦片](http://127.0.0.1:8765/tiles/4/0/0.png)
- [第 4 级右下角瓦片](http://127.0.0.1:8765/tiles/4/15/15.png)

正常情况下，你会看到：

- 图片完整拼接，上下左右方向正确。
- 鼠标滚轮和左上角加减按钮可以缩放，按住鼠标可以拖动。
- 点击“显示全图”可以回到完整图片视野。
- 顶部显示当前层级、分辨率、加载完成数和失败数。
- 点击图片后，底部显示原图像素坐标和对应的最高级瓦片路径。

加载完成数是本次页面会话中的加载完成事件累计值，不代表当前屏幕的瓦片张数，也不是下载进度百分比。

实验结束，在运行服务的窗口按 `Ctrl+C` 停止。服务只绑定本机地址，手机不能直接通过这个地址访问。

## 8. 观察浏览器如何加载瓦片

### 实验一：观察缩放时的层级变化

1. 按 `F12` 打开开发者工具。
2. 切到 **Network / 网络**，在过滤框输入 `.png`。
3. 勾选 **Disable cache / 停用缓存**。这个选项通常在开发者工具打开期间生效。
4. 刷新页面，再逐步放大图片。
5. 观察请求路径中的 `tiles/1/...`、`tiles/2/...`、`tiles/3/...`、`tiles/4/...`。

结论：缩放会改变所需的分辨率，页面随之请求另一层级的瓦片。初始页面会根据窗口大小适配全图，可能从 z=1 或 z=2 开始，不要求先请求 z=0。

### 实验二：观察拖动时的区域变化

1. 放大到 z=4，使窗口只能看到原图的一部分。
2. 记住几个已请求瓦片的 x、y 编号。
3. 按住鼠标拖动到尚未显示过的区域。
4. 观察新的 x、y 请求，z 应保持为 4。

结论：当前区域发生变化时，页面请求相应区域的瓦片。图层可能在可视边缘加载相邻瓦片，拖动和缩放过程中也可能暂时显示已缓存的旧层级瓦片，这些都是正常行为。

浏览器不会因为 `tiles` 中有 341 张图片就一开始全部下载。已经进入 OpenLayers 内存缓存的瓦片，再次拖回时也不一定重新发出 HTTP 请求；即使勾选了停用浏览器缓存，OpenLayers 自身的缓存仍然存在。

### 实验三：从原图位置推导瓦片路径

设原图左上角为原点，点击位置的像素坐标为 `(pixelX, pixelY)`。对于本实验：

```text
resolution(z) = 16 / 2^z
每张瓦片覆盖的原图边长 = 256 × resolution(z)
x = floor(pixelX / 每张瓦片覆盖的原图边长)
y = floor(pixelY / 每张瓦片覆盖的原图边长)
```

以 `(1000, 700)` 为例：

| 层级 | 覆盖原图边长 | 算出的瓦片路径 |
| --- | --- | --- |
| 2 | 1024 像素 | `tiles/2/0/0.png` |
| 3 | 512 像素 | `tiles/3/1/1.png` |
| 4 | 256 像素 | `tiles/4/3/2.png` |

坐标按像素位置处理，有效范围是 `0 ≤ pixelX, pixelY < 4096`。

## 9. 换成自己的照片

建议先完成网格图实验，再换照片：

1. 停止本地服务。
2. 在资源管理器里将 `input.png` 改名为 `input-grid.png`，将 `tiles` 改名为 `tiles-grid`。
3. 将自己的照片放进实验目录，命名为 `original.jpg`。
4. 执行 `python prepare_image.py "original.jpg"`。
5. 用 `gdalinfo input.png` 确认尺寸，再重新执行第 5 节切片命令。
6. 重新启动服务，在浏览器打开开发者工具并停用缓存，执行强制刷新。

因为输入尺寸和瓦片规则仍保持相同，OpenLayers 页面无需修改。

## 10. 常见问题

| 现象 | 检查与处理 |
| --- | --- |
| 找不到 `gdal` 或 `gdalinfo` | 确认使用 OSGeo4W Shell；普通系统 Python 不会自动带上 GDAL 环境 |
| `No module named osgeo_utils` 或 `PIL` | 检查是否误用了另一个 Python；本机已验证 QGIS 自带 Python 具备这两项依赖 |
| `input.png already exists` | 脚本在保护旧图；将旧图改名，或跳过生成步骤 |
| 输入图片尺寸不对 | 运行准备脚本，确认结果为 `Size is 4096, 4096` |
| 图片提示缺少地理参考 | 检查是否遗漏 `--tiling-scheme raster`，不要使用默认全球切片网格处理普通照片 |
| 页面灰白，没有地图 | 先看控制台错误；确认 `ol.js` 成功加载，并打开单张瓦片地址排查 |
| `ol is not defined` / CDN 加载失败 | 检查 CDN 网络连接，或按下文方式改为本地资源 |
| 瓦片请求返回 404 | 确认服务启动于实验目录，`index.html` 与 `tiles` 同级，URL 使用 `/tiles/z/x/y.png` |
| 图片上下错位或拼接异常 | 确认使用 XYZ，前端网格起点为 `[0,4096]`，分辨率数组为 `[16,8,4,2,1]` |
| 拖动时没有新请求 | 可能仍在同一批瓦片范围内，或已命中内存缓存；放到 z=4，再拖到没看过的区域 |
| 换图后仍显示旧内容 | 确认旧瓦片目录已改名，新图已经重新切片；停用浏览器缓存并强制刷新 |
| 放大到 4 级就不能再放大 | 本实验有意将最高级设为原图分辨率；继续放大也不会增加原始细节 |
| 8765 端口被占用 | 将服务命令中的端口改为 8766，浏览器地址同步改为 8766 |

### 临时目录写入失败

如果 GDAL 报错无法在临时目录写入 `.vrt` 等文件，可以在 OSGeo4W Shell 中逐行运行：

```bat
mkdir .tmp
set "TEMP=%CD%\.tmp"
set "TMP=%CD%\.tmp"
```

目录已存在时无需重复创建。然后重新运行切片命令；这些设置只作用于当前命令窗口。附带示例的验证过程中使用过这种方式。

### CDN 访问不稳定，改用本地 OpenLayers 文件

在浏览器分别打开下面两个固定版本链接，并将原始文件下载到实验目录的 `vendor` 文件夹：

- [OpenLayers 10.11.0 JavaScript 文件](https://cdn.jsdelivr.net/npm/ol@10.11.0/dist/ol.js)，保存为 `vendor/ol.js`。
- [OpenLayers 10.11.0 CSS 文件](https://cdn.jsdelivr.net/npm/ol@10.11.0/ol.css)，保存为 `vendor/ol.css`。

然后将 HTML 中的两个引用替换为：

```html
<link rel="stylesheet" href="./vendor/ol.css">
<script src="./vendor/ol.js"></script>
```

保持 CSS 引用在原来的 CSS 位置、脚本引用在原来的脚本位置即可。此后展示不依赖 CDN。

## 11. 对照：传统 gdal2tiles 写法

主流程优先使用第 5 节的新命令。很多旧教程仍然使用 `gdal2tiles`，它在本机 GDAL 3.12.4 中也经过了实际切片验证：

```bat
python -m osgeo_utils.gdal2tiles -p raster --xyz -z 0-4 --tilesize=256 -r average -w none input.png tiles
```

**两种写法选一种执行即可，不要为了完成本实验重复运行两遍。**

传统参数中，`-p raster`、`--xyz`、`-z 0-4` 分别对应图片网格、XYZ 编号和层级范围。

按照 [GDAL 官方迁移说明](https://gdal.org/en/stable/programs/gdal2tiles.html)，从 GDAL 3.13 起，`gdal2tiles` 已弃用并默认转交给新工具。因此本指南以 `gdal raster tile` 为主；使用其他版本时，先查看该版本工具的帮助，避免直接混用新旧参数名称。

## 12. 完成标准与第二阶段衔接

完成以下项目，就可以结束第一阶段：

- [ ] 我能检查输入图片为 4096 × 4096。
- [ ] 我能独立生成 0～4 级、共 341 张 PNG 瓦片。
- [ ] 我能通过 HTTP 地址打开 OpenLayers 页面，完成缩放、拖动和全图展示。
- [ ] 我能从网络面板区分缩放时的 z 变化和拖动时的 x、y 变化。
- [ ] 我能解释为什么不需要一次下载所有瓦片。
- [ ] 我能用一个原图像素坐标算出对应瓦片路径。
- [ ] 我已经成功将网格图换成另一张照片。

本机已验证：GDAL 新旧两种命令均可生成瓦片；各层数量为 1、4、16、64、256；OpenLayers 可显示全图、切换层级、拖动加载新区域，检查时未发生瓦片加载失败或浏览器控制台警告。

第二阶段再加入 QGIS 地理配准、真实坐标参考系与 Cesium 影像覆盖。本阶段生成的图片瓦片不具有真实地理定位，届时需要根据配准结果重新生成适合目标地理网格的瓦片，并让 Cesium 的切片方案与之匹配。
