# 0006 — 将 Pitch 作为独立分类维度

此前的分类器只返回单个 `PoseState`，且仅依据 yaw 进行分类。`HeadPose` 类型虽然有一个 `roll` 字段，但该字段实际存储的是 pitch（仰头/低头）数据，而 pitch 在分类中被忽略。本 ADR 记录以下决策：将 pitch 提升为一等分类维度、将 `roll` 改名为 `pitch`、返回按轴分离的状态对，并删除不再有意义的 `OFF_AXIS_OTHER` 状态。

## 考虑过的选项

- **保留 `roll` 命名，再新增一个 `pitch` 字段** —— 否决：这会让 `roll` 字段继续存 pitch 值，造成永久的术语债务。当前管线里根本没有真正的 roll 测量。
- **保持单个 `PoseState` 返回，并新增组合状态如 `OFF_AXIS_RIGHT_HEAD_UP`** —— 否决：状态空间会组合爆炸（左/右 × 上/下 × 无人脸），迫使每个下游消费者都理解组合名称。按轴分离的状态更简洁，且可以非互斥。
- **在 `PoseClassification` 结构体中返回两个独立的 `PoseState`** —— 采纳：yaw 和 pitch 是正交的物理轴，它们的状态应当独立。
- **对 pitch 不做迟滞** —— 否决：pitch 在阈值附近也会像 yaw 一样抖动。两个轴采用相同的迟滞模式。
- **保留 `OFF_AXIS_OTHER`** —— 否决：该状态原本表示"仅 roll 偏移"，但 roll 不再被跟踪，pitch 又已成为独立维度。新的分类器不会产生 `OFF_AXIS_OTHER`。

## 决策

- 在 Python 和 Rust 中把 `HeadPose.roll` 改名为 `HeadPose.pitch`。正 pitch = 仰头；负 pitch = 低头。
- 将 `NeutralPose.roll` 改名为 `NeutralPose.pitch`。
- 用 `Thresholds.pitch_deg`（默认 5.0°）替换 `Thresholds.roll_deg`，并新增 `Thresholds.pitch_hysteresis_deg`（默认 2.5°）。yaw 阈值保持不变（1.0° / 0.5°）。
- 扩展 `PoseState`：新增 `HEAD_UP` 和 `HEAD_DOWN`；删除 `OFF_AXIS_OTHER`。
- 引入 `PoseClassification` frozen dataclass / 结构体，包含 `yaw_state: PoseState` 和 `pitch_state: PoseState`。
- 修改 `classify()` 返回 `PoseClassification`。内部独立判断 yaw 和 pitch；两个轴可以同时偏离。
- 当 `pose is None`（未检测到人脸）时，`yaw_state` 和 `pitch_state` 都为 `NO_FACE`。
- 用 `prev_classification` 替换单个 `prev_state` 参数；每个轴使用各自上一帧的状态做迟滞判断。
- 保持函数纯函数特性：不修改输入、无副作用。
- 更新 `test_classifier.py` 和 `src-tauri/tests/classifier_behavior.rs`，覆盖 pitch 分类、pitch 迟滞、yaw 与 pitch 同时偏离、以及 `NO_FACE` 行为。

## 后果

- sense loop、accumulator、overlay 等下游代码必须适配为消费 `PoseClassification` 而非单个 `PoseState`。该工作有意推迟到 #55 处理。
- 仰头/低头的提示文案需在 #55 中确定（例如"向下看" / "向上看"）。
- `PoseState.FACING_SCREEN` 的含义从"整体正对屏幕"变为"该维度在阈值内"。下游逻辑必须通过 `yaw_state == FACING_SCREEN and pitch_state == FACING_SCREEN` 来表示 **正对屏幕**。
- Python 和 Rust 分类器必须保持同步；未来任何分类规则改动都应同时镜像到两个实现。
- 期望单个 `PoseState` 字符串的现有事件日志消费者需要更新；这部分也属于 #55。
