# XiaoZhi-PyQtFluent部署教程

⚠️务必按照教程安装顺序进行软件、工具的安装

⚠️推荐使用conda环境进行安装，PyQt5、OpenCV可以直接使用conda预编译好的版本。pip在arm64 4GB及其以下设备上PyQt5、OpenCV极其容易编译失败无法安装

### Linux apt软件包安装(缺一不可)

```bash
# debian系
sudo apt install -y curl ffmpeg portaudio19-dev
```

### 一键自动更换当前网络下最快pip软件源

* **为了更稳定更快速的安装所需依赖包，建议安装**

[工具地址|chsrc 全平台通用换源工具|GitHub仓库](https://github.com/RubyMetric/chsrc)

```bash
# 个人服务器，加速下载，支持x86_64和arm64架构
wget -O- aslant.top/chsrc.sh|sudo bash

# 更换pip软件源
chsrc set pip
```

<video controls="controls" src="assets/PixPin_2025-04-17_19-44-34-20250417194442-73it0v0.mp4" data-src="assets/PixPin_2025-04-17_19-44-34-20250417194442-73it0v0.mp4" __idm_id__="270338"></video>

### Miniconda下载安装

```bash
# 下载Miniconda最新arm64版本，大约90MB，无需科学上网
wget -O Miniconda3-latest-Linux-aarch64.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
```

```bash
chmod +x Miniconda3-latest-Linux-aarch64.sh
sudo ./Miniconda3-latest-Linux-aarch64.sh
```

1. 安装过程中，你会看到许可协议。按 `Enter` 键逐屏查看，或按 `q` 键跳过。然后输入 `yes` 接受许可协议。

2. 默认路径是 `$HOME/miniconda3`直接按 `Enter` 键。
3. 安装程序会询问是否初始化Miniconda。建议选择 `yes`。这会将Miniconda的 `bin` 目录添加到当前用户的 `PATH` 环境变量配置文件中。

```bash
nano ~/.bashrc
```

- 在文件末尾添加以下环境变量

```bash
export PATH=$HOME/miniconda3/bin:$PATH
```

4. 按 `Ctrl + X` ，然后按 `Y` ，最后按 `Enter` 保存并退出 `nano` 编辑器。

5. 使环境变量配置生效
   ```bash
   source ~/.bashrc
   ```

6. 如果激活环境，会出现(base)即可

```bash
conda --version
conda init
bash
```

### 拉取代码仓库

```python
git clone https://github.com/huangjunsen0406/XiaoZhi-PyQtFluent.git
```

```bash
# 创建一个新的python310环境
conda create -n xiaozhi python=3.10 -y

# 进入新创建的虚拟环境
conda activate xiaozhi
```

* 安装项目依赖

```bash
# 进入拉取的仓库根目录(包含requirements.txt的一级)
pip install -r requirements.txt
```

* 安装其它依赖(**三大件**)

```bash
# 依然在创建的xiaozhi虚拟环境中
# PyQt5
conda install pyqt=5.15.10 -y

# OpenCV
conda install opencv=4.10.0 -y

# PyQt-Fluent-Widgets
pip install PyQt-Fluent-Widgets
```

### <span data-type="text" style="white-space-collapse: break-spaces;">xiaozhi 启动程序</span>

不出意外的话，就可以启动了

```bash
# 在xiaozhi虚拟环境下
python main.py
```

‍
