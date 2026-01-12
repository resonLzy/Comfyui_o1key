# Changelog

所有值得注意的更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.2.0] - 2026-01-12

### 新增
- 新增 `nano-banana-pro-default` 模型选项，现为默认推荐模型
- 新增 `BatchRequestManager` 批量请求管理器，独立封装限流逻辑
- 批量处理节点新增 `request_interval` 参数，可调节请求间隔（0.5-10秒）
- 新增 `parse_api_error()` 函数，统一处理 API 错误
- 新增 `format_time()` 时间格式化工具函数

### 改进
- **错误提示优化**：将 HTML 错误响应（如 504 Gateway Timeout）转换为用户友好的中文提示
- **批量处理优化**：
  - 智能限流：自动控制请求频率，防止服务器过载
  - 自适应调整：遇到 429 限流错误时自动增加请求间隔
  - 进度预估：实时计算并显示预计完成时间（ETA）
  - 连续失败处理：连续失败 3 次以上自动增加等待时间
- 调整模型列表顺序：`nano-banana-pro-default` > `nano-banana-pro-svip` > `nano-banana-svip`
- 简化日志输出，更清晰的进度展示

### 移除
- 移除测试节点（Gemini3ProImageTest、Gemini3ProSimpleTest、Gemini3ProImageEditTest）
- 移除批量处理的批次暂停参数（batch_pause_size、batch_pause_time）

### 技术细节
- 删除 `nodes/gemini3_test.py` 测试文件
- 新增 `BatchRequestManager` 类到 `utils.py`，封装批量请求的限流、进度追踪和自适应调整逻辑
- 重构批量处理节点，使用 `BatchRequestManager` 管理请求
- 统一错误处理：500/502/503/504/520-524 等错误码都有友好提示
- README 更新：中文优先展示，顶部添加微信联系方式

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
