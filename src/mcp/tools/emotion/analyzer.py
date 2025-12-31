import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - 运行时才会暴露
    cv2 = None  # type: ignore

try:
    from deepface import DeepFace  # type: ignore
except Exception:  # pragma: no cover
    DeepFace = None  # type: ignore


class EmotionAnalyzerError(Exception):
    """情绪分析过程中出现的可预期错误."""


@dataclass
class FaceEmotionResult:
    """单张人脸的情绪分析结果."""

    dominant_emotion: str
    confidence: float
    all_emotions: Dict[str, float]


async def _capture_frame(
    camera_index: int = 0,
    timeout: float = 3.0,
) -> "Any":
    """从指定摄像头采集一帧图像.

    使用线程池执行阻塞的 OpenCV 调用，避免阻塞事件循环。
    """

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        _capture_frame_sync,
        camera_index,
        timeout,
    )


def _capture_frame_sync(camera_index: int, timeout: float):
    """同步方式从摄像头采集一帧图像."""
    if cv2 is None:
        raise EmotionAnalyzerError(
            "未安装 OpenCV 库，请先安装依赖：pip install opencv-python"
        )

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap.release()
        raise EmotionAnalyzerError(f"无法打开摄像头（索引 {camera_index}），"
                                   "请检查是否存在可用摄像头或权限设置。")

    try:
        # 尝试降低分辨率以提升推理速度
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        ret, frame = cap.read()
        if not ret or frame is None:
            raise EmotionAnalyzerError("未能从摄像头读取到有效画面，请稍后重试。")

        return frame
    finally:
        cap.release()


async def _analyze_emotions(frame: "Any") -> List[FaceEmotionResult]:
    """对单帧图像进行人脸情绪分析."""
    if DeepFace is None:
        raise EmotionAnalyzerError(
            "未安装 DeepFace 库，请先安装依赖：pip install deepface"
        )

    loop = asyncio.get_running_loop()
    analysis = await loop.run_in_executor(
        None,
        _analyze_emotions_sync,
        frame,
    )
    return analysis
    # analysis = _analyze_emotions_sync(frame)  # 临时直接调用
    # return analysis


def _normalize_analysis_result(raw: Any) -> List[Dict[str, Any]]:
    """将 DeepFace 的返回结果统一规范为列表."""
    if raw is None:
        return []

    # DeepFace 可能返回 dict 或 list[dict]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def _analyze_emotions_sync(frame: "Any") -> List[FaceEmotionResult]:
    """同步调用 DeepFace 进行情绪分析."""
    try:
        # 仅分析情绪，关闭强制检测（否则无脸时会抛异常）
        raw_result = DeepFace.analyze(  # type: ignore[call-arg]
            img_path=frame,
            actions=["emotion"],
            enforce_detection=False,
        )
    except Exception as e:  # pragma: no cover - 模型内部异常
        raise EmotionAnalyzerError(f"情绪分析失败：{e}") from e

    normalized = _normalize_analysis_result(raw_result)
    if not normalized:
        raise EmotionAnalyzerError("未在画面中检测到人脸，或情绪分析结果为空。")

    results: List[FaceEmotionResult] = []
    for item in normalized:
        emotions: Dict[str, float] = {}
        raw_emotions = item.get("emotion") or item.get("emotions") or {}
        if isinstance(raw_emotions, dict):
            emotions = {
                str(k): float(v)
                for k, v in raw_emotions.items()
                # if isinstance(v, (int, float))
            }

        dominant = item.get("dominant_emotion")
        if dominant is None and emotions:
            # 兼容缺少 dominant_emotion 的情况
            dominant = max(emotions.items(), key=lambda x: x[1])[0]

        if not dominant:
            dominant = "unknown"

        confidence = 0.0
        if emotions and dominant in emotions:
            confidence = float(emotions[dominant])

        results.append(
            FaceEmotionResult(
                dominant_emotion=str(dominant),
                confidence=confidence,
                all_emotions=emotions,
            )
        )

    return results


def _format_results_text(results: List[FaceEmotionResult]) -> str:
    """将情绪分析结果格式化为适合 LLM 理解的中文描述."""
    if not results:
        return "未检测到任何人脸情绪结果。"

    lines: List[str] = []

    if len(results) == 1:
        r = results[0]
        lines.append(
            f"画面中检测到 1 张人脸，主要情绪为「{r.dominant_emotion}」，"
            f"置信度约为 {r.confidence:.1f}%。"
        )
    else:
        lines.append(f"画面中共检测到 {len(results)} 张人脸：")
        for idx, r in enumerate(results, start=1):
            lines.append(
                f"- 第 {idx} 个人脸主要情绪为「{r.dominant_emotion}」，"
                f"置信度约为 {r.confidence:.1f}%。"
            )

    # 补充整体情绪分布（简单聚合）
    aggregated: Dict[str, float] = {}
    for r in results:
        for emotion, score in r.all_emotions.items():
            aggregated[emotion] = aggregated.get(emotion, 0.0) + score

    if aggregated:
        total = sum(aggregated.values()) or 1.0
        # 取前 3 个情绪
        top = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)[:3]
        summary_parts = []
        for emotion, score in top:
            pct = score / total * 100.0
            summary_parts.append(f"{emotion}（约 {pct:.1f}%）")
        lines.append("整体情绪分布大致为：" + "，".join(summary_parts) + "。")

    return "\n".join(lines)


async def analyze_face_emotion(args: Dict[str, Any]) -> str:
    """MCP 工具回调：采集摄像头画面并进行人脸情绪分析.

    参数:
        camera_index: 摄像头索引，整数，可选，默认 0。
        capture_timeout: 采集超时时间（秒），整数或浮点，可选，默认 3。
        return_raw: 布尔值，可选，默认 False。为 True 时返回原始结果列表（JSON），否则返回格式化文本。
    """
    camera_index = int(args.get("camera_index", 0) or 0)
    capture_timeout_raw: Optional[Any] = args.get("capture_timeout", 3)
    try:
        capture_timeout = float(capture_timeout_raw)
    except Exception:
        capture_timeout = 3.0
    
    return_raw = bool(args.get("return_raw", False))

    try:
        frame = await _capture_frame(camera_index=camera_index, timeout=capture_timeout)
        results = await _analyze_emotions(frame)
        
        if return_raw:
            # 返回原始结果，转换为 JSON 字符串
            return json.dumps([
                {
                    "dominant_emotion": r.dominant_emotion,
                    "confidence": r.confidence,
                    "all_emotions": r.all_emotions
                }
                for r in results
            ], ensure_ascii=False)
        else:
            return _format_results_text(results)
    except EmotionAnalyzerError as e:
        # 业务可预期错误，直接返回友好提示
        return f"人脸情绪分析未完成：{e}"
    except Exception as e:  # pragma: no cover - 意外错误
        # 让上层 MCP 捕获并设置 isError，但仍返回信息
        raise EmotionAnalyzerError(f"人脸情绪分析时出现未预期错误：{e}") from e


