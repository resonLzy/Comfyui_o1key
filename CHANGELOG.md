# Changelog

所有值得注意的更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-01-10

### 新增
- 图生图节点支持多参考图（最多6张）
  - 新增 `reference_2` 到 `reference_6` 可选输入端口
  - 自动显示所有参考图的数量和分辨率信息
- API调用函数支持批量参考图列表

### 改进
- 参数顺序优化：`image_size`（清晰度）移至必需参数区域
- 简化节点界面和日志输出
- 代码结构优化，提升可维护性

### 移除
- 移除 `batch_size` 参数（文生图和图生图节点）
- 批量处理功能将在下个版本通过专门节点实现

### 技术细节
- `utils.py`: `call_nano_banana_api` 函数参数从 `reference_image_base64` 改为 `reference_images_base64`（列表类型）
- `nodes.py`: 重构图生图和文生图节点逻辑，移除batch循环

## [1.0.0] - 2026-01-09

### 新增
- 初始版本发布
- Nano Banana 文生图节点
- Nano Banana 图生图节点
- 支持 nano-banana-pro-svip 和 nano-banana-svip 模型
- 多种宽高比预设（1:1, 4:3, 3:4, 16:9, 9:16等）
- 清晰度选项（1K, 2K, 4K）
- 种子参数支持
- 优化的日志输出
