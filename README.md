# Video2x Mac环境安装

- ###### Video2X没有Mac安装包，需要手动编译
- ###### <u>只支持`-p realcugan`参数</u>

## 安装依赖

### 安装 pkg-config 以便 CMake 能找到其他库

```bash
brew install pkg-config
```

### 安装 FFmpeg, spdlog, Boost, Ncnn依赖

```bash
brew install ffmpeg spdlog boost ncnn
```

## 安装Vulkan

```bash
brew install molten-vk vulkan-loader
```

## 下载Video2X

- git下载

```bash
git clone --recurse-submodules https://github.com/k4yt3x/video2x.git
```

- .`git`文件太大，速度较慢，可以手动下载(同时下载依赖项目)

## 编译前修改

### 支持mac环境链接

```makefile
# 根目录CMakeLists.txt修改为下面形式
if(NOT APPLE)
  # 在linux环境使用这个选项
  target_link_options(some_target PRIVATE -Wl,--gc-sections)
endif()
```

#### 指定链接库路径

```cmake
# 生成libvideo2x前指定库路径
if(APPLE)
    target_link_directories(libvideo2x PRIVATE 
        ${libavcodec_LIBRARY_DIRS}
        ${libavfilter_LIBRARY_DIRS}
        ${libavformat_LIBRARY_DIRS}
        ${libavutil_LIBRARY_DIRS}
        ${libswscale_ILIBRARY_DIRS}
    )
endif()
```

```cmake
# 生成video2x前指定库路径    
if(APPLE)
    target_link_directories(video2x PRIVATE 
        ${libavcodec_LIBRARY_DIRS}
        ${libavfilter_LIBRARY_DIRS}
    )
endif()
```

### macOS 上用MoltenVK必须加扩展

```cpp
// vulkan_utils.cpp 文件enumerate_vulkan_devices函数修改创建实例代码
VkApplicationInfo appInfo{};
appInfo.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
appInfo.pApplicationName = "YourAppName";
appInfo.applicationVersion = VK_MAKE_VERSION(1, 0, 0);
appInfo.pEngineName = "No Engine";
appInfo.engineVersion = VK_MAKE_VERSION(1, 0, 0);
appInfo.apiVersion = VK_API_VERSION_1_0;

std::vector<const char*> extensions = {
    VK_KHR_SURFACE_EXTENSION_NAME,
    "VK_MVK_macos_surface",
    VK_KHR_GET_PHYSICAL_DEVICE_PROPERTIES_2_EXTENSION_NAME,
    VK_KHR_PORTABILITY_ENUMERATION_EXTENSION_NAME,
};

VkInstanceCreateInfo createInfo{};
createInfo.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
createInfo.pApplicationInfo = &appInfo;
createInfo.enabledExtensionCount = static_cast<uint32_t>(extensions.size());
createInfo.ppEnabledExtensionNames = extensions.data();
createInfo.flags = VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR; 

VkInstance instance;
VkResult result = vkCreateInstance(&createInfo, nullptr, &instance);
```

## cmake编译

```bash
# 创建构建目录
mkdir build && cd build

# 运行 cmake，默认会使用系统安装的库
# 如果你是 Apple Silicon 用户，可以加上 -DVIDEO2X_ENABLE_NATIVE=ON
# 如果你是 Intel Silicon 用户，可以加上 -VIDEO2X_ENABLE_X86_64_V4=ON 或VIDEO2X_ENABLE_X86_64_V3=ON
# 如果报OpenMP错误，见下面
cmake -DVIDEO2X_ENABLE_NATIVE=ON .. 

# 运行编译
make VERBOSE=1
# 不要make install!!!
# 模型文件路径是相对路径，只能在根目录下运行
# 拷贝到上层目录
cp video2x libvideo2x.dylib ..
```

### 编译问题---无法找到OpenMP

```bash
  The link interface of target "ncnn" contains:

    OpenMP::OpenMP_CXX

  but the target was not found.  Possible reasons include:
```

- 安装libomp

```bash
brew install libomp
```

- 使用llvm进行编译

```bash
# 设置CC和CXX编译器为llvm
CC=$(brew --prefix llvm)/bin/clang CXX=$(brew --prefix llvm)/bin/clang++ cmake -DVIDEO2X_ENABLE_NATIVE=ON -DVIDEO2X_USE_EXTERNAL_NCNN=ON  ..
# 如果能生成Makefile文件，基本就可以编译成功
# make 可能报错，根据报错直接修改对应的编译文件即可
# -D CMAKE_BUILD_TYPE=Debug
```

## 使用

### 命令

```bash
./video2x -i input.mp4 -o output2.mp4 -p realcugan  -s 4 --realcugan-model models-se
```

- ***<u><mark>必须指定`-p realcugan`参数运行，调用其他参数进行GPU计算会空出错，原因未知</mark></u>***

### app应用

- Video2X.app为手动构建的app应用

- 内涵一个python界面程序

- 如果无法运行，修改`Video2X.app/Contents/MacOS/Video2X `中的pyton路径

- Video2X需要执行权限`chmod u+x Video2X`

```bash
#!/bin/bash
cd "$(dirname "$0")"
# 调用系统 Python3 运行你的脚本（也可以指定虚拟环境或打包环境）
exec /opt/homebrew/bin/python3 script.py
```

### 模型

| 模型            | 作用         | 场景                   |
| ------------- | ---------- | -------------------- |
| `models-se`   | 放大分辨率 + 降噪 | 效果均衡的主力模型，大多数情况下的首选。 |
| `models-pro`  | 放大分辨率 + 降噪 | se 的备选方案，风格略有不同。     |
| `models-nose` | 仅降噪        | 只清理画质，不改变视频原始分辨率。    |
