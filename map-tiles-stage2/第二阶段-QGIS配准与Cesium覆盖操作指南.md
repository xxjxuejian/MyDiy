# 第二阶段：QGIS 地理配准、GeoTIFF 切片与 Cesium 覆盖

## 1. 目标与第一阶段的区别

本阶段将一张真实园区俯视图放到地球上的正确位置：

```text
真实园区图片 + 已知坐标的参考数据
          ↓ QGIS 选择同名控制点并进行地理配准
带坐标参考系和地理范围的 GeoTIFF
          ↓ 检查位置、配准误差和透明边缘
EPSG:3857 GeoTIFF
          ↓ GDAL 生成 WebMercatorQuad / XYZ 瓦片
标准全球网格中的 {z}/{x}/{y}.png
          ↓ Cesium WebMercatorTilingScheme
园区影像覆盖在对应地理位置
```

| 内容 | 第一阶段 | 第二阶段 |
| --- | --- | --- |
| 图片含义 | 任意图片 | 确定地点的真实园区影像 |
| 坐标 | 自定义图片像素 | 真实地理参考 |
| GDAL 切片方案 | `raster` | `WebMercatorQuad` |
| 瓦片编号 | 围绕图片自身编号 | 围绕全球固定网格编号 |
| 层级 | 实验设置为 0～4 | 本次先用全球层级 0～18 |
| 前端 | OpenLayers 自定义图片投影 | Cesium 的 Web Mercator 切片方案 |

**XYZ 规定编号方式，不会自动赋予图片真实坐标。** 位置来自 GeoTIFF 的地理参考；每张瓦片覆盖哪里，则由切片网格决定。Cesium 的 `rectangle` 用于限制覆盖范围，不能用来把第一阶段的任意瓦片平移到园区。

本指南沿用已安装的 QGIS 3.44.10、GDAL 3.12.4 和 Python 3.12.13；Cesium 示例固定使用 1.146。QGIS 菜单以该版本为准，其他版本的文字或位置可能略有不同。

目前尚未提供真实园区图片和控制点，因此本文是操作流程与示例文件，不代表已经完成某个园区的配准。真实位置和误差需要你操作后验收。

## 2. 准备文件和参考数据

### 2.1 园区图片怎么选

第一次建议选择面积较小、地势较平、能清楚辨认道路交叉口与地面角点的园区。

素材优先级：

1. 已有的无人机正射影像：最容易获得稳定的平面对应关系。若本身就是有正确地理参考的 GeoTIFF，可直接从第 6 节检查，跳过配准。
2. 接近垂直拍摄的航拍照片：适合学习，仍可能有镜头和地形造成的变形。
3. 拍摄角度明显倾斜的照片：可以尝试，但建筑立面、遮挡和高差会限制准确性。

图片不要求是 4096 × 4096，也不要求正方形。不要为凑尺寸裁掉有用控制点。需旋转、裁剪或修正手机照片方向时，应在选控制点之前完成；配准后不要再用普通图片编辑器另存来替代 GeoTIFF。

单张照片的二维配准不能恢复被建筑遮挡的地面，也不能自动解决建筑高度和地形起伏导致的位移。明显倾斜的影像通常需要无人机摄影测量与正射处理，不能仅靠增加控制点来保证全图准确。

### 2.2 需要什么参考数据

你必须知道“原图里的某个角点，在真实地理空间中的同一个点在哪里”。可以使用：

- 坐标参考系已知的高质量正射影像或测绘数据。
- 已知 WGS84 / 其他明确坐标系的地面控制点。
- 用于学习的 OpenStreetMap 道路和建筑轮廓，前提是能找到可靠的同名地物。

OSM 参考数据可用于跑通流程，但其精度、更新日期与覆盖情况不保证满足测绘或工程要求。若参考底图不准确，配准结果也会继承偏差。

**特别注意坐标来源：** 高德常用 GCJ-02，不能把拾取到的高德经纬度直接当作 WGS84，也不能仅给它标注 EPSG:4326 就认为完成了转换。初次实验尽量采用坐标来源明确的数据，不混用不同地图体系。参考：[高德官方坐标说明](https://lbs.amap.com/api/javascript-api-v2/guide/transform/convertfrom)。

### 2.3 目录安排

本指南和配套脚本已放在：

```text
C:\Users\AOC\Desktop\xxj\MyDiy\map-tiles-stage2
```

建议文件结构如下；带“操作后生成”的文件需要你完成相应步骤后才会出现：

```text
map-tiles-stage2/
├─ 第二阶段-QGIS配准与Cesium覆盖操作指南.md
├─ make_config.py          # 已附带：读取范围并生成前端配置
├─ index.html              # 已附带：Cesium 展示页面
├─ park_original.jpg       # 你准备的园区图片，也可以是 PNG
├─ park_original.jpg.points # 配准时保存的控制点，名称可能不同
├─ park_project.qgz        # 保存的 QGIS 工程
├─ park_georef.tif         # QGIS 配准输出，操作后生成
├─ park_3857.tif           # 规范化后的切片输入，操作后生成
├─ config.json             # 脚本生成的范围和层级配置
├─ tile-plan.txt           # 脚本生成的瓦片数量估算
└─ tiles/                  # GDAL 输出的地理瓦片
```

## 3. 在 QGIS 中准备参考地图

### 3.1 创建工程并设置坐标系

1. 打开 QGIS，新建工程。
2. 点击右下角的坐标参考系按钮，在工程坐标参考系中搜索 `3857`。
3. 选择 **WGS 84 / Pseudo-Mercator — EPSG:3857**。
4. 保存工程为 `park_project.qgz`。

本指南统一使用 EPSG:3857 作为目标坐标系，便于后续与全球 Web Mercator 网格对齐。它的坐标单位是投影米，不能直接当作经纬度，也不能把其中的距离不加修正地当作精确地面距离。

### 3.2 加载参考数据

如果你有自己的参考 GeoTIFF、道路或地块数据，拖入 QGIS，并确认图层的原始坐标参考系正确；QGIS 可以将它动态显示在工程坐标系中。

若用 OSM 学习：

1. 打开“浏览器 / Browser”面板；若未显示，在“视图 → 面板”中启用。
2. 展开 **XYZ Tiles / XYZ 瓦片**。
3. 双击 **OpenStreetMap**。
4. 缩放、移动到目标园区。

如果没有预置条目，在 XYZ Tiles 上右键新建连接，填写：

```text
名称：OpenStreetMap
URL：https://tile.openstreetmap.org/{z}/{x}/{y}.png
```

首次仅进行少量交互查看；网络不可访问时改用本地参考影像，不影响后续地理配准原理。

## 4. 用 QGIS 地理配准器建立控制点

### 4.1 打开原图和设置

1. 在菜单中打开 **图层 → 地理配准器 / Layer → Georeferencer**。
2. 在地理配准器窗口点击“打开栅格”，选择 `park_original.jpg`。
3. 打开“变换设置 / Transformation settings”，先按第 5 节填写目标坐标系和输出文件；这样便于统一理解后面的目标点坐标。

QGIS 3.44 的入口在“图层”菜单；部分旧教程将其写在“栅格”菜单中。操作依据：[QGIS 3.44 地理配准器文档](https://docs.qgis.org/3.44/en/docs/user_manual/managing_data_source/georeferencer.html)。

### 4.2 选取 6～10 个清晰的控制点

控制点是原图和参考图上能够识别为**同一个实际位置**的点。优先选：

- 地面道路交叉点或铺装边缘拐角。
- 清晰、稳定的围墙或地块地面角点。
- 已知坐标的地面标志。

避免选树冠、阴影边缘、车辆等可能变化的对象。倾斜照片中也不要用屋顶角点冒充建筑在地面的角点。

点位应覆盖四周和中间，避免全部集中在同一边或近似排成一条直线。另保留 2～3 个分散位置的点作为独立检查点，先不加入拟合。

### 4.3 从地图画布取得目标坐标

每一个点都按以下顺序操作：

1. 在地理配准器中点击“添加控制点”。
2. 放大原图，精确点击所选地物。
3. 在弹出的坐标窗口中选择 **从地图画布 / From map canvas**。
4. 在 QGIS 主地图上找到相同地物，点击完全相同的位置。
5. 确认坐标和该点的 CRS 后保存。
6. 重复，直到完成第一轮控制点。

这里取到的目标坐标通常是工程中的 EPSG:3857 坐标，即较大的投影数值，而不是 `120, 30` 一类的经纬度。

如果手工输入经纬度，必须将该点的坐标系明确设为 EPSG:4326，并按 X=经度、Y=纬度输入；不要在 EPSG:3857 的输入框里直接填写经纬度。

完成后使用“保存控制点为”保存 `.points` 文件，便于之后修正和重做。QGIS 工程文件不能替代控制点文件。

## 5. 设置变换并导出 GeoTIFF

### 5.1 推荐第一轮设置

| 选项 | 建议值 | 说明 |
| --- | --- | --- |
| 变换类型 | Polynomial 1 / 一阶多项式 | 适合先处理较接近正射的图像，可拟合平移、旋转、缩放和剪切 |
| 重采样 | Bilinear / 双线性 | 适合连续色彩照片 |
| 目标 CRS | EPSG:3857 | 与后续 Web Mercator 网格一致 |
| 输出栅格 | 本实验目录的 `park_georef.tif` | 输出为 GeoTIFF |
| 仅创建世界文件 | 不选 | 需要实际导出的地理栅格 |
| 目标分辨率 | 第一轮不手填 | 先使用自动计算结果，避免盲目设成极小数值 |
| 创建选项 | 可使用 `COMPRESS=LZW` | 无损压缩，若界面不熟悉也可以先保持默认 |
| Use 0 for transparency when needed | 启用，并检查输出 Alpha | 用于处理配准后影像外部空白；最终以输出掩膜和 Alpha 为准 |
| 保存控制点 | 选中 | 保存配准依据 |
| 完成后加载到工程 | 选中 | 立即检查与参考图的叠加效果 |

一阶多项式数学上至少需要 3 个控制点，本实验使用更多点来发现误选和局部误差。若照片有明显平面透视变化，可尝试 Projective / 投影变换，数学上至少需要 4 点；它仍不能校正不同建筑高度产生的全部位移。

不要为追求控制点处误差接近 0 就直接使用高阶多项式或 TPS。它们可能把控制点之间或图像边缘拉弯。先检查点是否选对、分布是否合理，以及图像是否适合二维配准。

### 5.2 执行并初步查看

1. 点击“开始地理配准”。
2. 等待输出完成，并确认 `park_georef.tif` 已加载到主工程中。
3. 将影像不透明度调为约 50%，或者反复勾选、关闭图层。
4. 检查道路、地面拐角等是否与参考数据重合。

配准以后 GeoTIFF 的宽高可能变化，不必再保持 4096 × 4096。旋转或投影变换后的外接矩形中出现透明三角区，也是正常现象。

## 6. 先验收配准，再切片

### 6.1 查看残差并用独立点检查

在地理配准器的控制点表中检查残差：如果某一个点明显大于其他点，回到两张图检查它是否确为同一位置。

残差显示单位可以是像素或地图单位，应先确认；目标 CRS 为 EPSG:3857 时，地图单位也不等于所有纬度下的真实地面米。

检查时至少做两件事：

1. 观察用于拟合的控制点残差，排除明显误选点。
2. 在 QGIS 主地图中检查预留的 2～3 个独立点，以及四角、中心位置，不只检查已用于拟合的点。

只有最少数量控制点时，数学拟合残差可能接近 0，这不能证明整幅图准确。也不要把地图底图的视觉重合直接当作工程测量精度证明。

学习阶段可以先要求：道路与地块没有明显整体偏移、独立点没有显著局部错位。若最终要用于设备定位或测距，应先明确可接受的实际误差，再用足够准确的地面检查点验收。

### 6.2 在 OSGeo4W Shell 中检查 GeoTIFF

开始菜单打开 OSGeo4W Shell；也可以打开本机文件：

```text
C:\Program Files\QGIS 3.44.10\OSGeo4W.bat
```

后面的命令按 CMD 语法编写，都在这个窗口中逐条执行：

```bat
cd /d "C:\Users\AOC\Desktop\xxj\MyDiy\map-tiles-stage2"
gdalinfo park_georef.tif
```

应看到：

- 驱动为 `GTiff/GeoTIFF`。
- 坐标参考系为 EPSG:3857 对应的 WGS 84 / Pseudo-Mercator。
- 存在真实的 `Origin`、`Pixel Size` 和角点坐标。
- RGB 波段为 `Byte`，透明处理正确时还应有 `ColorInterp=Alpha` 波段。

**仅仅扩展名是 `.tif` 不代表它具有正确地理参考。** 单纯给图片“指定 EPSG:3857”也不会创建有效的控制点对应关系。

### 6.3 规范化为切片输入

确认位置正确后，执行：

```bat
gdalwarp -t_srs EPSG:3857 -r bilinear -dstalpha -co COMPRESS=LZW -co TILED=YES park_georef.tif park_3857.tif
gdalinfo park_3857.tif
```

这一步把已有正确地理参考的数据规范化为北向上的 EPSG:3857 GeoTIFF，并保留或建立输出 Alpha 波段。首次运行使用新的输出文件名；需要重做时先将旧输出改名，避免误用旧结果。

如果输入本来就是可信的其他坐标系 GeoTIFF，也可以通过这一步重投影；前提是其源坐标系正确。**重投影**和“更改 CRS 标签”是不同操作。

### 6.4 透明边缘必须单独检查

将 `park_3857.tif` 加到 QGIS，确认图像外部没有不透明黑色三角区，且影像内部的暗色道路和阴影没有异常缺口。

`-dstalpha` 根据输入中已有的有效范围 / NoData 掩膜建立透明度。若前一步已把外部黑边写成了普通有效 RGB 像素，仅在这个文件上增加 Alpha 并不能自动识别哪些黑色属于背景。

若仍有黑边，回到地理配准器，检查透明设置并重新输出；可查看“生成 GDAL 脚本”中的 `gdalwarp` 步骤是否包含 `-dstalpha`。对于需要保留的纯黑内容，不要随意用 `-srcnodata 0` 将所有黑色统一挖空；应在真正的配准变换时生成 Alpha，或使用准确的有效区掩膜。

参考：[GDAL 重投影与 Alpha 文档](https://gdal.org/en/stable/programs/gdalwarp.html)。

## 7. 自动生成 Cesium 范围配置，并估算瓦片数量

### 7.1 先使用 0～18 级

先跑通显示，再根据原图细节提高到 19 或 20 级。全球 Web Mercator 的级别越大，瓦片越多，生成与存储成本也越高。

| 全球层级 | 赤道附近每像素约代表 | 纬度 30° 附近每像素约代表 |
| --- | --- | --- |
| 18 | 0.60 米 | 0.52 米 |
| 19 | 0.30 米 | 0.26 米 |
| 20 | 0.15 米 | 0.13 米 |

以上按 256 像素瓦片和球面 Web Mercator 近似计算，只用于理解缩放选择，不代表影像本身有同等精度。

本教程从 z=0 生成，是为了让 Cesium 的最低层级与数据完整匹配。它只生成覆盖该影像地理范围的瓦片，不会生成整个地球在 0～18 级的全部瓦片。低层级瓦片中的园区可能只占很小一部分，这是正常现象。

### 7.2 运行附带脚本

```bat
python make_config.py park_3857.tif --max-zoom 18
```

脚本会检查图片坐标系、方向与类型，读取地理范围，将其转换成 **WGS84 经度、纬度**，并生成：

- `config.json`：Cesium 使用的范围、URL 模板和层级。
- `tile-plan.txt`：各层矩形覆盖的瓦片数量估算。

打开 `tile-plan.txt`，先看范围是否确实在园区附近，数量是否符合预期。异常巨大的输出应先检查配准范围和目标分辨率，不要直接生成。

脚本用于普通、北向上、小范围的 EPSG:3857 RGB / RGBA Byte 影像，不覆盖跨日期变更线、极区或专业多光谱数据处理。

`make_config.py` 完整代码如下，已另附同名文件：

```python
"""Read a north-up EPSG:3857 GeoTIFF and prepare the Cesium tile config."""

import argparse
import json
import math
from pathlib import Path

from osgeo import gdal, osr


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("geotiff", nargs="?", default="park_3857.tif")
parser.add_argument("--max-zoom", type=int, default=18)
args = parser.parse_args()
if not 0 <= args.max_zoom <= 22:
    parser.error("--max-zoom must be between 0 and 22")

gdal.UseExceptions()
dataset = gdal.Open(args.geotiff)
source_srs = dataset.GetSpatialRef()
mercator = osr.SpatialReference()
mercator.ImportFromEPSG(3857)
mercator.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
if source_srs is None:
    raise SystemExit("Missing CRS. Complete georeferencing before continuing.")
source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
if not source_srs.IsSame(mercator):
    raise SystemExit("Expected EPSG:3857. Reproject with gdalwarp, not gdal_edit.")

gt = dataset.GetGeoTransform()
if abs(gt[2]) > 1e-10 or abs(gt[4]) > 1e-10 or gt[1] <= 0 or gt[5] >= 0:
    raise SystemExit("Expected a north-up raster. Normalize it with gdalwarp first.")
if dataset.RasterCount not in (3, 4) or any(
    dataset.GetRasterBand(i).DataType != gdal.GDT_Byte
    for i in range(1, dataset.RasterCount + 1)
):
    raise SystemExit("This example expects an RGB or RGBA Byte image.")

xmin, ymax = gt[0], gt[3]
xmax = xmin + dataset.RasterXSize * gt[1]
ymin = ymax + dataset.RasterYSize * gt[5]
world_half = math.pi * 6378137.0
if not (-world_half < xmin < xmax < world_half and -world_half < ymin < ymax < world_half):
    raise SystemExit("Outside the supported local Web Mercator extent.")

wgs84 = osr.SpatialReference()
wgs84.ImportFromEPSG(4326)
wgs84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
transform = osr.CoordinateTransformation(source_srs, wgs84)
west, south, east, north = transform.TransformBounds(xmin, ymin, xmax, ymax, 21)

config = {
    "bounds": [west, south, east, north],
    "minimumLevel": 0,
    "maximumLevel": args.max_zoom,
    "url": "./tiles/{z}/{x}/{y}.png",
    "credit": "Local park image — replace with the actual image source",
}
Path("config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

lines = [
    f"Source: {args.geotiff}",
    f"Raster size: {dataset.RasterXSize} x {dataset.RasterYSize}",
    f"Projected pixel size: {gt[1]:.6f} x {abs(gt[5]):.6f} Web Mercator units",
    f"WGS84 bounds [west, south, east, north]: {config['bounds']}",
    "z: estimated rectangular tile count",
]
total = 0
for z in range(args.max_zoom + 1):
    span = 2 * world_half / (2**z)
    left = max(0, math.floor((xmin + world_half) / span))
    right = min(2**z - 1, math.ceil((xmax + world_half) / span) - 1)
    top = max(0, math.floor((world_half - ymax) / span))
    bottom = min(2**z - 1, math.ceil((world_half - ymin) / span) - 1)
    count = (right - left + 1) * (bottom - top + 1)
    total += count
    lines.append(f"{z}: {count} (x={left}..{right}, y={top}..{bottom})")
lines.append(f"Total estimate: {total}")
if not any(
    dataset.GetRasterBand(i).GetColorInterpretation() == gdal.GCI_AlphaBand
    for i in range(1, dataset.RasterCount + 1)
):
    lines.append("WARNING: No alpha band. Check transparent edges before tiling.")
if total > 10000:
    lines.append("Large output: lower --max-zoom or reduce the geographic coverage first.")
report = "\n".join(lines) + "\n"
Path("tile-plan.txt").write_text(report, encoding="utf-8")
print(report)
print("Created config.json and tile-plan.txt. Keep GDAL zoom options consistent with config.json.")
```

`config.json` 中 `bounds` 的顺序是：

```text
[west, south, east, north]
[西经度界, 南纬度界, 东经度界, 北纬度界]
```

这里都是角度数值；不要把 GeoTIFF 中的 EPSG:3857 投影米直接填入 `Cesium.Rectangle.fromDegrees()`。脚本已设置 GDAL 的坐标轴顺序，按经度、纬度输出。

请将生成配置里的 `credit` 改为影像的真实来源或署名要求。它只是文字说明，不参与地理定位。

## 8. 生成标准 Web Mercator XYZ 瓦片

执行一整行：

```bat
gdal raster tile --tiling-scheme WebMercatorQuad --convention xyz --tile-size 256 --min-zoom 0 --max-zoom 18 --resampling bilinear --overview-resampling average --format PNG --add-alpha --webviewer none --num-threads 1 park_3857.tif tiles
```

与第一阶段相比，最关键的是将 `--tiling-scheme raster` 改成 **`--tiling-scheme WebMercatorQuad`**，且输入已经具有正确地理参考。

| 参数 | 本阶段的意义 |
| --- | --- |
| `WebMercatorQuad` | EPSG:3857 的全球固定网格，z=0 为一张全球瓦片 |
| `--convention xyz` | X 向右、Y 向下，与 Cesium 的 `{y}` 对应 |
| `--min-zoom 0 --max-zoom 18` | 与 `config.json` 中的层级保持一致 |
| `--format PNG --add-alpha` | 输出支持透明度的瓦片 |
| `--resampling bilinear` | 用于最高输出层级 |
| `--overview-resampling average` | 用于较低层级的缩小采样 |
| `--webviewer none` | 使用本指南的 Cesium 页面 |

不要额外添加 `--skip-blank`，先保留范围内的透明瓦片，减少透明区域请求不存在文件造成的 404。

标准目录仍是 `tiles/{z}/{x}/{y}.png`，但 x、y 是全球编号，通常不再从 0 连续排到十几。比如 z=18 的某个园区可能出现在较大的行列号目录中，这是预期结果。

第二阶段的瓦片总数由地理范围、纬度、层级与网格交叉位置决定，**不再固定为 341 张**。

若需要对照旧教程，GDAL 3.12 可使用以下传统命令，二选一执行即可：

```bat
python -m osgeo_utils.gdal2tiles -p mercator --xyz -z 0-18 --tilesize=256 -r average -w none park_3857.tif tiles
```

新旧参数名不要混用。从 GDAL 3.13 起传统工具已弃用，优先使用本节主命令。参考：[GDAL 新切片工具](https://gdal.org/en/stable/programs/gdal_raster_tile.html)、[传统工具迁移说明](https://gdal.org/en/stable/programs/gdal2tiles.html)。

## 9. 用 Cesium 加载影像

### 9.1 页面方案

本指南的页面使用：

- 本地生成的 `config.json` 与 `tiles`。
- Cesium 的 `WebMercatorTilingScheme`，与 GDAL 的 WebMercatorQuad 对齐。
- 程序绘制的全球网格底图，避免将局部园区影像误当作唯一的全球底图。
- 椭球地形，先检查水平位置。
- 可选的 OSM 参考图，用于交互比对。

这套最小示例没有启用 Cesium ion 世界影像、世界地形或地理搜索，因此无需 ion Token。Cesium 本身通过固定版本官方 CDN 加载，首次运行仍需要网络。

园区图片是铺在地球表面的**二维影像图层**，不会自动变成立体建筑，也不是 3D Tiles 模型。

### 9.2 完整页面

将下面内容保存为与 `config.json`、`tiles` 同级的 `index.html`，也可以直接使用附带页面：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>第二阶段：园区地理瓦片覆盖</title>
  <link rel="icon" href="data:,">
  <script>window.CESIUM_BASE_URL = 'https://cesium.com/downloads/cesiumjs/releases/1.146/Build/Cesium/';</script>
  <link rel="stylesheet" href="https://cesium.com/downloads/cesiumjs/releases/1.146/Build/Cesium/Widgets/widgets.css">
  <style>
    html, body, #cesiumContainer { width: 100%; height: 100%; margin: 0; overflow: hidden; }
    body { font: 14px/1.7 system-ui, sans-serif; }
    #panel { position: absolute; z-index: 2; top: 12px; left: 12px; max-width: min(440px, calc(100vw - 48px)); padding: 14px; color: #edf3ff; background: #15233bee; border-radius: 8px; }
    h1 { font-size: 18px; margin: 0 0 8px; }
    button { cursor: pointer; padding: 5px 12px; }
    #status { margin-top: 8px; overflow-wrap: anywhere; }
    label { display: block; margin: 6px 0; }
  </style>
</head>
<body>
  <div id="cesiumContainer"></div>
  <section id="panel">
    <h1>园区地理瓦片覆盖</h1>
    <button id="locate" disabled>定位园区</button>
    <label><input id="visible" type="checkbox" checked disabled>显示园区影像</label>
    <label>影像不透明度 <input id="opacity" type="range" min="0" max="1" step="0.05" value="0.85" disabled></label>
    <label><input id="osm" type="checkbox" disabled>显示 OSM 参考底图（需要联网）</label>
    <div id="status">正在加载 Cesium 和 config.json…</div>
  </section>
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.146/Build/Cesium/Cesium.js"></script>
  <script>
    async function main() {
      if (typeof Cesium === 'undefined') throw new Error('Cesium 加载失败，请检查 CDN 网络连接。');
      const response = await fetch('./config.json');
      if (!response.ok) throw new Error('找不到 config.json，请先运行 make_config.py。');
      const config = await response.json();
      const rectangle = Cesium.Rectangle.fromDegrees(...config.bounds);

      // 程序生成的全球网格底图与椭球地形均不需要 ion Token。
      // 保留全球底图，使局部园区图层始终作为覆盖层使用。
      const viewer = new Cesium.Viewer('cesiumContainer', {
        baseLayerPicker: false,
        baseLayer: new Cesium.ImageryLayer(new Cesium.GridImageryProvider({
          cells: 8,
          backgroundColor: Cesium.Color.fromCssColorString('#17304a'),
          color: Cesium.Color.WHITE.withAlpha(0.15),
          glowWidth: 0,
        })),
        terrainProvider: new Cesium.EllipsoidTerrainProvider(),
        geocoder: false,
        animation: false,
        timeline: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        requestRenderMode: true,
      });
      const provider = new Cesium.UrlTemplateImageryProvider({
        url: config.url,
        tilingScheme: new Cesium.WebMercatorTilingScheme(),
        rectangle,
        minimumLevel: config.minimumLevel,
        maximumLevel: config.maximumLevel,
        tileWidth: 256,
        tileHeight: 256,
        hasAlphaChannel: true,
        enablePickFeatures: false,
        credit: config.credit,
      });
      const overlay = viewer.imageryLayers.addImageryProvider(provider);
      overlay.alpha = 0.85;

      const status = document.getElementById('status');
      status.textContent = `范围（西、南、东、北）：${config.bounds.map(v => v.toFixed(6)).join(', ')}；层级 ${config.minimumLevel}～${config.maximumLevel}。默认网格底图用于检查加载，配准精度需对照参考数据。`;
      provider.errorEvent.addEventListener(error => {
        status.textContent = `园区瓦片加载失败：${error.message}。请检查 Network 面板和文件路径。`;
      });
      function locate() {
        viewer.camera.flyTo({ destination: rectangle, duration: 1.2 });
      }
      document.getElementById('locate').addEventListener('click', locate);
      document.getElementById('visible').addEventListener('change', event => {
        overlay.show = event.target.checked;
        viewer.scene.requestRender();
      });
      document.getElementById('opacity').addEventListener('input', event => {
        overlay.alpha = Number(event.target.value);
        viewer.scene.requestRender();
      });

      let osmLayer;
      document.getElementById('osm').addEventListener('change', event => {
        if (event.target.checked && !osmLayer) {
          const osmProvider = new Cesium.OpenStreetMapImageryProvider({
            url: 'https://tile.openstreetmap.org/',
            maximumLevel: 19,
            credit: new Cesium.Credit('<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'),
          });
          osmProvider.errorEvent.addEventListener(() => {
            status.textContent = 'OSM 底图加载失败，可以关闭它并使用本地参考数据检查。';
          });
          osmLayer = viewer.imageryLayers.addImageryProvider(osmProvider, 1);
        }
        if (osmLayer) osmLayer.show = event.target.checked;
        viewer.scene.requestRender();
      });
      for (const id of ['locate', 'visible', 'opacity', 'osm']) document.getElementById(id).disabled = false;
      locate();
      // 用于学习时在浏览器控制台检查，不参与瓦片定位。
      window.demo = { viewer, provider, overlay, rectangle, config };
    }
    main().catch(error => {
      document.getElementById('status').textContent = error.message;
      console.error(error);
    });
  </script>
</body>
</html>
```

实现依据：[Cesium Quickstart](https://cesium.com/learn/cesiumjs-learn/cesiumjs-quickstart/)、[URL 模板影像提供器](https://cesium.com/learn/cesiumjs/ref-doc/UrlTemplateImageryProvider.html)、[WebMercatorTilingScheme](https://cesium.com/learn/cesiumjs/ref-doc/WebMercatorTilingScheme.html)、[Viewer](https://cesium.com/learn/cesiumjs/ref-doc/Viewer.html)。

### 9.3 启动本地服务

在实验目录的 OSGeo4W Shell 中执行：

```bat
python -m http.server 8766 --bind 127.0.0.1
```

保持窗口运行，在浏览器访问：

[打开第二阶段本地页面](http://127.0.0.1:8766/)

本阶段使用 8766，避免与第一阶段的 8765 混淆。不要直接双击 HTML；页面需要通过 HTTP 读取配置和瓦片。

数据完成后，点击“定位园区”会飞到 GeoTIFF 对应的范围。鼠标可以拖动地球和缩放；可以开关园区影像、调节透明度，再选择是否开启 OSM 底图。

如果还没有生成 `config.json`，页面会明确提示缺少配置，此时应回到第 7 节。

## 10. 在 Cesium 中验收

### 10.1 检查加载是否正确

1. `F12` 打开 Network / 网络面板，过滤 `.png`。
2. 点击“定位园区”，确认请求指向本地 `/tiles/{z}/{x}/{y}.png`。
3. 缩放时应出现不同的 z；平移时应出现不同的 x、y。
4. 确认园区图层没有持续的 404，透明边缘没有黑色矩形遮挡。
5. 检查页面显示的经纬度范围与真实园区所在区域一致。

Cesium 根据相机距离与屏幕误差选择瓦片级别，不必要求“某个相机高度一定请求某一级”。最大级别之外可以继续靠近，但不会增加原图细节。

### 10.2 检查真实位置

默认网格底图只证明“数据能显示在给定经纬度位置”，不能证明配准准确。位置验收需要可靠参考：

1. 若 QGIS 中使用 OSM 配准，Cesium 可开启 OSM，并降低园区影像透明度，检查道路和地面角点。
2. 在影像四周和中心检查多个地物，特别是未参与拟合的独立检查点。
3. 若有地面点的 WGS84 坐标，可在浏览器控制台添加一个核对标记：

```js
// 将示意变量替换为这个检查点的真实 WGS84 经度、纬度。
const checkLon = 你的经度;
const checkLat = 你的纬度;
demo.viewer.entities.add({
  position: Cesium.Cartesian3.fromDegrees(checkLon, checkLat, 0),
  point: { pixelSize: 10, color: Cesium.Color.YELLOW },
  label: { text: '独立检查点', pixelOffset: new Cesium.Cartesian2(0, -20) },
});
demo.viewer.scene.requestRender();
```

上面的经纬度是需要替换的占位内容，不能原样执行。若真实数据来自其他坐标体系，先使用准确的方法转换到 WGS84。

### 10.3 区分三类错误

| 现象 | 优先排查 |
| --- | --- |
| QGIS 和 Cesium 都整体偏移 | 控制点、参考数据精度与坐标体系 |
| QGIS 正确，Cesium 却错位或倒置 | Web Mercator / Geographic 网格是否混用、XYZ / TMS 是否混用 |
| 中心接近正确、边缘明显偏离 | 控制点分布、模型适用性、透视、地形或建筑高度 |

## 11. 常见问题与重做方法

| 问题 | 处理 |
| --- | --- |
| 找不到地理配准器 | QGIS 3.44 从“图层 → 地理配准器”进入，也可通过定位器搜索 Georeferencer |
| 只能生成世界文件，不能设置输出影像 | 检查是否选成 Linear；本指南先选 Polynomial 1，并关闭仅创建世界文件 |
| 手工输入后跑到错误国家或海上 | 检查经纬度顺序、点的 CRS，避免将经纬度当成投影米 |
| `make_config.py` 提示不是 EPSG:3857 | 先正确重投影，不能只修改 CRS 标签来通过检查 |
| 脚本提示图片类型不符合 | 本例面向 RGB / RGBA Byte；专业影像要先明确渲染和数值缩放，不能直接丢掉波段 |
| 生成了非常多瓦片 | 检查配准范围、输出像素大小和最高级别，先用 18 级 |
| 页面没有任何园区图 | 先检查 config.json，再检查本地瓦片路径、加载错误和相机范围 |
| 很多 404 | 配置层级要与真实目录一致；确认旧图未混入，且没有跳过透明瓦片 |
| 图片上下颠倒或行号不对 | 主流程使用 XYZ 和 `{y}`；TMS 才需要 `{reverseY}`，不要两边同时翻转 |
| 图层覆盖到了整个地球 | 检查是否删掉了全球网格底图；局部影像应作为覆盖层 |
| 黑边、透明孔洞 | 检查 GeoTIFF 的 Alpha / NoData，不要统一把照片里的黑色当作无效值 |
| 不提示 Token，却出现 ion 认证请求 | 检查是否恢复了 Viewer 的默认底图、世界地形或搜索，本示例已明确关闭这些默认服务 |
| OSM 加载失败 | 可关闭 OSM，用本地参考数据在 QGIS 中检查位置，不影响本地园区瓦片的加载 |
| CESIUM_BASE_URL / Workers / Assets 请求失败 | 固定版本的整个 Cesium 运行资源必须可访问，不仅是 Cesium.js |
| 换图后仍显示旧瓦片 | 将旧 tiles 目录改名，重新生成，重跑配置脚本并强制刷新浏览器 |

### 提高到 19 或 20 级

先停止服务，并把旧 `tiles` 目录改名，例如 `tiles-z18`，保留对照。以 20 级为例：

```bat
python make_config.py park_3857.tif --max-zoom 20
gdal raster tile --tiling-scheme WebMercatorQuad --convention xyz --tile-size 256 --min-zoom 0 --max-zoom 20 --resampling bilinear --overview-resampling average --format PNG --add-alpha --webviewer none --num-threads 1 park_3857.tif tiles
python -m http.server 8766 --bind 127.0.0.1
```

第一条命令后先查看新的 `tile-plan.txt`，确认数量合理，再执行切片。提高层级只提高采样密度，不会让模糊照片变清晰。

### 临时目录无法写入

若切片工具提示不能写临时文件，在当前 OSGeo4W Shell 中运行：

```bat
mkdir .tmp
set "TEMP=%CD%\.tmp"
set "TMP=%CD%\.tmp"
```

然后重试。目录已经存在时无需重复创建。结束服务使用 `Ctrl+C`。

### 需要离线使用 Cesium

从 [Cesium 官方下载入口](https://cesium.com/downloads/) 获取相应版本，将完整的 `Build/Cesium` 目录放在本地 `vendor/Cesium/`。不要只复制单个 JS：还需要 `Assets`、`Workers`、`Widgets`、`ThirdParty` 等运行资源。

将 `CESIUM_BASE_URL` 改为 `./vendor/Cesium/`，JS 和 CSS 引用分别改为 `./vendor/Cesium/Cesium.js`、`./vendor/Cesium/Widgets/widgets.css`。使用本地网格底图并关闭 OSM 后，园区展示可不依赖在线底图。

## 12. 本阶段完成标准

- [ ] 已确认原图地点和参考数据的坐标体系。
- [ ] 已保存 QGIS 工程与 `.points` 控制点文件。
- [ ] 已导出具有正确地理参考的 GeoTIFF。
- [ ] 已用独立点和边缘位置检查配准结果。
- [ ] 已检查透明边缘，未破坏影像内部有效内容。
- [ ] 已得到北向上的 EPSG:3857 RGB / RGBA Byte 切片输入。
- [ ] 已查看瓦片数量估算，再生成对应的全球 XYZ 瓦片。
- [ ] Cesium 能定位园区、显示图层并正常缩放加载。
- [ ] Cesium 中的相同地物与可靠参考重合，没有持续加载错误。

第一阶段掌握后，再按本指南操作即可。配准质量由真实素材、控制点与参考数据决定，示例页面本身不会改善这部分精度。

### 配套文件的验证范围

已使用具有已知地理范围的测试影像检查 `gdalwarp`、范围配置脚本和 0～18 级切片命令：实际生成 93 张瓦片，与估算一致；Cesium 1.146 页面可加载该覆盖层，检查时没有控制台警告或错误，也没有请求 ion 服务。

这些检查验证的是命令与页面之间的衔接，不包含真实园区的 QGIS 控制点采集、配准残差和地面精度。后者需要你提供实际影像和参考数据，再按第 6、10 节完成。
