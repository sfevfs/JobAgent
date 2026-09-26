#!/usr/bin/env python3
"""Deterministic, offline JD matcher for Codex JobAgent V1.

The matcher reads only local configuration and resume facts.  A ``selected``
decision means suitable for a local review list; this module has no application,
messaging, browser, or mobile side effects.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESUME = PROJECT_ROOT / ".local/candidates/candidate_a/resume_facts.yaml"
DEFAULT_PROFILE = PROJECT_ROOT / ".local/candidates/candidate_a/profile.yaml"
DEFAULT_SCORING = PROJECT_ROOT / "config" / "scoring_candidate_a.yaml"
DEFAULT_ELIGIBILITY = PROJECT_ROOT / ".local/candidates/candidate_a/eligibility_policy.yaml"

TRACKS = ("communication_ai", "medical_cv", "general_ai")

LEVEL_VALUE = {
    "proficient": 1.0,
    "familiar": 0.8,
    "basic": 0.45,
    "used": 0.45,
    "true": 0.8,
}

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "PyTorch": ("pytorch",),
    "TensorFlow": ("tensorflow",),
    "MATLAB": ("matlab",),
    "C++": ("c++", "cpp"),
    "C#": ("c#", "c sharp"),
    "Java": ("java",),
    "JavaScript": ("javascript",),
    "TypeScript": ("typescript",),
    "React": ("react", "react.js", "next.js", "nextjs"),
    "Spring Boot": ("spring boot",),
    "CUDA": ("cuda",),
    "TensorRT": ("tensorrt",),
    "ONNX": ("onnx",),
    "Docker": ("docker",),
    "Linux server": ("linux server", "linux servers"),
    "Linux": ("linux",),
    "Git": ("git", "github"),
    "OpenCV": ("opencv",),
    "SimpleITK": ("simpleitk",),
    "NumPy": ("numpy",),
    "Pandas": ("pandas",),
    "scikit-learn": ("scikit-learn", "sklearn"),
    "SQL": ("sql", "postgresql", "mysql"),
    "Spark": ("spark", "pyspark"),
    "Kafka": ("kafka",),
    "AWS": ("aws", "sagemaker"),
    "Kubernetes": ("kubernetes", "k8s"),
    "MLflow": ("mlflow",),
    "Airflow": ("airflow",),
    "FastAPI": ("fastapi",),
    "Deep Learning": ("deep learning", "深度学习"),
    "Machine Learning": ("machine learning", "机器学习"),
    "CNN": ("cnn", "convolutional neural network"),
    "RNN/LSTM": ("rnn", "lstm", "recurrent neural network"),
    "Transformer": ("transformer", "transformers"),
    "U-Net": ("u-net", "unet"),
    "nnU-Net": ("nnunet", "nn u-net", "nn-unet"),
    "LLM": ("llm", "large language model", "大语言模型", "大模型"),
    "RAG": ("rag", "retrieval-augmented generation"),
    "AI agents": ("ai agent", "ai agents", "agentic ai", "tool calling"),
    "Multimodal learning": (
        "multimodal",
        "multi-modal",
        "多模态",
        "vision-language",
        "vision language",
        "vla",
    ),
    "Time-series modeling": (
        "time series",
        "time-series",
        "forecasting",
        "sequential modeling",
        "时序预测",
    ),
    "Computer Vision": ("computer vision", "计算机视觉"),
    "Image segmentation": ("image segmentation", "图像分割", "segmentation"),
    "Object detection": ("object detection", "目标检测", "detection"),
    "3D Vision": ("3d vision", "3d视觉", "三维视觉", "point cloud", "点云"),
    "Image reconstruction": ("image reconstruction", "图像重建", "三维重建"),
    "Image enhancement": ("image enhancement", "图像增强", "图像优化"),
    "Video understanding": ("video understanding", "视频理解", "视频分析"),
    "Recommendation": ("recommendation", "recommender", "推荐算法"),
    "Speech algorithms": (
        "speech recognition",
        "speech synthesis",
        "voiceprint",
        "audio algorithm",
        "语音识别",
        "语音合成",
        "声纹识别",
        "音频算法",
    ),
    "Embedded systems": ("embedded", "嵌入式"),
    "FPGA": ("fpga",),
    "Radar algorithms": ("radar", "雷达算法", "雷达信号处理"),
    "Integrated sensing and communication": (
        "integrated sensing and communication",
        "isac",
        "通信感知一体化",
        "通感一体化",
    ),
    "Distributed training": (
        "distributed training",
        "large-scale distributed training",
        "大规模分布式训练",
    ),
}

ENGINEERING_TOOLS = {
    "C++",
    "CUDA",
    "TensorRT",
    "ONNX",
    "Docker",
    "Linux server",
    "Linux",
    "Git",
    "OpenCV",
    "SimpleITK",
    "SQL",
    "Spark",
    "Kafka",
    "AWS",
    "Kubernetes",
    "MLflow",
    "Airflow",
    "FastAPI",
    "Java",
    "C#",
    "JavaScript",
    "TypeScript",
    "React",
    "Spring Boot",
    "Distributed training",
    "Embedded systems",
    "FPGA",
}

PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "a plus",
    "advantage",
    "desirable",
    "优先",
    "加分",
    "优先考虑",
)
REQUIRED_MARKERS = (
    "required",
    "must have",
    "must-have",
    "must possess",
    "proficient",
    "proficiency",
    "strong expertise",
    "strong experience",
    "mandatory",
    "minimum",
    "at least",
    "要求",
    "必须",
    "精通",
    "熟练掌握",
    "掌握",
    "熟悉",
    "具备",
)

COMM_SIGNALS: dict[str, float] = {
    "massive mimo": 3.0,
    "mimo": 2.0,
    "csi": 3.0,
    "channel state information": 3.0,
    "channel prediction": 2.5,
    "channel estimation": 2.5,
    "channel modeling": 2.0,
    "ofdm": 2.0,
    "phy": 2.0,
    "physical layer": 2.5,
    "ran": 2.0,
    "baseband": 2.5,
    "wireless": 2.0,
    "telecom": 1.5,
    "radio access": 2.0,
    "radio": 1.2,
    "modem": 2.0,
    "transmitter": 1.5,
    "beamforming": 2.0,
    "resource allocation": 1.5,
    "signal processing": 2.0,
    "dsp": 2.0,
    "rf": 1.5,
    "5g": 1.5,
    "6g": 1.5,
    "radar": 1.5,
    "baseband algorithm": 2.5,
    "channel coding": 1.5,
    "modulation": 1.2,
    "demodulation": 1.2,
    "无线通信": 2.0,
    "无线算法": 2.5,
    "通信算法": 2.5,
    "信号处理": 2.0,
    "物理层": 2.5,
    "信道": 2.0,
    "信道估计": 2.5,
    "基带": 2.5,
    "调制解调": 1.5,
    "波束赋形": 2.0,
    "通信感知一体化": 2.0,
    "通感一体化": 2.0,
    "雷达": 1.5,
}

MEDICAL_STRONG_SIGNALS: dict[str, float] = {
    "medical imaging": 3.0,
    "medical image": 3.0,
    "医学图像": 3.0,
    "医疗影像": 3.0,
    "radiology": 2.5,
    "pathology": 2.0,
    "dicom": 2.5,
    "nifti": 2.5,
    "mri": 2.5,
    "ct": 2.5,
    "image segmentation": 2.5,
    "图像分割": 2.5,
    "u-net": 2.0,
    "unet": 2.0,
    "nnunet": 2.0,
    "3d segmentation": 2.5,
    "医学影像": 3.0,
    "超声成像": 2.5,
    "医学信号": 2.5,
    "medical signal": 2.5,
    "生理信号": 2.0,
    "超声": 1.5,
    "医疗产品": 1.2,
}

CV_SIGNALS: dict[str, float] = {
    "computer vision": 2.5,
    "计算机视觉": 2.5,
    "cv algorithm": 2.0,
    "cv算法": 2.0,
    "visual algorithm": 2.0,
    "视觉算法": 2.0,
    "vision algorithm": 2.0,
    "image processing": 2.0,
    "图像处理": 2.0,
    "image algorithm": 2.0,
    "图像算法": 2.0,
    "object detection": 2.0,
    "目标检测": 2.0,
    "image recognition": 1.8,
    "图像识别": 1.8,
    "3d vision": 2.0,
    "3d视觉": 2.0,
    "三维视觉": 2.0,
    "point cloud": 1.8,
    "点云": 1.8,
    "autonomous driving perception": 2.2,
    "自动驾驶感知": 2.2,
    "智能驾驶感知": 2.2,
    "自动驾驶算法": 1.6,
    "机器人感知": 2.2,
    "感知算法": 1.8,
    "工业视觉": 2.0,
    "machine vision": 2.0,
    "遥感": 1.6,
    "video understanding": 1.8,
    "视频理解": 1.8,
    "语义分割": 1.8,
    "实例分割": 1.8,
    "深度估计": 1.5,
    "图像增强": 1.2,
    "图像重建": 1.2,
}

# Direct computer-vision roles are a P1 transfer lane for candidates whose
# verified projects are medical-CV focused.  These signals deliberately use
# explicit vision/image wording; generic "AI" or "deep learning" alone is not
# enough to enter this lane.
DIRECT_CV_TRANSFER_SIGNALS: dict[str, float] = {
    "computer vision": 2.0,
    "计算机视觉": 2.0,
    "cv algorithm": 2.0,
    "cv算法": 2.0,
    "visual algorithm": 2.0,
    "视觉算法": 2.0,
    "vision algorithm": 2.0,
    "image processing": 1.8,
    "图像处理": 1.8,
    "image algorithm": 1.8,
    "图像算法": 1.8,
    "object detection": 1.8,
    "目标检测": 1.8,
    "image segmentation": 1.8,
    "图像分割": 1.8,
    "semantic segmentation": 1.6,
    "语义分割": 1.6,
    "instance segmentation": 1.6,
    "实例分割": 1.6,
    "machine vision": 1.8,
    "工业视觉": 1.8,
    "opencv": 1.0,
}

DIRECT_CV_BLOCKED_CORE_SIGNALS: tuple[str, ...] = (
    "llm",
    "large language model",
    "大模型",
    "rag",
    "retrieval augmented generation",
    "检索增强",
    "知识库问答",
    "multimodal",
    "multi-modal",
    "多模态",
    "vision-language",
    "视觉语言模型",
)

MEDICAL_EXPLORATORY_SIGNALS: dict[str, float] = {
    "ultrasound": 0.7,
    "registration": 1.0,
    "reconstruction": 1.0,
    "detection": 0.8,
    "classification": 0.8,
    "enhancement": 0.8,
    "denoising": 0.8,
    "超声": 0.7,
    "配准": 1.0,
    "重建": 1.0,
    "检测": 0.8,
    "分类": 0.8,
    "增强": 0.8,
    "去噪": 0.8,
}

GENERAL_SIGNALS: dict[str, float] = {
    "machine learning": 1.5,
    "deep learning": 1.5,
    "artificial intelligence": 1.2,
    " ai ": 1.0,
    "llm": 2.5,
    "large language model": 2.5,
    "agentic": 2.0,
    "tool calling": 2.0,
    "nlp": 2.0,
    "natural language": 2.0,
    "time series": 2.0,
    "time-series": 2.0,
    "forecasting": 2.0,
    "multimodal": 2.0,
    "multi-modal": 2.0,
    "vision-language": 2.0,
    "transformer": 1.0,
    "foundation model": 2.0,
    "recommendation": 2.0,
    "data science": 1.0,
    "机器学习": 1.5,
    "深度学习": 1.5,
    "多模态": 2.0,
    "时序预测": 2.0,
    "大模型": 2.5,
    "推荐算法": 2.0,
    "语音算法": 2.0,
    "语音识别": 1.8,
    "音频算法": 1.8,
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return data


def normalize(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("–", "-").replace("—", "-").replace("‑", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def term_present(text: str, term: str) -> bool:
    """Match a term without short-token substring false positives."""

    text = normalize(text)
    term = normalize(term)
    if not term:
        return False
    if term == " ai ":
        return bool(re.search(r"(?<![a-z0-9])ai(?![a-z0-9])", text))
    if re.fullmatch(r"[a-z0-9+#. -]+", term):
        return bool(
            re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text)
        )
    return term in text


def first_present(text: str, aliases: Iterable[str]) -> bool:
    return any(term_present(text, alias) for alias in aliases)


def signal_score(text: str, signals: dict[str, float]) -> float:
    return sum(weight for term, weight in signals.items() if term_present(text, term))


def stable_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = normalize(value)
        if value and key not in seen:
            seen.add(key)
            output.append(value)
    return output


def split_clauses(text: str) -> list[str]:
    raw_lines = re.split(r"[\r\n]+", text)
    clauses: list[str] = []
    for raw_line in raw_lines:
        line = raw_line.strip(" \t-*•")
        if not line:
            continue
        parts = re.split(r"(?<=[.!?。；;])\s*", line)
        clauses.extend(part.strip() for part in parts if part.strip())
    return clauses


def nested_get(mapping: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


@dataclass(frozen=True)
class ParsedJD:
    education_requirements: list[str]
    experience_requirements: list[str]
    required_skills: list[str]
    preferred_skills: list[str]
    domain_requirements: list[str]
    tool_requirements: list[str]
    project_preferences: list[str]
    language_requirements: list[str]
    location_requirements: list[str]
    hard_constraints: list[str]
    soft_requirements: list[str]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "education_requirements": self.education_requirements,
            "experience_requirements": self.experience_requirements,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "domain_requirements": self.domain_requirements,
            "tool_requirements": self.tool_requirements,
            "project_preferences": self.project_preferences,
            "language_requirements": self.language_requirements,
            "location_requirements": self.location_requirements,
            "hard_constraints": self.hard_constraints,
            "soft_requirements": self.soft_requirements,
        }


class JobMatcher:
    """Evidence-grounded matcher with no external side effects."""

    def __init__(
        self,
        resume_path: Path = DEFAULT_RESUME,
        profile_path: Path = DEFAULT_PROFILE,
        scoring_path: Path = DEFAULT_SCORING,
        eligibility_path: Path = DEFAULT_ELIGIBILITY,
    ) -> None:
        self.resume_path = Path(resume_path)
        self.profile_path = Path(profile_path)
        self.scoring_path = Path(scoring_path)
        self.eligibility_path = Path(eligibility_path)
        self.resume = load_yaml(self.resume_path)
        self.profile = load_yaml(self.profile_path)
        self.scoring = load_yaml(self.scoring_path)
        self.eligibility_policy = load_yaml(self.eligibility_path)
        self._validate_configuration()
        self.candidate_levels = self._build_candidate_levels()
        self.project_names = set(nested_get(self.resume, "projects", default={}).keys())
        self.soft_gap_names = self._profile_soft_gaps()
        self.medical_exploratory_signals = self._profile_medical_exploratory_signals()
        self.direct_cv_transfer = self._profile_direct_cv_transfer()

    def _validate_configuration(self) -> None:
        dimensions = nested_get(self.scoring, "scoring", "dimensions", default={})
        expected = {
            "common_technical_core": 25,
            "track_domain_match": 25,
            "project_evidence": 20,
            "education_background_fit": 15,
            "engineering_tools": 10,
            "technical_role_relevance": 5,
        }
        actual = {key: nested_get(dimensions, key, "weight") for key in expected}
        if actual != expected or sum(expected.values()) != 100:
            raise ValueError(
                "scoring.yaml must define the fixed 25/25/20/15/10/5 framework"
            )
        method = nested_get(self.scoring, "final_score_rule", "method")
        if method != "best_relevant_track":
            raise ValueError("final_score_rule.method must be best_relevant_track")
        statuses = nested_get(
            self.eligibility_policy, "eligibility", "statuses", default=[]
        )
        if statuses != ["eligible", "uncertain", "ineligible"]:
            raise ValueError(
                "eligibility_policy.yaml must define eligible/uncertain/ineligible"
            )

    def _level(self, *path: str, default: float = 0.0) -> float:
        value = nested_get(self.resume, *path)
        if isinstance(value, bool):
            return 0.8 if value else 0.0
        return LEVEL_VALUE.get(normalize(value), default)

    def _build_candidate_levels(self) -> dict[str, float]:
        levels = {
            "Python": self._level("skills", "programming", "Python", "level"),
            "PyTorch": self._level("skills", "programming", "PyTorch", "level"),
            "MATLAB": self._level("skills", "programming", "MATLAB", "level"),
            "C++": self._level("skills", "programming", "C++", "level"),
            "NumPy": self._level("skills", "data_and_image_tools", "NumPy", "level"),
            "OpenCV": self._level("skills", "data_and_image_tools", "OpenCV", "level"),
            "SimpleITK": self._level(
                "skills", "data_and_image_tools", "SimpleITK", "level"
            ),
            "Pandas": self._level("skills", "data_and_image_tools", "Pandas", "level"),
            "scikit-learn": self._level(
                "skills", "data_and_image_tools", "scikit_learn", "level"
            ),
            "Git": self._level("skills", "engineering", "Git", "level"),
            "Linux": self._level("skills", "engineering", "Linux", "level"),
            "Linux server": self._level(
                "skills", "engineering", "Linux_server", "level"
            ),
            "Docker": self._level("skills", "engineering", "Docker", "level"),
            "ONNX": self._level("skills", "engineering", "ONNX", "level"),
            "TensorRT": self._level("skills", "engineering", "TensorRT", "level"),
            "CUDA": self._level("skills", "engineering", "CUDA", "level"),
            "Distributed training": self._level(
                "skills", "engineering", "multi_gpu_training", "level"
            ),
            "CNN": self._level("skills", "deep_learning_models", "CNN", "level"),
            "RNN/LSTM": self._level(
                "skills", "deep_learning_models", "RNN_LSTM", "level"
            ),
            "Transformer": self._level(
                "skills", "deep_learning_models", "Transformer", "level"
            ),
            "U-Net": self._level("skills", "deep_learning_models", "U_Net", "level"),
            "nnU-Net": self._level(
                "skills", "deep_learning_models", "nnU_Net", "level"
            ),
            "Deep Learning": self._level(
                "skills", "deep_learning_workflow", "model_training"
            ),
            "Machine Learning": self._level(
                "skills", "deep_learning_workflow", "model_design"
            ),
            "Computer Vision": 0.8
            if "medical_cv_segmentation_project" in nested_get(self.resume, "projects", default={})
            else 0.0,
            "Image segmentation": 0.9
            if nested_get(
                self.resume, "medical_imaging", "main_expertise", "image_segmentation"
            )
            else 0.0,
            "Object detection": self._level(
                "medical_imaging", "additional_topics", "detection", "level"
            ),
            "3D Vision": 0.45
            if nested_get(
                self.resume,
                "medical_imaging",
                "main_expertise",
                "3D_medical_image_processing",
            )
            else 0.0,
            "Image reconstruction": self._level(
                "medical_imaging", "additional_topics", "reconstruction", "level"
            ),
            "Image enhancement": self._level(
                "medical_imaging", "additional_topics", "enhancement", "level"
            ),
            "Video understanding": 0.0,
            "Recommendation": 0.0,
            "Speech algorithms": 0.35
            if "multimodal_fusion_project" in nested_get(self.resume, "projects", default={})
            else 0.0,
            "Embedded systems": 0.0,
            "FPGA": 0.0,
            "Radar algorithms": 0.35,
            "Integrated sensing and communication": 0.55,
            "Time-series modeling": 1.0
            if "wireless_temporal_feedback_project"
            in nested_get(self.resume, "projects", default={})
            else 0.0,
            "Multimodal learning": 0.9
            if nested_get(
                self.resume, "projects", "multimodal_fusion_project", "ownership"
            ) == "major_contributor"
            else 0.0,
        }
        # Intentionally absent: Java, C#, React, production deployment, LLM,
        # and agent experience. Missing facts remain zero rather than inferred.
        return levels

    def _profile_soft_gaps(self) -> set[str]:
        configured = nested_get(self.profile, "soft_gap", "engineering", default=[])
        result: set[str] = set()
        for raw in configured:
            key = normalize(raw).replace("_", " ")
            for canonical in SKILL_ALIASES:
                if normalize(canonical) == key:
                    result.add(canonical)
                    break
            else:
                if key == "large scale distributed training":
                    result.add("Distributed training")
        return result

    def _profile_medical_exploratory_signals(self) -> dict[str, float]:
        configured = nested_get(
            self.profile, "keywords", "medical_exploratory", default=[]
        )
        if not isinstance(configured, list) or not configured:
            raise ValueError("profile.yaml must define keywords.medical_exploratory")
        return {
            normalize(term): MEDICAL_EXPLORATORY_SIGNALS.get(normalize(term), 0.8)
            for term in configured
            if normalize(term)
        }

    def _profile_direct_cv_transfer(self) -> dict[str, Any]:
        """Load the optional profile-controlled direct-CV transfer lane."""

        configured = nested_get(self.profile, "direct_cv_transfer", default={})
        if not isinstance(configured, dict):
            configured = {}
        enabled = bool(configured.get("enabled", False))
        raw_signals = configured.get("signals", [])
        signals = [normalize(term) for term in raw_signals if normalize(term)]
        if not signals:
            signals = list(DIRECT_CV_TRANSFER_SIGNALS)
        raw_blocked = configured.get("blocked_core_signals", [])
        blocked = [normalize(term) for term in raw_blocked if normalize(term)]
        if not blocked:
            blocked = list(DIRECT_CV_BLOCKED_CORE_SIGNALS)
        return {
            "enabled": enabled,
            "signals": tuple(stable_unique(signals)),
            "blocked_core_signals": tuple(stable_unique(blocked)),
            "priority": str(configured.get("priority", "P1")),
        }

    def _direct_cv_transfer_info(self, title: str, text: str) -> dict[str, Any]:
        """Return auditable evidence for the direct-CV transfer lane."""

        config = self.direct_cv_transfer
        combined = f"{title}\n{text}"
        if not config["enabled"]:
            return {
                "eligible": False,
                "signals": [],
                "blocked_core_signals": [],
            }
        present = [
            term
            for term in config["signals"]
            if term_present(combined, term)
        ]
        blocked = [
            term
            for term in config["blocked_core_signals"]
            if term_present(combined, term)
        ]
        title_present = [
            term
            for term in config["signals"]
            if term_present(title, term)
        ]
        technical_context = any(
            term_present(combined, term)
            for term in (
                "算法",
                "algorithm",
                "模型",
                "model",
                "开发",
                "研发",
                "训练",
                "pytorch",
                "opencv",
                "tensorflow",
                "深度学习",
                "机器学习",
            )
        )
        # A title-level CV signal is sufficient; otherwise require two
        # independent explicit CV signals in the JD.  This keeps generic AI
        # roles out while allowing direct CV roles whose application domain is
        # not medical.
        eligible = bool(
            not blocked
            and technical_context
            and (title_present or len(present) >= 2)
            and signal_score(combined, DIRECT_CV_TRANSFER_SIGNALS) >= 1.8
        )
        return {
            "eligible": eligible,
            "signals": stable_unique(present),
            "blocked_core_signals": stable_unique(blocked),
        }

    def _hard_constraints(self, title: str, text: str) -> list[str]:
        """Return only safety/content rejects; qualifications live in eligibility."""

        combined = normalize(f"{title}\n{text}")
        constraints: list[str] = []

        title_sales = any(
            phrase in normalize(title)
            for phrase in (
                "sales development representative",
                "sales representative",
                "telephone sales",
                "account executive",
                "business development representative",
                "电话销售",
                "销售代表",
            )
        )
        pure_sales_duties = (
            sum(
                phrase in combined
                for phrase in (
                    "cold call",
                    "cold calling",
                    "prospecting",
                    "sales quota",
                    "book meetings",
                    "generate pipeline",
                    "lead qualification",
                    "电话销售",
                    "销售指标",
                )
            )
            >= 2
        )
        if title_sales or pure_sales_duties:
            constraints.append("岗位内容硬冲突：职责为纯销售或电话拓客")

        if any(
            phrase in combined
            for phrase in (
                "paid training",
                "training fee",
                "application fee",
                "security deposit",
                "培训贷",
                "付费培训",
                "收取押金",
                "提前支付费用",
                "以招聘名义收费",
            )
        ):
            constraints.append("安全硬冲突：招聘信息涉及培训费、押金或提前付费")

        return stable_unique(constraints)

    def parse_jd(self, job: dict[str, Any]) -> ParsedJD:
        title = str(job.get("job_title") or "")
        text = str(job.get("jd_text") or "")
        combined = f"{title}\n{text}"
        clauses = split_clauses(text)

        education = [
            clause
            for clause in clauses
            if any(
                term_present(clause, term)
                for term in (
                    "bachelor",
                    "master",
                    "msc",
                    "phd",
                    "degree",
                    "本科",
                    "硕士",
                    "博士",
                    "学历",
                )
            )
        ]
        experience = [
            clause
            for clause in clauses
            if re.search(r"\b\d+\s*(?:-|to|\+)\s*\d*\s*years?", normalize(clause))
            or re.search(r"\b\d+\+?\s*years?", normalize(clause))
            or re.search(r"\d+\s*(?:-|至|到)\s*\d+\s*年", normalize(clause))
            or re.search(r"\d+\s*年(?:及|以)?上", normalize(clause))
            or any(
                phrase in normalize(clause)
                for phrase in (
                    "freshers",
                    "professional experience",
                    "work experience",
                    "应届生",
                    "工作经验",
                    "社招",
                )
            )
        ]

        required: list[str] = []
        preferred: list[str] = []
        for canonical, aliases in SKILL_ALIASES.items():
            mentions = [clause for clause in clauses if first_present(clause, aliases)]
            if not mentions and first_present(title, aliases):
                mentions = [title]
            if not mentions:
                continue
            preferred_only = all(
                any(marker in normalize(clause) for marker in PREFERRED_MARKERS)
                for clause in mentions
            )
            required_any = any(
                any(marker in normalize(clause) for marker in REQUIRED_MARKERS)
                for clause in mentions
            )
            if preferred_only:
                preferred.append(canonical)
            elif required_any or mentions:
                required.append(canonical)

        domain_terms = [
            term
            for term in (
                list(COMM_SIGNALS)
                + list(MEDICAL_STRONG_SIGNALS)
                + list(CV_SIGNALS)
                + list(self.medical_exploratory_signals)
                + list(GENERAL_SIGNALS)
            )
            if term_present(combined, term)
        ]
        tools = [
            skill
            for skill in required + preferred
            if skill in ENGINEERING_TOOLS
        ]
        project_preferences = [
            clause
            for clause in clauses
            if any(
                marker in normalize(clause)
                for marker in (
                    "project experience",
                    "research experience",
                    "publication",
                    "papers",
                    "项目经验",
                    "科研经历",
                    "论文",
                )
            )
        ]
        language_requirements = [
            clause
            for clause in clauses
            if any(
                term_present(clause, term)
                for term in (
                    "english",
                    "chinese",
                    "mandarin",
                    "cet-4",
                    "cet-6",
                    "英语",
                    "中文",
                    "四级",
                    "六级",
                )
            )
        ]
        location_requirements = [
            clause
            for clause in clauses
            if any(
                phrase in normalize(clause)
                for phrase in (
                    "on-site",
                    "onsite",
                    "hybrid",
                    "visa",
                    "work authorization",
                    "legally authorized",
                    "citizens",
                    "relocation",
                    "现场办公",
                    "工作许可",
                )
            )
        ]

        soft_requirements = [
            clause
            for clause in clauses
            if any(marker in normalize(clause) for marker in PREFERRED_MARKERS)
        ]
        hard = self._hard_constraints(title, text)
        return ParsedJD(
            education_requirements=stable_unique(education),
            experience_requirements=stable_unique(experience),
            required_skills=stable_unique(required),
            preferred_skills=stable_unique(preferred),
            domain_requirements=stable_unique(domain_terms),
            tool_requirements=stable_unique(tools),
            project_preferences=stable_unique(project_preferences),
            language_requirements=stable_unique(language_requirements),
            location_requirements=stable_unique(location_requirements),
            hard_constraints=hard,
            soft_requirements=stable_unique(soft_requirements),
        )

    def _track_classification(self, title: str, text: str) -> dict[str, Any]:
        combined = f"{title}\n{text}"
        comm_raw = signal_score(combined, COMM_SIGNALS)
        med_strong_raw = signal_score(combined, MEDICAL_STRONG_SIGNALS)
        cv_raw = signal_score(combined, CV_SIGNALS)
        med_explore_raw = signal_score(combined, self.medical_exploratory_signals)
        general_raw = signal_score(combined, GENERAL_SIGNALS)
        direct_cv = self._direct_cv_transfer_info(title, text)

        comm_title = signal_score(title, COMM_SIGNALS)
        med_title = signal_score(title, MEDICAL_STRONG_SIGNALS) + signal_score(
            title, CV_SIGNALS
        )
        general_title = signal_score(title, GENERAL_SIGNALS)

        confidences = {
            "communication_ai": min(1.0, (comm_raw + 0.8 * comm_title) / 9.0),
            "medical_cv": min(
                1.0,
                (
                    med_strong_raw
                    + cv_raw
                    + 0.35 * med_explore_raw
                    + 0.8 * med_title
                )
                / 9.0,
            ),
            "general_ai": min(1.0, (general_raw + 0.8 * general_title) / 9.0),
        }

        if med_title >= 1.5 and med_title > comm_title:
            primary = "medical_cv"
        elif (
            comm_title >= 2.0
            or (comm_raw >= 3.5 and comm_raw >= med_strong_raw + cv_raw)
        ):
            primary = "communication_ai"
        elif direct_cv["eligible"] and med_strong_raw == 0:
            # Explicit non-medical CV roles belong to the P1 transfer lane.
            # The track remains medical_cv so the score uses the candidate's
            # verified CV/medical-image evidence, while preference_fit marks
            # the result as transfer-only.
            primary = "medical_cv"
        elif (
            med_title >= 1.5
            or (
                med_strong_raw + cv_raw >= 3.5
                and med_strong_raw + cv_raw > comm_raw
            )
        ):
            primary = "medical_cv"
        elif general_title >= 1.2:
            primary = "general_ai"
        else:
            primary = max(TRACKS, key=lambda track: (confidences[track], -TRACKS.index(track)))
            if max(confidences.values()) < 0.18:
                primary = "general_ai"

        reasons = {
            "communication_ai": "标题或职责以无线通信、PHY、RAN、信号处理或雷达为核心",
            "medical_cv": "标题或职责以医学图像、图像处理、分割或计算机视觉为核心；非医学 CV 仅按迁移能力给证据",
            "general_ai": "标题或职责以通用机器学习、深度学习、时序、多模态或大模型为核心",
        }
        if max(confidences.values()) < 0.18:
            reason = "未发现稳定的主线领域信号；以 general_ai 作为低置信度兜底路线"
        elif direct_cv["eligible"] and primary == "medical_cv" and med_strong_raw == 0:
            reason = "直接计算机视觉/图像算法岗位；按医学图像经验做 P1 技能迁移评估，不宣称目标应用场景的直接项目经历"
        else:
            reason = reasons[primary]
        return {
            "primary_track": primary,
            "communication_confidence": round(confidences["communication_ai"], 3),
            "medical_cv_confidence": round(confidences["medical_cv"], 3),
            "general_ai_confidence": round(confidences["general_ai"], 3),
            "direct_cv_transfer": bool(
                direct_cv["eligible"] and primary == "medical_cv" and med_strong_raw == 0
            ),
            "direct_cv_signals": direct_cv["signals"],
            "blocked_core_signals": direct_cv["blocked_core_signals"],
            "reason": reason,
        }

    def _common_score(self, parsed: ParsedJD, combined: str) -> int:
        if any("纯销售" in item for item in parsed.hard_constraints):
            return 0
        common_core_skills = {
            "Python",
            "PyTorch",
            "TensorFlow",
            "MATLAB",
            "C++",
            "Java",
            "C#",
            "Deep Learning",
            "Machine Learning",
            "CNN",
            "RNN/LSTM",
            "Transformer",
            "U-Net",
            "nnU-Net",
        }
        common = [
            skill for skill in parsed.required_skills if skill in common_core_skills
        ]
        common = stable_unique(common)
        if not common:
            if signal_score(combined, COMM_SIGNALS) >= 2 or (
                signal_score(combined, MEDICAL_STRONG_SIGNALS)
                + signal_score(combined, CV_SIGNALS)
                >= 2
            ):
                return 14
            if signal_score(combined, GENERAL_SIGNALS) >= 1.0:
                return 15
            if any(
                token in normalize(combined)
                for token in ("engineer", "developer", "scientist", "算法", "研发")
            ):
                return 7
            return 1
        values = [self.candidate_levels.get(skill, 0.0) for skill in common]
        alternatives = any(
            marker in normalize(combined)
            for marker in (
                "至少一种",
                "至少一门",
                "任一种",
                "one of",
                "at least one",
            )
        ) or bool(re.search(r"(?:c/c\+\+|c\+\+)\s*(?:或|or)\s*python", normalize(combined)))
        ratio = max(values) if alternatives else sum(values) / len(values)
        return max(0, min(25, round(25 * ratio)))

    def _domain_score(self, track: str, combined: str) -> int:
        if track == "communication_ai":
            raw = signal_score(combined, COMM_SIGNALS)
            if raw == 0:
                return 2 if signal_score(combined, GENERAL_SIGNALS) else 0
            return min(25, round(4 + 21 * min(1.0, raw / 9.0)))

        if track == "medical_cv":
            medical = signal_score(combined, MEDICAL_STRONG_SIGNALS)
            cv = signal_score(combined, CV_SIGNALS)
            exploratory = signal_score(combined, self.medical_exploratory_signals)
            direct = medical + cv
            if direct == 0:
                return min(10, round(3 + 4 * exploratory)) if exploratory else 0
            score = min(25, round(5 + 20 * min(1.0, direct / 9.0)))
            if "clinical data analyst" in normalize(combined) or (
                "annotate" in normalize(combined)
                and "develop model" not in normalize(combined)
                and "build model" not in normalize(combined)
            ):
                score = min(score, 10)
            return score

        raw = signal_score(combined, GENERAL_SIGNALS)
        if raw == 0:
            return 1 if "engineer" in normalize(combined) else 0
        score = min(25, round(5 + 20 * min(1.0, raw / 8.0)))
        if first_present(combined, SKILL_ALIASES["LLM"]) and not any(
            term_present(combined, term)
            for term in ("time series", "multimodal", "computer vision")
        ):
            score = min(score, 10)
        return score

    def _project_score_and_evidence(
        self, track: str, combined: str
    ) -> tuple[int, list[dict[str, str]], list[str]]:
        evidence: list[dict[str, str]] = []
        transferable: list[str] = []

        def add(project: str, detail: str, evidence_type: str = "direct") -> None:
            if project in self.project_names:
                evidence.append(
                    {
                        "project": project,
                        "evidence": detail,
                        "evidence_type": evidence_type,
                    }
                )

        if track == "communication_ai":
            if any(
                term_present(combined, term)
                for term in (
                    "radar",
                    "雷达",
                    "integrated sensing and communication",
                    "isac",
                    "通信感知一体化",
                    "通感一体化",
                )
            ):
                add(
                    "wireless_temporal_feedback_project",
                    "CSI、时变信道与信号处理方法可迁移；不是雷达或感知直接项目经历",
                    "transferable",
                )
                transferable.extend(
                    ["信号处理理论", "时序建模", "MATLAB/Python 仿真"]
                )
                return 10, evidence, transferable
            if any(
                term_present(combined, term)
                for term in (
                    "csi",
                    "massive mimo",
                    "channel prediction",
                    "channel estimation",
                    "feedback",
                    "resource allocation",
                )
            ):
                add(
                    "wireless_temporal_feedback_project",
                    "Massive MIMO、CSI 反馈、时变信道预测与自适应决策",
                )
                add("wireless_adaptive_compression_project", "CSI 反馈、自适应压缩与轻量模型")
                add("wireless_resource_allocation_project", "严格反馈预算、资源分配与轻量网络")
                return 20, evidence, transferable
            if any(
                term_present(combined, term)
                for term in ("ofdm", "phy", "physical layer", "ran", "baseband", "rf", "dsp")
            ):
                add(
                    "wireless_temporal_feedback_project",
                    "无线信道、链路指标和 MATLAB/Python 仿真经验可迁移",
                    "transferable",
                )
                transferable.extend(["OFDM/MIMO/CSI 理论基础", "链路级仿真与结果分析"])
                return 13, evidence, transferable
            if signal_score(combined, GENERAL_SIGNALS) and signal_score(
                combined, COMM_SIGNALS
            ) < 1:
                add(
                    "wireless_temporal_feedback_project",
                    "深度学习建模、训练和严谨实验流程可迁移",
                    "transferable",
                )
                return 7, evidence, transferable
            if any(
                term_present(combined, term)
                for term in ("wireless", "5g", "6g", "无线", "通信")
            ):
                add(
                    "wireless_temporal_feedback_project",
                    "无线通信、CSI与算法实验流程可迁移；岗位未给出更细的项目要求",
                    "transferable",
                )
                transferable.extend(["通信工程专业背景", "无线通信科研方法"])
                return 11, evidence, transferable
            return 0, evidence, transferable

        if track == "medical_cv":
            is_medical = any(
                term_present(combined, term)
                for term in (
                    "medical",
                    "mri",
                    "ct",
                    "dicom",
                    "radiology",
                    "医学",
                    "医疗影像",
                    "医疗产品",
                    "医学信号",
                    "超声",
                )
            )
            if "clinical data analyst" in normalize(combined) or (
                "annotate" in normalize(combined)
                and "develop model" not in normalize(combined)
                and "build model" not in normalize(combined)
            ):
                transferable.extend(["DICOM/医学图像数据处理基础", "结果分析"])
                return 4, evidence, transferable
            if any(
                term_present(combined, term)
                for term in (
                    "segmentation",
                    "图像分割",
                    "语义分割",
                    "实例分割",
                    "分割",
                    "u-net",
                    "unet",
                    "nnunet",
                )
            ):
                if is_medical:
                    add(
                        "medical_cv_segmentation_project",
                        "CT/MRI 3D 医学图像分割、U-Net/Transformer、训练验证与消融",
                    )
                else:
                    add(
                        "medical_cv_segmentation_project",
                        "医学图像分割中的视觉建模和实验方法可迁移；不是该行业直接项目",
                        "transferable",
                    )
                return (20 if is_medical else 17), evidence, transferable
            if is_medical and any(
                term_present(combined, term)
                for term in self.medical_exploratory_signals
            ):
                add(
                    "medical_cv_segmentation_project",
                    "医学图像数据处理与模型训练可迁移；具体任务不是已验证直接项目",
                    "transferable",
                )
                transferable.extend(
                    ["3D 医学图像处理基础", "Python/PyTorch 模型训练", "OpenCV/SimpleITK"]
                )
                return 9, evidence, transferable
            if signal_score(combined, CV_SIGNALS):
                add(
                    "medical_cv_segmentation_project",
                    "3D 医学图像分割中的视觉建模、数据处理和消融方法可迁移；不是目标行业直接项目",
                    "transferable",
                )
                transferable.extend(
                    [
                        "视觉 Transformer 与 U-Net 建模",
                        "Python/PyTorch 训练验证",
                        "图像预处理、可视化与结果分析",
                    ]
                )
                return 12, evidence, transferable
            if any(
                term_present(combined, term)
                for term in ("computer vision", "image processing", "medical imaging")
            ):
                add(
                    "medical_cv_segmentation_project",
                    "视觉模型设计、数据预处理和实验分析能力可迁移",
                    "transferable",
                )
                return 9, evidence, transferable
            if signal_score(combined, GENERAL_SIGNALS):
                add(
                    "medical_cv_segmentation_project",
                    "深度学习和视觉 Transformer 训练流程可迁移",
                    "transferable",
                )
                return 6, evidence, transferable
            return 0, evidence, transferable

        heading = normalize(combined.splitlines()[0] if combined.splitlines() else combined)
        if first_present(heading, SKILL_ALIASES["LLM"]) and not first_present(
            heading, SKILL_ALIASES["Multimodal learning"]
        ):
            transferable.extend(["Transformer 基础", "模型训练、消融和量化实验流程"])
            return 4, evidence, transferable
        if first_present(heading, SKILL_ALIASES["Recommendation"]):
            transferable.extend(["深度学习建模", "排序与资源分配思路", "实验分析"])
            return 6, evidence, transferable
        if first_present(combined, SKILL_ALIASES["Time-series modeling"]):
            add("wireless_temporal_feedback_project", "RNN/LSTM 时序预测、泛化与鲁棒性分析")
            return 18, evidence, transferable
        if first_present(combined, SKILL_ALIASES["Multimodal learning"]):
            add("multimodal_fusion_project", "门控、残差融合与音视频特征融合")
            return 18, evidence, transferable
        if first_present(combined, SKILL_ALIASES["LLM"]):
            transferable.extend(["Transformer 基础", "模型训练、消融和量化实验流程"])
            return 4, evidence, transferable
        if first_present(combined, SKILL_ALIASES["Recommendation"]):
            transferable.extend(["深度学习建模", "排序与资源分配思路", "实验分析"])
            return 6, evidence, transferable
        if first_present(combined, SKILL_ALIASES["Speech algorithms"]):
            add(
                "multimodal_fusion_project",
                "音视频特征融合方法可迁移；不是语音识别或语音合成直接项目",
                "transferable",
            )
            return 8, evidence, transferable
        if signal_score(combined, GENERAL_SIGNALS):
            add("wireless_temporal_feedback_project", "独立完成深度学习模型设计、训练和实验分析")
            add("medical_cv_segmentation_project", "视觉 Transformer、验证和消融实验")
            return 14, evidence, transferable
        return 0, evidence, transferable

    def _experience_years(self, combined: str) -> int | None:
        text = normalize(combined)
        numbers: list[int] = []
        for match in re.finditer(r"\b(\d+)\s*(?:-|to|\+)\s*(\d*)\s*years?", text):
            numbers.append(int(match.group(1)))
        for match in re.finditer(r"\b(\d+)\+?\s*years?", text):
            numbers.append(int(match.group(1)))
        for match in re.finditer(r"(\d+)\s*(?:-|至|到)\s*(\d+)\s*年", text):
            numbers.append(int(match.group(1)))
        for match in re.finditer(r"(\d+)\s*年(?:及|以)?上", text):
            numbers.append(int(match.group(1)))
        return max(numbers) if numbers else None

    def _education_background_score(self, track: str, combined: str) -> int:
        """Score technical academic background without using eligibility gates."""

        text = normalize(combined)
        if track == "communication_ai":
            score = 15 if signal_score(text, COMM_SIGNALS) >= 2 else 11
        elif track == "medical_cv":
            if signal_score(text, MEDICAL_STRONG_SIGNALS) >= 2:
                score = 13
            elif signal_score(text, CV_SIGNALS) >= 2:
                score = 12
            else:
                score = 10
        else:
            score = 11

        # Communication engineering is adjacent to electronics/information/AI,
        # but a narrowly clinical or mechanical background is not direct.
        if any(
            phrase in text
            for phrase in (
                "通信工程",
                "信息与通信工程",
                "电子信息",
                "信号与信息处理",
                "electrical engineering",
                "wireless communications",
            )
        ):
            score = max(score, 15 if track == "communication_ai" else 12)
        if any(
            phrase in text
            for phrase in ("仅限临床医学专业", "仅限机械工程专业", "clinical degree only")
        ):
            score = min(score, 6)
        return max(0, min(15, score))

    def _eligibility(
        self, job: dict[str, Any], title: str, combined: str, parsed: ParsedJD
    ) -> dict[str, Any]:
        """Evaluate application eligibility independently from technical scoring."""

        structured = " ".join(
            str(job.get(key) or "")
            for key in ("job_type", "graduation_cohort", "candidate_scope")
        )
        text = normalize(f"{title}\n{combined}\n{structured}")
        hard_conflicts: list[str] = []
        risks: list[str] = []
        notes: list[str] = []

        campus = any(
            marker in text
            for marker in ("校园招聘", "校招", "应届生", "提前批", "campus")
        )
        internship = any(
            marker in text for marker in ("实习", "实习生", "intern", "internship")
        )
        graduation_value = normalize(
            nested_get(self.resume, "candidate", "expected_graduation", default="")
        )
        graduation_match = re.search(r"(20\d{2})", graduation_value)
        candidate_cohort = int(graduation_match.group(1)) if graduation_match else None
        candidate_graduation_label = graduation_value or "未填写"
        cohort_matches_candidate = False
        if candidate_cohort is not None:
            short_cohort = str(candidate_cohort)[-2:]
            cohort_matches_candidate = bool(
                re.search(fr"(?:{candidate_cohort}|{short_cohort})\s*届", text)
                or re.search(
                    fr"{candidate_cohort}.{{0,12}}(?:校招|校园招聘|graduate|campus)",
                    text,
                )
                or normalize(job.get("graduation_cohort"))
                in {str(candidate_cohort), f"{candidate_cohort}届", f"{short_cohort}届"}
            )

        phd_flexible = bool(
            re.search(
                r"(?:master'?s?|msc|硕士)\s*(?:or|/|、|或|及|和)\s*(?:ph\.?d\.?|博士)|"
                r"(?:ph\.?d\.?|博士)\s*(?:or|/|、|或|及|和)\s*(?:master'?s?|msc|硕士)|"
                r"硕士(?:研究生)?及以上|master'?s?\s+(?:degree\s+)?or\s+above",
                text,
            )
        )
        phd_preferred = any(
            phrase in text
            for phrase in ("phd preferred", "ph.d. preferred", "博士优先")
        )
        phd_only = any(
            re.search(pattern, text)
            for pattern in (
                r"仅限博士",
                r"博士(?:研究生)?学历(?:，|,|。|;|；|$)",
                r"博士及以上",
                r"\bph\.?d\.?\s+(?:degree\s+)?(?:is\s+)?required\b",
                r"\brequires?\s+(?:a\s+)?ph\.?d\.?(?:\s+degree)?\b",
                r"\bmust\s+(?:hold|have|be pursuing)\s+(?:a\s+)?ph\.?d\.?\b",
            )
        )
        if (phd_only and not phd_flexible and not phd_preferred) or any(
            phrase in text for phrase in ("不接受硕士", "硕士不可投")
        ):
            hard_conflicts.append("学历资格冲突：岗位明确仅接受博士或明确不接受硕士")
        elif phd_preferred:
            notes.append("博士为优选条件，不构成硬性拒绝")

        cohorts = {
            int(value)
            for value in re.findall(r"(?<!\d)(20\d{2})\s*届", text)
        }
        explicit_other_cohort = bool(
            candidate_cohort is not None and cohorts and candidate_cohort not in cohorts
        )
        if explicit_other_cohort and (campus or internship):
            hard_conflicts.append(
                "毕业届次冲突：岗位明确面向 "
                + "/".join(str(year) for year in sorted(cohorts))
                + (f" 届，不包含候选人届次 {candidate_cohort}" if candidate_cohort is not None else " 届")
            )
        elif cohort_matches_candidate:
            notes.append(f"毕业届次匹配：候选人预计毕业时间 {candidate_graduation_label}")
        elif campus:
            if candidate_cohort is None:
                risks.append("候选人预计毕业时间未在事实库中明确，需人工确认")
            else:
                risks.append(
                    f"毕业窗口未明确包含候选人届次 {candidate_cohort}，需人工确认"
                )

        years = self._experience_years(combined)
        fulltime_experience = any(
            phrase in text
            for phrase in (
                "全职工作经验",
                "相关工作经验",
                "professional experience",
                "work experience",
                "仅限社招",
                "社招",
                "experienced hire",
                "experienced professionals only",
            )
        )
        if years is not None and years >= 2 and fulltime_experience and not (
            campus or internship
        ):
            hard_conflicts.append(
                f"经验资格冲突：非校招岗位明确要求至少 {years} 年相关全职经验"
            )

        if any(
            phrase in text
            for phrase in (
                "仅限本科且不接受硕士",
                "仅限本科生，不接受硕士",
                "仅限本科生且不接受硕士",
                "bachelor only; master's not accepted",
            )
        ):
            hard_conflicts.append("学历资格冲突：岗位明确排除硕士研究生")

        exclusive_major = any(
            phrase in text
            for phrase in (
                "仅限计算机科学专业且不接受其他专业",
                "仅限临床医学专业",
                "仅限机械工程专业",
                "only computer science majors; related majors not accepted",
            )
        )
        if exclusive_major:
            hard_conflicts.append("专业资格冲突：岗位明确限定候选人未具备的专业")
        elif any(
            phrase in text
            for phrase in ("专业要求详见", "专业范围以招聘系统为准", "限定专业目录")
        ):
            risks.append("专业限制信息不完整，候选人专业是否在目录内需人工确认")

        cet6 = any(
            phrase in text for phrase in ("cet-6", "cet6", "英语六级", "六级证书")
        )
        language_preferred = any(
            phrase in text for phrase in ("英语六级优先", "cet-6 preferred", "cet6优先")
        )
        if cet6 and not language_preferred:
            hard_conflicts.append(
                "语言资格冲突：岗位明确要求 CET-6，但事实库未确认 CET-6"
            )
        elif language_preferred:
            notes.append("CET-6 仅为优选条件，不构成硬性拒绝")
        if any(
            phrase in text
            for phrase in (
                "英语口语流利",
                "流利英语",
                "fluent english",
                "business english",
            )
        ):
            risks.append("语言熟练度要求较高，但事实库未明确确认流利英语能力")

        if any(
            phrase in text
            for phrase in (
                "work authorization",
                "legally authorized to work",
                "工作许可",
                "仅限中国公民",
                "户籍要求",
            )
        ):
            risks.append("工作许可、国籍或户籍资格未在事实库中确认")

        if internship:
            notes.append("实习可用性、到岗日期和时长仍需基于事实库与用户确认")
        if not (campus or internship) and not hard_conflicts:
            risks.append("岗位不是明确的目标届次校招/实习，申请窗口需人工确认")

        hard_conflicts = stable_unique(hard_conflicts)
        risks = stable_unique(risks)
        notes = stable_unique(notes)
        if hard_conflicts:
            status = "ineligible"
        elif risks:
            status = "uncertain"
        else:
            status = "eligible"
        return {
            "status": status,
            "hard_conflicts": hard_conflicts,
            "risks": risks,
            "notes": "；".join(notes) if notes else "无明显资格冲突",
        }

    def _tool_score(self, parsed: ParsedJD, combined: str) -> int:
        required = [s for s in parsed.required_skills if s in ENGINEERING_TOOLS]
        preferred = [s for s in parsed.preferred_skills if s in ENGINEERING_TOOLS]
        if not required and not preferred:
            return 7
        alternatives = any(
            marker in normalize(combined)
            for marker in (
                "至少一种",
                "至少一门",
                "任一种",
                "one of",
                "at least one",
            )
        ) or bool(re.search(r"(?:c/c\+\+|c\+\+)\s*(?:或|or)\s*python", normalize(combined)))
        if alternatives and any(
            self.candidate_levels.get(skill, 0.0) >= 0.75
            for skill in parsed.required_skills
        ):
            required = []
            if not preferred:
                return 7
        weighted_values: list[tuple[float, float]] = []
        for skill in required:
            weighted_values.append((self.candidate_levels.get(skill, 0.0), 2.0))
        for skill in preferred:
            weighted_values.append((self.candidate_levels.get(skill, 0.0), 1.0))
        denominator = sum(weight for _, weight in weighted_values)
        score = 10 * sum(value * weight for value, weight in weighted_values) / denominator
        return max(0, min(10, round(score)))

    def _technical_role_relevance(self, title: str, combined: str) -> int:
        """Score how clearly the duties are technical R&D, not company preference."""

        text = normalize(f"{title} {combined}")
        if any(word in text for word in ("cold call", "sales quota", "generate pipeline")):
            return 0
        if "intern" in normalize(title) or "student" in normalize(title):
            return 5
        if any(
            word in text
            for word in (
                "research",
                "研究",
                "algorithm",
                "machine learning",
                "deep learning",
                "medical imaging",
                "wireless",
                "算法",
                "研发",
                "仿真",
                "图像处理",
            )
        ):
            return 5
        if any(
            word in normalize(title)
            for word in ("engineer", "developer", "scientist", "工程师")
        ):
            return 3
        return 1

    def _cpp_requirement(self, parsed: ParsedJD, combined: str) -> str:
        text = normalize(combined)
        if not first_present(text, SKILL_ALIASES["C++"]):
            return "none"
        if any(
            phrase in text
            for phrase in (
                "未把c++列为唯一必需语言",
                "未把 c++ 列为唯一必需语言",
                "c++ is not required",
                "c++ not required",
            )
        ):
            return "none"
        if any(
            phrase in text
            for phrase in (
                "大型c++工程",
                "大型 c++ 工程",
                "以c++为主要开发语言",
                "以 c++ 为主要开发语言",
                "主要使用c++",
                "主要使用 c++",
                "c++为主",
                "c++ 为主",
                "c++开发工程师",
                "c++ software engineer",
            )
        ) or (
            first_present(text, SKILL_ALIASES["Embedded systems"])
            and any(phrase in text for phrase in ("嵌入式部署", "embedded deployment"))
        ):
            return "cpp_heavy"
        if any(
            phrase in text
            for phrase in (
                "任一种",
                "至少一种",
                "one of",
                "c++或python",
                "c++ or python",
                "python或c++",
                "python or c++",
                "c/c++或python",
                "c/c++ or python",
                "python、c或c++",
                "python, c or c++",
                "部分方向要求python/c++",
                "部分方向要求 python/c++",
                "matlab或c/c++",
                "matlab or c++",
                "至少熟练一门",
                "c/c++基础",
                "c++基础",
            )
        ):
            return "bonus_only"
        if "C++" in parsed.preferred_skills:
            return "preferred"
        if "C++" in parsed.required_skills:
            return "core_required"
        return "bonus_only"

    def _role_preference(self, title: str, combined: str) -> str:
        text = normalize(f"{title} {combined}")
        direct_cv = self._direct_cv_transfer_info(title, combined)
        if any(
            phrase in text
            for phrase in (
                "通信感知一体化",
                "通感一体化",
                "integrated sensing and communication",
                "雷达算法",
                "radar algorithm",
                "多模态算法",
                "multimodal algorithm",
            )
        ):
            return "P1_direct"
        if any(
            phrase in text
            for phrase in (
                "大模型",
                "large language model",
                "llm",
                "推荐算法",
                "recommendation",
                "语音算法",
                "语音识别",
                "speech",
                "音频算法",
                "嵌入式",
                "embedded",
                "fpga",
            )
        ):
            return "P1_transfer"
        if direct_cv["eligible"] and signal_score(text, MEDICAL_STRONG_SIGNALS) == 0:
            return "P1_transfer"
        if signal_score(text, COMM_SIGNALS) >= 2 or (
            signal_score(text, MEDICAL_STRONG_SIGNALS) + signal_score(text, CV_SIGNALS)
            >= 2
        ):
            return "P0"
        if signal_score(text, GENERAL_SIGNALS) >= 1:
            return "P1"
        return "unclassified"

    def _preference_fit(
        self,
        job: dict[str, Any],
        title: str,
        combined: str,
        parsed: ParsedJD,
        primary_track: str,
        project_evidence: list[dict[str, str]],
    ) -> dict[str, Any]:
        text = normalize(f"{job.get('company') or ''} {job.get('company_type') or ''} {title} {combined}")
        company_type = normalize(job.get("company_type") or "")
        state_owned = company_type in {
            "state_owned",
            "state_owned_research_institute",
            "research_institute",
        } or any(
            phrase in text
            for phrase in (
                "state_owned",
                "state-owned",
                "国有企业",
                "国企",
                "央企",
                "研究院",
                "研究所",
                "实验室",
                "中国移动",
                "中国电信",
                "中国联通",
                "中国信通院",
            )
        )
        domain_score = self._domain_score(primary_track, combined)
        project_score = max(
            (20 if item.get("evidence_type") == "direct" else 10)
            for item in project_evidence
        ) if project_evidence else 0
        high_domain_match = domain_score >= 22 and project_score >= 10
        if primary_track == "communication_ai" and project_score >= 10 and any(
            phrase in text
            for phrase in (
                "5g-a",
                "6g无线",
                "6g 无线",
                "无线与下一代网络",
                "wireless and next-generation network",
            )
        ):
            high_domain_match = True

        if state_owned and high_domain_match:
            company_preference = "state_owned_high_match_override"
            state_owned_penalty = "none_high_domain_match_override"
            company_score = 80
        elif state_owned:
            company_preference = "state_owned_or_research_institute_low"
            state_owned_penalty = "default_low_priority"
            company_score = 55
        else:
            company_preference = "normal"
            state_owned_penalty = "none"
            company_score = 80

        role_preference = self._role_preference(title, combined)
        role_scores = {
            "P0": 90,
            "P1_direct": 82,
            "P1_transfer": 70,
            "P1": 76,
            "unclassified": 60,
        }
        cpp_requirement = self._cpp_requirement(parsed, combined)
        cpp_labels = {
            "none": "none",
            "bonus_only": "no_penalty",
            "preferred": "small_penalty",
            "core_required": "deprioritize_and_review",
            "cpp_heavy": "heavy_low_priority",
        }
        cpp_deductions = {
            "none": 0,
            "bonus_only": 0,
            "preferred": 4,
            "core_required": 12,
            "cpp_heavy": 20,
        }
        basic_cpp_requirement_met = cpp_requirement == "core_required" and any(
            phrase in text
            for phrase in ("c++基础", "c/c++基础", "了解c++", "了解 c++")
        )
        if basic_cpp_requirement_met:
            cpp_labels["core_required"] = "requirement_met_at_basic_level"
            cpp_deductions["core_required"] = 0
        score = round(
            (company_score + role_scores[role_preference]) / 2
            - cpp_deductions[cpp_requirement]
        )

        is_nonmedical_cv = (
            primary_track == "medical_cv"
            and signal_score(combined, CV_SIGNALS) > 0
            and signal_score(combined, MEDICAL_STRONG_SIGNALS) == 0
        )
        evidence_types = {item.get("evidence_type", "direct") for item in project_evidence}
        if not evidence_types:
            evidence_mode = "none"
        elif evidence_types == {"direct"}:
            evidence_mode = "direct_project_evidence"
        elif evidence_types == {"transferable"}:
            evidence_mode = "transferable_only"
        else:
            evidence_mode = "mixed"

        return {
            "score": max(0, min(100, score)),
            "company_preference": company_preference,
            "role_preference": role_preference,
            "cpp_penalty": cpp_labels[cpp_requirement],
            "state_owned_penalty": state_owned_penalty,
            "cpp_requirement": cpp_requirement,
            "state_owned_or_research_institute": state_owned,
            "high_domain_match_override": bool(state_owned and high_domain_match),
            "evidence_mode": evidence_mode,
            "transfer_only": bool(is_nonmedical_cv or role_preference == "P1_transfer"),
        }

    def _opportunity_priority(
        self,
        technical_score: int,
        grade: str,
        eligibility: dict[str, Any],
        preference: dict[str, Any],
        soft_gaps: list[dict[str, str]],
        hard_constraints: list[str],
    ) -> str:
        if hard_constraints or eligibility["status"] == "ineligible" or grade == "D":
            return "reject"
        if eligibility["status"] == "uncertain" or grade == "C":
            return "P2"
        if preference["cpp_penalty"] in {
            "deprioritize_and_review",
            "heavy_low_priority",
        }:
            return "P2"
        if (
            preference["state_owned_or_research_institute"]
            and not preference["high_domain_match_override"]
        ):
            return "P2"
        if preference["transfer_only"]:
            return "P1" if grade in {"S", "A", "B"} else "P2"
        if grade in {"S", "A"}:
            penalizing_gaps = any(
                gap.get("importance")
                in {"preferred", "core_required", "cpp_heavy"}
                for gap in soft_gaps
            )
            if penalizing_gaps or preference["role_preference"] in {
                "P1",
                "P1_direct",
                "P1_transfer",
            }:
                return "P1"
            return "P0"
        if grade == "B":
            return "P1"
        return "reject" if technical_score < 55 else "P2"

    def _soft_gaps(self, parsed: ParsedJD, combined: str) -> list[dict[str, str]]:
        gaps: list[dict[str, str]] = []
        cpp_requirement = self._cpp_requirement(parsed, combined)
        for skill in sorted(self.soft_gap_names):
            aliases = SKILL_ALIASES.get(skill, (skill,))
            if not first_present(combined, aliases):
                continue
            candidate_value = self.candidate_levels.get(skill, 0.0)
            if candidate_value >= 0.75:
                continue
            if skill == "C++" and any(
                phrase in normalize(combined)
                for phrase in ("c++基础", "c/c++基础", "了解c++", "了解 c++")
            ):
                continue
            if skill == "C++":
                importance = cpp_requirement
                effect = {
                    "none": "none",
                    "bonus_only": "no_rejection",
                    "preferred": "small_penalty_only",
                    "core_required": "penalize_and_review",
                    "cpp_heavy": "deprioritize_and_review",
                }[cpp_requirement]
                if cpp_requirement == "none":
                    continue
            elif skill in parsed.required_skills:
                importance = "core_required"
                effect = "penalize_and_review"
            elif skill in parsed.preferred_skills:
                importance = "preferred"
                effect = "small_penalty_only"
            else:
                importance = "bonus_only"
                effect = "no_rejection"
            level = "basic" if candidate_value > 0 else "not_evidenced"
            gaps.append(
                {
                    "skill": skill,
                    "importance": importance,
                    "candidate_level": level,
                    "effect": effect,
                }
            )
        return gaps

    def _grade_and_decision(self, score: int) -> tuple[str, str]:
        grades = nested_get(self.scoring, "grades", default={})
        for grade in ("S", "A", "B", "C", "D"):
            spec = grades.get(grade, {})
            if spec.get("min", 101) <= score <= spec.get("max", -1):
                return grade, str(spec.get("decision"))
        raise ValueError(f"Score {score} is outside configured grade ranges")

    def _matches_and_missing(
        self,
        parsed: ParsedJD,
        combined: str,
        primary_track: str,
    ) -> tuple[list[str], list[str], list[str]]:
        matched: list[str] = []
        missing: list[str] = []
        risks: list[str] = []
        for skill in parsed.required_skills:
            value = self.candidate_levels.get(skill, 0.0)
            if skill == "C++":
                cpp_requirement = self._cpp_requirement(parsed, combined)
                if cpp_requirement == "bonus_only":
                    if value < 0.75:
                        risks.append("C++仅为加分项；候选人证据有限，不构成拒绝或扣分")
                    continue
                if cpp_requirement == "preferred" and value < 0.75:
                    missing.append("C++：岗位优选项，候选人仅有基础证据")
                    continue
            if value >= 0.75:
                matched.append(f"{skill}：简历事实中有充分或熟悉级证据")
            elif value > 0:
                missing.append(f"{skill}：岗位要求较高，候选人仅有基础或有限证据")
            else:
                missing.append(f"{skill}：resume_facts.yaml 中无直接证据")

        if primary_track == "communication_ai" and signal_score(combined, COMM_SIGNALS):
            matched.append("通信/信号处理方向与候选人的无线通信及 CSI 项目证据一致")
        if primary_track == "medical_cv" and signal_score(
            combined, MEDICAL_STRONG_SIGNALS
        ):
            matched.append("医学图像方向与 medical_cv_segmentation_project 和 3D 分割事实直接相关")
        elif primary_track == "medical_cv" and signal_score(combined, CV_SIGNALS):
            matched.append("通用 CV 职责可迁移现有视觉建模能力，但无该行业直接项目事实")
        if primary_track == "general_ai" and signal_score(combined, GENERAL_SIGNALS):
            matched.append("通用 AI 职责可使用现有深度学习训练与实验能力")

        years = self._experience_years(combined)
        if years:
            missing.append(f"岗位提到 {years} 年及以上经验；简历事实中无正式工作或实习经历")
        if any(
            phrase in normalize(combined)
            for phrase in (
                "legally authorized to work",
                "citizens of schengen",
                "u.s. person status is required",
                "visa sponsorship",
                "thai national",
            )
        ):
            risks.append("工作许可或国籍资格未在 resume_facts.yaml 中确认")
        if primary_track == "medical_cv" and any(
            term_present(combined, term)
            for term in self.medical_exploratory_signals
        ):
            risks.append("探索性医学/CV 主题不得当作直接项目经历")
        if max(
            signal_score(combined, COMM_SIGNALS),
            signal_score(combined, MEDICAL_STRONG_SIGNALS)
            + signal_score(combined, CV_SIGNALS),
            signal_score(combined, GENERAL_SIGNALS),
        ) < 1.0:
            risks.append("主线分类置信度低，需人工核对岗位核心职责")
        return stable_unique(matched), stable_unique(missing), stable_unique(risks)

    def match(self, job: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(job, dict):
            raise TypeError("Each JD must be a JSON object")
        title = str(job.get("job_title") or "")
        text = str(job.get("jd_text") or "")
        combined = f"{title}\n{text}"
        parsed = self.parse_jd(job)
        classification = self._track_classification(title, text)
        primary = classification["primary_track"]

        common = self._common_score(parsed, combined)
        tools = self._tool_score(parsed, combined)
        technical_role = self._technical_role_relevance(title, combined)

        track_dimensions: dict[str, dict[str, int]] = {}
        evidence_by_track: dict[str, list[dict[str, str]]] = {}
        transferable_by_track: dict[str, list[str]] = {}
        totals: dict[str, int] = {}
        for track in TRACKS:
            domain = self._domain_score(track, combined)
            project_score, evidence, transferable = self._project_score_and_evidence(
                track, combined
            )
            education_background = self._education_background_score(track, combined)
            dims = {
                "common_technical_core": common,
                "track_domain_match": domain,
                "project_evidence": project_score,
                "education_background_fit": education_background,
                "engineering_tools": tools,
                "technical_role_relevance": technical_role,
            }
            total = max(0, min(100, sum(dims.values())))
            track_dimensions[track] = dims
            evidence_by_track[track] = evidence
            transferable_by_track[track] = transferable
            totals[track] = total

        final_score = totals[primary]
        grade, _ = self._grade_and_decision(final_score)
        soft_gaps = self._soft_gaps(parsed, combined)
        hard_reject = bool(parsed.hard_constraints)
        hard_reject_reason = "; ".join(parsed.hard_constraints) if hard_reject else None
        eligibility = self._eligibility(job, title, combined, parsed)
        preference = self._preference_fit(
            job,
            title,
            combined,
            parsed,
            primary,
            evidence_by_track[primary],
        )
        priority = self._opportunity_priority(
            final_score,
            grade,
            eligibility,
            preference,
            soft_gaps,
            parsed.hard_constraints,
        )
        decision = {
            "P0": "selected",
            "P1": "selected",
            "P2": "review",
            "reject": "rejected",
        }[priority]

        matched, missing, risks = self._matches_and_missing(parsed, combined, primary)
        if soft_gaps:
            risks.append("存在工程软缺口，已按必备/优选层级处理")
        if hard_reject:
            risks.append("岗位内容或安全 hard reject 已覆盖机会优先级")
        risks.extend(eligibility["risks"])
        if eligibility["hard_conflicts"]:
            risks.append("资格硬冲突只影响 eligibility 和机会优先级，未改写技术等级")
        if preference["transfer_only"]:
            risks.append("该岗位按技能迁移评估，未声明候选人拥有对应直接项目经历")
        risks = stable_unique(risks)

        score_keys = {
            "communication_ai": "communication_score",
            "medical_cv": "medical_cv_score",
            "general_ai": "general_ai_score",
        }
        score_output = {score_keys[track]: totals[track] for track in TRACKS}

        if hard_reject:
            gate_reason = hard_reject_reason or "岗位内容或安全 hard reject"
        elif eligibility["status"] == "ineligible":
            gate_reason = "；".join(eligibility["hard_conflicts"])
        elif eligibility["status"] == "uncertain":
            gate_reason = "；".join(eligibility["risks"])
        elif priority == "P2":
            gate_reason = "存在迁移型匹配、核心工程缺口或低公司偏好，需人工复核"
        else:
            gate_reason = "无明显资格冲突，按偏好和技术匹配进入本地候选池"
        final_reason = (
            f"技术匹配 {final_score}（{grade}，{primary}）；"
            f"Eligibility={eligibility['status']}；"
            f"Preference={preference['score']}；"
            f"机会优先级={priority}。{gate_reason}。"
        )

        actions = {
            "selected": "加入本地岗位发现候选池；任何真实投递前必须由用户确认。",
            "review": "人工核验核心缺口、资格和 JD 原文；不得自动投递。",
            "rejected": "离线拒绝，不进入待投候选池。",
        }

        return {
            "job_id": job.get("job_id"),
            "platform": job.get("platform"),
            "platform_job_id": job.get("platform_job_id"),
            "company": job.get("company"),
            "job_title": job.get("job_title"),
            "city": job.get("city"),
            "salary": job.get("salary"),
            "url": job.get("url"),
            "source": job.get("source"),
            "source_label": job.get("source_label"),
            "source_checked_at": job.get("source_checked_at"),
            "track_classification": classification,
            "technical_match": {
                "score": final_score,
                "grade": grade,
                "primary_track": primary,
                **score_output,
                "dimension_scores": track_dimensions[primary],
                "track_dimension_scores": track_dimensions,
            },
            "eligibility": eligibility,
            "preference_fit": preference,
            "opportunity_priority": priority,
            "decision": decision,
            "matched_requirements": matched,
            "missing_requirements": missing,
            "soft_gaps": soft_gaps,
            "hard_constraints": parsed.hard_constraints,
            "hard_reject": hard_reject,
            "hard_reject_reason": hard_reject_reason,
            "transferable_skills": transferable_by_track[primary],
            "project_evidence": evidence_by_track[primary],
            "risk_flags": risks,
            "final_reason": final_reason,
            "recommended_action": actions[decision],
            "parsed_jd": parsed.to_dict(),
        }

    def match_many(self, jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.match(job) for job in jobs]


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="One JSON object or JSON array")
    source.add_argument("--input-dir", type=Path, help="Directory containing JD JSON files")
    parser.add_argument("--output", type=Path, help="Output path for a single input")
    parser.add_argument("--output-dir", type=Path, help="Output directory for batch mode")
    parser.add_argument("--resume", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--scoring", type=Path, default=DEFAULT_SCORING)
    parser.add_argument("--eligibility", type=Path, default=DEFAULT_ELIGIBILITY)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    matcher = JobMatcher(
        args.resume, args.profile, args.scoring, args.eligibility
    )

    if args.input:
        payload = read_json(args.input)
        if isinstance(payload, list):
            result: Any = matcher.match_many(payload)
        elif isinstance(payload, dict):
            result = matcher.match(payload)
        else:
            raise ValueError("Input JSON must be an object or an array of objects")
        if args.output:
            write_json(args.output, result)
        else:
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        return 0

    input_dir: Path = args.input_dir
    files = sorted(input_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {input_dir}")
    output_dir = args.output_dir or (PROJECT_ROOT / "data" / "offline_test_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    all_results: list[dict[str, Any]] = []
    for path in files:
        payload = read_json(path)
        if not isinstance(payload, dict):
            raise ValueError(f"Batch fixture must contain one object: {path}")
        result = matcher.match(payload)
        write_json(output_dir / f"{path.stem}_result.json", result)
        all_results.append(result)
    write_json(output_dir / "all_results.json", all_results)
    print(f"Matched {len(all_results)} JD files into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
