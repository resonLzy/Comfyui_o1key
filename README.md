# Comfyui_o1key

> 📱 **微信联系：qin1se**

[中文](#中文) | [English](#english)

---

## 中文

ComfyUI 插件，集成 Nano Banana 图像生成 API，提供文生图和图生图功能。

### 功能特性

🎨 **双生成模式**
- 文生图：从文本提示生成图像
- 图生图：使用文本引导转换现有图像（支持最多6张参考图）

🚀 **高级功能**
- 三种模型选择：
  - `nano-banana-pro-default`（默认推荐）- 稳定高质量
  - `nano-banana-pro-svip` - 超高质量 Pro 版
  - `nano-banana-svip` - 高速高质量
- 10种宽高比：1:1, 4:3, 3:4, 16:9, 9:16, 2:3, 3:2, 4:5, 5:4, 21:9
- 图像尺寸控制：1K、2K、4K（Pro模型）
- 自动重试机制（指数退避，3次尝试）
- 完善的错误处理
- 失败不扣费保障
- 批量处理节点

### 安装方法

1. 进入 ComfyUI 的 custom_nodes 目录：
```bash
cd ComfyUI/custom_nodes/
```

2. 克隆此仓库：
```bash
git clone https://github.com/yourusername/Comfyui_o1key.git
```

3. 安装依赖：
```bash
cd Comfyui_o1key
pip install -r requirements.txt
```

4. 重启 ComfyUI

### 使用说明

#### 1. 文生图

1. 添加 **Nano Banana Text-to-Image** 节点到工作流
2. 配置参数：
   - **Prompt**：文本描述
   - **API Key**：您的 o1key.com API 密钥
   - **Model**：选择模型（默认 `nano-banana-pro-default`）
   - **Aspect Ratio**：选择所需宽高比
   - **Image Size**：1K/2K/4K（Pro模型支持4K）
   - **Seed**（可选）：设置随机种子，-1为随机
3. 连接到预览或保存节点
4. 运行工作流

#### 2. 图生图

1. 添加 **Nano Banana Image-to-Image** 节点
2. 将参考图像连接到 `image` 输入（可选连接 `image_2` 到 `image_6`，最多6张参考图）
3. 配置与文生图相同的参数
4. 节点将使用参考图像引导生成
5. 运行工作流

#### 3. 批量处理

1. 添加 **Nano Banana Batch Processor** 节点
2. 输入多个提示词（每行一个）
3. 配置生成参数
4. 批量生成多张图片

### 获取 API 密钥

1. 访问 [o1key.com](https://o1key.com)
2. 注册或登录账户
3. 进入 API 设置
4. 从 Google AI Studio 创建新的 API 密钥
5. 复制密钥并在插件中使用

### 参数说明

| 参数 | 说明 | 选项 |
|------|------|------|
| `prompt` | 图像的文本描述 | 任意字符串 |
| `api_key` | o1key.com API 密钥 | 字符串 |
| `model` | 生成模型 | `nano-banana-pro-default`（默认）, `nano-banana-pro-svip`, `nano-banana-svip` |
| `aspect_ratio` | 图像宽高比 | 1:1, 4:3, 3:4, 16:9, 9:16, 2:3, 3:2, 4:5, 5:4, 21:9 |
| `image_size` | 输出图像分辨率 | `1K`, `2K`, `4K`（Pro模型）|
| `seed` | 随机种子（-1为随机） | -1 到 2147483647 |
| `image`（图生图）| 参考图像 | ComfyUI IMAGE 张量 |
| `image_2` - `image_6`（可选）| 额外参考图像 | ComfyUI IMAGE 张量 |

### 模型对比

| 特性 | nano-banana-pro-default | nano-banana-pro-svip | nano-banana-svip |
|------|------------------------|----------------------|------------------|
| 速度 | 快 | 快 | 快 |
| 质量 | 高 | 超高 | 高 |
| 图像尺寸 | 1K, 2K, 4K | 1K, 2K, 4K | 1K, 2K |
| 推荐度 | ✓✓（默认） | ✓✓✓（最高质量） | ✓ |
| 适用场景 | 日常创作 | 专业作品 | 快速预览 |

### 常见问题

**问题："API key is required" 错误**
- 解决：确保在节点参数中输入了 API 密钥

**问题："API error (status 401)" 错误**
- 解决：检查 API 密钥是否有效且未过期

**问题：图像生成失败且无明确错误**
- 解决：检查网络连接和 o1key.com 的 API 服务状态

**问题：节点未在 ComfyUI 中显示**
- 解决：确保已安装依赖并完全重启 ComfyUI

### 技术细节

- **API 端点**：`https://o1key.com/v1/images/generations`
- **认证方式**：通过 Authorization header 的 Bearer token
- **重试逻辑**：3次尝试，指数退避（1秒、2秒、4秒）
- **超时设置**：每个请求 60 秒
- **支持的图像格式**：PNG、JPEG（自动转换为 RGB）

### 错误处理

插件实现了完善的错误处理：
- **网络错误**：自动重试，指数退避
- **API错误**：清晰的错误消息和状态码
- **无效响应**：适当的验证和用户反馈
- **失败请求**：不收费（依据平台政策）

### 更新日志

#### v1.2.0 (2026-01-12)
- ✨ 新增 `nano-banana-pro-default` 模型（默认推荐）
- 🚀 批量处理优化：智能限流、自适应调整、进度预估
- 🔧 错误提示优化：友好的中文错误信息
- 📦 新增 `BatchRequestManager` 批量请求管理器
- 🗑️ 移除测试节点，代码更简洁

#### v1.1.0 (2026-01-10)
- ✨ 图生图支持多参考图（最多6张）
- 🔧 优化参数顺序和界面
- 📝 改进日志输出

#### v1.0.0 (2026-01-09)
- 🎉 初始版本发布
- ✨ 文生图和图生图功能
- ✨ 多模型和多宽高比支持

### 许可证

MIT License - 详见 LICENSE 文件

### 支持

- 📱 微信：qin1se
- 🐛 问题反馈：[GitHub Issues](https://github.com/yourusername/Comfyui_o1key/issues)
- 🌐 官网：[o1key.com](https://o1key.com)

---

## English

ComfyUI plugin for Nano Banana image generation API, providing text-to-image and image-to-image capabilities.

### Features

🎨 **Dual Generation Modes**
- Text-to-Image: Generate images from text prompts
- Image-to-Image: Transform existing images with text guidance (up to 6 reference images)

🚀 **Advanced Features**
- Three model options:
  - `nano-banana-pro-default` (Default) - Stable high quality
  - `nano-banana-pro-svip` - Ultra high quality Pro version
  - `nano-banana-svip` - High-speed quality
- 10 aspect ratios: 1:1, 4:3, 3:4, 16:9, 9:16, 2:3, 3:2, 4:5, 5:4, 21:9
- Image size control: 1K, 2K, 4K (Pro models)
- Automatic retry with exponential backoff (3 attempts)
- Comprehensive error handling
- No charge on failure guarantee
- Batch processing node

### Installation

1. Navigate to your ComfyUI custom nodes directory:
```bash
cd ComfyUI/custom_nodes/
```

2. Clone this repository:
```bash
git clone https://github.com/yourusername/Comfyui_o1key.git
```

3. Install required dependencies:
```bash
cd Comfyui_o1key
pip install -r requirements.txt
```

4. Restart ComfyUI

### Usage

#### 1. Text-to-Image Generation

1. Add the **Nano Banana Text-to-Image** node to your workflow
2. Configure parameters:
   - **Prompt**: Your text description
   - **API Key**: Your o1key.com API key
   - **Model**: Choose model (default `nano-banana-pro-default`)
   - **Aspect Ratio**: Select desired aspect ratio
   - **Image Size**: 1K/2K/4K (Pro models support 4K)
   - **Seed** (optional): Set random seed, -1 for random
3. Connect to preview or save nodes
4. Run the workflow

#### 2. Image-to-Image Generation

1. Add the **Nano Banana Image-to-Image** node
2. Connect reference image to `image` input (optionally connect `image_2` to `image_6`, up to 6 reference images)
3. Configure same parameters as text-to-image
4. The node will use reference images to guide generation
5. Run the workflow

#### 3. Batch Processing

1. Add the **Nano Banana Batch Processor** node
2. Enter multiple prompts (one per line)
3. Configure generation parameters
4. Generate multiple images in batch

### Getting Your API Key

1. Visit [o1key.com](https://o1key.com)
2. Sign up or log in to your account
3. Navigate to API settings
4. Create a new API key from Google AI Studio
5. Copy the key and use it in the plugin

### Parameters

| Parameter | Description | Options |
|-----------|-------------|---------|
| `prompt` | Text description of desired image | Any string |
| `api_key` | Your o1key.com API key | String |
| `model` | Generation model | `nano-banana-pro-default` (default), `nano-banana-pro-svip`, `nano-banana-svip` |
| `aspect_ratio` | Image aspect ratio | 1:1, 4:3, 3:4, 16:9, 9:16, 2:3, 3:2, 4:5, 5:4, 21:9 |
| `image_size` | Output image resolution | `1K`, `2K`, `4K` (Pro models) |
| `seed` | Random seed (-1 for random) | -1 to 2147483647 |
| `image` (I2I) | Reference image | ComfyUI IMAGE tensor |
| `image_2` - `image_6` (optional) | Additional reference images | ComfyUI IMAGE tensor |

### Model Comparison

| Feature | nano-banana-pro-default | nano-banana-pro-svip | nano-banana-svip |
|---------|------------------------|----------------------|------------------|
| Speed | Fast | Fast | Fast |
| Quality | High | Ultra High | High |
| Image Sizes | 1K, 2K, 4K | 1K, 2K, 4K | 1K, 2K |
| Recommended | ✓✓ (Default) | ✓✓✓ (Highest Quality) | ✓ |
| Use Case | Daily Creation | Professional Work | Quick Preview |

### Troubleshooting

**Problem: "API key is required" error**
- Solution: Make sure you've entered your API key in the node parameters

**Problem: "API error (status 401)" error**
- Solution: Check that your API key is valid and hasn't expired

**Problem: Image generation fails without clear error**
- Solution: Check your internet connection and API service status at o1key.com

**Problem: Node doesn't appear in ComfyUI**
- Solution: Ensure you've installed dependencies and restarted ComfyUI completely

### Technical Details

- **API Endpoint**: `https://o1key.com/v1/images/generations`
- **Authentication**: Bearer token via Authorization header
- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s)
- **Timeout**: 60 seconds per request
- **Supported Image Formats**: PNG, JPEG (auto-converted to RGB)

### Error Handling

The plugin implements robust error handling:
- **Network errors**: Automatic retry with exponential backoff
- **API errors**: Clear error messages with status codes
- **Invalid responses**: Proper validation and user feedback
- **Failed requests**: No charges (as per platform policy)

### Changelog

#### v1.2.0 (2026-01-12)
- ✨ Added `nano-banana-pro-default` model (now default)
- 🚀 Batch processing: Smart rate limiting, adaptive adjustment, ETA estimation
- 🔧 Improved error messages: User-friendly error handling
- 📦 New `BatchRequestManager` for batch request management
- 🗑️ Removed test nodes for cleaner codebase

#### v1.1.0 (2026-01-10)
- ✨ Image-to-image now supports multiple reference images (up to 6)
- 🔧 Optimized parameter order and interface
- 📝 Improved logging output

#### v1.0.0 (2026-01-09)
- 🎉 Initial release
- ✨ Text-to-image and image-to-image functionality
- ✨ Multiple models and aspect ratios support

### License

MIT License - See LICENSE file for details

### Support

- 📱 WeChat: qin1se
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/Comfyui_o1key/issues)
- 🌐 Website: [o1key.com](https://o1key.com)
