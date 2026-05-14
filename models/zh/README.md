---
frameworks:
- 其他
license: Apache License 2.0
tasks:
- keyword-spotting
---

sherpa 中自定义唤醒词模型，训练数据为 wenetspeech L （10000 小时）数据，模型大小约为 3.3 M， 建模单元为拼音（声母 + 韵母）。
使用 icefall 训练，已转换为 onnx 格式，此仓库主要是给 sherpa-onnx 这个 inference 引擎使用。

模型结构为 zipformer 模型， 本质是一个非常小的语音识别模型，为了实现唤醒词的功能，我们在解码端做了一些修改和约束。
支持自定义唤醒词，数量不限，效果需要单个调整参数。

#### Clone with HTTP
```bash
 git lfs install
 git clone https://www.modelscope.cn/pkufool/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01.git
```
