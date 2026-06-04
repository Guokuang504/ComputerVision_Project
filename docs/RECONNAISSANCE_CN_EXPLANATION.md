# Reconnaissance 部分中文说明

## 1. 你负责的范围

本项目被拆成三个模块后，你负责的是 `reconnaissance`，也就是“识别已经被裁剪出来的内容”。因此你的模块不应该负责整页定位、旋转校正、表格线检测、复选框检测、Student ID 网格读取、cryptogram 检测等工作。这些属于另外两位组员。

你的模块负责三件事：

1. 签名识别：输入一个签名区域的小图，输出最可能的 student ID。
2. 印刷文字 OCR：输入一个印刷文字区域的小图，输出文字内容，例如 module、professor、date、code。
3. 手写数字/字符识别：输入一个手写答案区域的小图，输出数字，例如 mantisse、exposant。

我已经把这部分做成了 `recognition/` Python 包，位置是：

`/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/recognition`

## 2. 为什么这样设计

项目说明要求图形元素要用课程里的低层图像处理方法，但文字识别可以使用更高层的方法。你的模块里：

- 签名识别没有用深度学习黑盒，而是用可解释的图像特征和最近邻匹配。
- 手写数字识别用了 `sklearn` 的 SVM 基线模型，方便解释，也容易在报告中描述。
- 印刷 OCR 使用可选的 Tesseract 后端；如果环境没有 OCR 引擎，程序不会崩溃，而是返回空结果和低置信度。

这样可以保证整条链先跑起来，然后后续再提高精度。

## 3. 签名识别方法

签名数据库在：

`SIGNATURES/`

里面每个学生一个文件夹，每个文件夹有多张该学生签名图像，例如：

`SIGNATURES/Scan_16042026093714_SIG/62034/62034_000.png`

签名识别流程如下：

1. 读入图像并转成灰度图。
2. 使用 Otsu 阈值法把签名墨迹二值化。
3. 找到前景像素的外接区域，把空白背景裁掉。
4. 保持长宽比缩放到固定大小 `192 x 96`。
5. 提取多组特征：HOG cell size `8/10/12/16`，再加 `6 x 12` zoning density。
6. 对每组特征分别计算欧氏距离，再按权重加权求和。
7. 选择距离最小的样本，其文件夹名就是预测的 student ID。
8. 如果最小距离大于阈值，则拒绝识别，返回空 ID。

核心类是：

```python
from recognition import SignatureRecognizer

model = SignatureRecognizer(threshold=0.82)
model.fit_from_folder("SIGNATURES")
prediction = model.predict(signature_crop)
```

返回结果包括：

- `student_id`: 预测出的学生 ID。
- `confidence`: 置信度，来自最佳匹配和第二匹配之间的距离差。
- `distance`: 最佳匹配距离。
- `accepted`: 是否通过阈值。

当前用 `threshold=0.82`、`ambiguous_margin=0.02` 在签名库上做 leave-one-out 交叉验证：

- 样本数：`1220`
- top-1 accuracy：约 `86.0%`
- accepted correct rate：约 `71.7%`
- accepted wrong rate：约 `3.8%`
- rejection rate：约 `21.5%`
- ambiguous rate：约 `3.0%`

阈值越高，接受的签名越多，但误接受风险也越高。阈值越低，系统更保守，会把更多样本交给人工检查。

这次优化前单一 HOG 的 top-1 accuracy 约为 `83.9%`。改成多尺度 HOG + zoning density 后，top-1 accuracy 提升到约 `86.0%`。随后根据 `signature_scores.csv` 做阈值校准，把默认阈值设为 `0.82`，并把 ambiguous margin 设为 `0.02`，用较低误接受率换取更少的 rejected 样本。

## 4. 手写数字识别方法

文件：

`recognition/handwriting.py`

类：

```python
from recognition import HandwrittenNumberRecognizer

model = HandwrittenNumberRecognizer()
model.fit_default_digits()
pred = model.predict_number(crop)
```

流程如下：

1. 对手写区域做灰度化和 Otsu 二值化。
2. 裁掉多余空白。
3. 用 connected components 分割字符。
4. 对每个字符判断是否像小数点或负号。
5. 对数字字符缩放到 `8 x 8`，保留灰度强度而不是只保留二值图。
6. 用加入轻量平移增强的数据训练 SVM，并分类为 `0-9`。
7. 把所有字符结果拼成字符串。

这个基线模型使用 `sklearn.datasets.load_digits` 训练。demo 中的内部验证准确率约为 `0.996`，但这个准确率来自 sklearn 自带数据，不是考试真实手写数据。所以报告里要说明：这是 baseline，后续最好用本项目的真实手写 crop 重新训练或微调。

## 5. 印刷文字 OCR

文件：

`recognition/ocr.py`

类：

```python
from recognition import PrintedTextRecognizer

ocr = PrintedTextRecognizer()
pred = ocr.predict(crop)
```

对于常见字段，也可以使用预定义白名单：

```python
pred = ocr.predict_field(code_crop, "code")
```

可用字段类型包括：

- `code`: 大写字母、数字、连字符。
- `date`: 数字和 `/`。
- `number`: 数字、小数点、逗号、负号。
- `student_id`: 数字。
- `unit`: 英文字母。

它会优先寻找本机是否有 `tesseract` 命令。如果有，就调用 Tesseract 做 OCR。如果没有，就返回：

```python
text = ""
confidence = 0.0
backend = "none"
```

当前机器已经通过 Homebrew 安装并验证了 Tesseract：

- Tesseract 版本：`5.5.2`
- 可用语言数据：`eng`, `osd`, `snum`
- 安装命令：`brew install tesseract`

因此 printed OCR 现在是真正可用的，不再只是 fallback。代码仍然保留 fallback：如果换到另一台机器没有 Tesseract，程序不会崩溃，而是返回空文本和低置信度。

这次还把 OCR 置信度从固定值改成读取 Tesseract 的 TSV confidence。`run_reconnaissance_demo.py` 里加入了 OCR smoke test，会生成三张合成字段图并识别：

- `code`: `S1-01-G1`
- `student_id`: `62034`
- `number`: `3.745`

如果你们最后想继续提高 printed OCR，可以换成 EasyOCR/PaddleOCR，或者针对真实裁剪字段调 Tesseract 的 `psm` 和白名单。

## 6. 和队友如何对接

你应该告诉负责 structure 的队友：

他负责：

- 打开 PDF 或图片。
- 把页面转成图像。
- 做旋转和透视校正。
- 创建 Excel 文件。
- 把结果写入 `PAGE-01` 和 `EXAM` sheet。

你应该告诉负责 graphical elements 的队友：

他负责：

- 读取 Student ID grid。
- 检测复选框。
- 检测 cryptogram。
- 找到签名框、文字框、手写答案框的位置。
- 把这些区域裁剪出来传给你的 recognition 模块。

你的接口示例：

```python
from recognition import RecognitionService

service = RecognitionService.from_signature_folder("SIGNATURES", threshold=0.82)

result = service.recognize_page_01(
    signature_crop=signature_crop,
    printed_crops={
        "module": module_crop,
        "professor": professor_crop,
        "code": code_crop,
    },
    handwritten_crops={}
)
```

然后 integration 代码应该比较：

```python
student_id_grid == result.student_id_signature
```

如果相等，就把 Excel 中 `Validation signature` 写成 `1`；否则写成 `0` 或留给人工检查。

考试页中：

- `CHOIX A-H` 来自 graphical module。
- `MANTISSE` 和 `EXPOSANT` 可以用 `recognize_handwritten_number`。
- `UNITE` 目前还没有高精度手写字母识别，需要后续改进。

## 7. 如何运行

在项目目录运行：

```bash
cd "/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530"
python3 run_reconnaissance_demo.py
```

这个命令会：

1. 从 `SIGNATURES/` 训练签名识别模型。
2. 训练手写数字 SVM。
3. 保存模型到 `output/reconnaissance/`。
4. 打印一个签名样本的预测结果。

评估签名识别：

```bash
python3 -m recognition.evaluate --signatures SIGNATURES --threshold 0.82
```

输出文件：

`output/reconnaissance/signature_eval.csv`

同时会输出：

- `output/reconnaissance/signature_scores.csv`
- `output/reconnaissance/signature_thresholds.csv`
- `debug/signatures/validation/`

## 8. 报告中可以怎么写

你可以在 report 的 methods 部分写：

- Preprocessing: grayscale conversion, Gaussian smoothing, Otsu thresholding, foreground bounding box crop, aspect-ratio preserving resize.
- Signature descriptor: HOG feature vector.
- Optimized signature descriptor: weighted fusion of multi-scale HOG and zoning density.
- Signature classification: nearest-neighbor classification over reference signatures.
- Rejection rule: accept only if the nearest-neighbor distance is below threshold tau.
- Handwritten digit recognition: connected-component segmentation plus SVM classifier.
- Evaluation: leave-one-out validation on the signature database.

可以使用这个公式描述签名识别：

给定输入签名图像 `I`，提取第 `k` 组特征向量：

`x_k = phi_k(preprocess(I))`

数据库中第 `j` 个签名样本的第 `k` 组特征是 `x_{j,k}`，对应学生是 `s_j`。加权距离：

`d(I, j) = sum_k w_k ||x_k - x_{j,k}||_2`

预测：

`j* = argmin_j d(I, j)`

如果：

`d(I, j*) <= tau`

则输出：

`studentID = s_j*`

否则拒绝识别。

## 9. 真实 FORM 验证结果

这次 final delivery 阶段已经不只跑 demo，而是在真实 `FORM1/FORM2/FORM3` 数据上跑了完整主流程：

```bash
python3 main.py FORM1 --results-dir output/verification_FORM1_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM1_FINAL --exam-root FORM1

python3 main.py FORM2 --results-dir output/verification_FORM2_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM2_FINAL --exam-root FORM2

python3 main.py FORM3 --results-dir output/verification_FORM3_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM3_FINAL --exam-root FORM3
```

验证结果：

- FORM1：Program 1 `32/32` 行，Program 2 `43/43` 个 Excel。
- FORM2：Program 1 `22/22` 行，Program 2 `52/52` 个 Excel。
- FORM3：Program 1 `42/42` 行，Program 2 `46/46` 个 Excel。
- 对于损坏或无法被 PIL 读取的 presence 图片，程序现在不会崩溃，也不会丢行，而是写入对应 `imageName` 和空识别结果。
- 每个 Program 2 Excel 至少包含 `PAGE-01` 和 `EXAM` 两个 sheet。

真实 crop 的 debug 统计：

- 每个 results folder 内都有 `handwritten_debug.csv`、`signature_scores.csv`、`printed_ocr_debug.csv` 和 `qcm_candidates.csv`。
- 手写 crop 统计详见 `docs/EVALUATION_SUMMARY.md`；这些不是 accuracy，因为当前没有真实手写答案标签，只能用于人工检查低置信和坏 crop。
- 真实 FORM 的签名匹配统计也不是真实 accuracy，因为没有直接提供签名 ground truth；签名 accuracy 仍以 `SIGNATURES/` 的 leave-one-out 评估为准。

QCM 误检修复：

- 旧逻辑会把 `QUESTION` 标题附近的小方块或字母碎片误当成 checkbox。
- 新逻辑仍然使用低层方法：阈值、connected components、几何过滤、border score 和垂直 A-D 选项栈规则。
- 最终 review overlay 显示，QCM 框现在落在左侧 A-D 选项框上，不再框住标题文字。
- 候选日志在各 results folder 的 `qcm_candidates.csv`，也会写入当前 `debug/qcm/qcm_candidates.csv`，包括 `x/y/w/h`、面积、宽高比、填充率、page zone、accepted/rejected decision 和 reason。

详细测试报告在：

`docs/VERIFICATION_REPORT.md`

最终三套 FORM 评估汇总在：

`docs/EVALUATION_SUMMARY.md`

## 10. 当前不足和改进方向

当前版本是可运行 baseline，不是最终高精度方案。主要不足：

- 签名识别对裁剪质量敏感，签名框边线如果被裁进来会干扰识别。
- 阈值 `0.82` 是在当前签名库 leave-one-out 验证上校准的，challenge 数据可能需要重新调。
- 手写数字模型不是用本项目手写数据训练的。
- 印刷 OCR 依赖外部 OCR 引擎；当前机器已经安装 Tesseract，但在 Vocareum 或其他电脑上仍需要确认 `tesseract` 命令存在。
- 手写单位 `KHz`、`Mo`、`Bit` 等还没有专门分类器。

建议后续改进：

1. 收集队友裁剪出的真实 mantisse/exposant 字符，建立训练集。
2. 为单位字段建立小型分类器，只识别有限集合，例如 `Hz`, `KHz`, `Mo`, `Bit`。
3. 用验证集搜索签名阈值，而不是固定写死。
4. 对签名继续加入 skeleton 或 projection profile，并用验证集重新调权重。
5. 对 OCR 字段继续使用并扩展白名单，例如 code 只允许大写字母、数字、连字符。
