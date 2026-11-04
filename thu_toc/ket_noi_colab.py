"""AI local. Giữ tên hàm cũ để tương thích với views.py."""

import atexit
import hashlib
import io
import json
import logging
import threading
from pathlib import Path

from django.conf import settings


nhat_ky = logging.getLogger(__name__)

khoa_suy_luan = threading.Lock()
bo_ai = None


TEN_DANG_MAT = {
    "Heart": "Mặt trái tim",
    "Oblong": "Mặt dài",
    "Oval": "Mặt trái xoan",
    "Round": "Mặt tròn",
    "Square": "Mặt vuông",
}


FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454,
    323, 361, 288, 397, 365, 379, 378, 400, 377,
    152, 148, 176, 149, 150, 136, 172, 58, 132,
    93, 234, 127, 162, 21, 54, 103, 67, 109,
]


class LoiKetNoiColab(Exception):
    """Giữ tên cũ để views.py tiếp tục bắt lỗi."""


def doc_json(duong_dan):
    with duong_dan.open("r", encoding="utf-8") as tep:
        return json.load(tep)


def sha256(duong_dan):
    h = hashlib.sha256()

    with duong_dan.open("rb") as tep:
        for khoi in iter(
            lambda: tep.read(1024 * 1024),
            b"",
        ):
            h.update(khoi)

    return h.hexdigest()


class BoAILocal:
    def __init__(self):
        self.detector = None

        thu_muc = (
            Path(settings.BASE_DIR)
            / "tai_nguyen"
            / "ai_khuon_mat"
        )

        tep_manifest = thu_muc / "export_manifest.json"

        if not tep_manifest.is_file():
            raise LoiKetNoiColab(
                f"Thiếu bộ AI local tại: {thu_muc}"
            )

        manifest = doc_json(tep_manifest)

        can_co = {
            "model.keras",
            "face_shape_labels.json",
            "face_shape_class_thresholds.json",
            "inference_config.json",
            "calibration_config.json",
            "face_landmarker.task",
            "test_seal.json",
        }

        if not can_co.issubset(manifest.get("files", {})):
            raise LoiKetNoiColab(
                "Bộ AI local thiếu danh sách file cần thiết."
            )

        for ten in can_co:
            tep = thu_muc / ten

            if not tep.is_file():
                raise LoiKetNoiColab(
                    f"Thiếu file AI: {ten}"
                )

            if sha256(tep) != manifest["files"][ten]["sha256"]:
                raise LoiKetNoiColab(
                    f"File AI không khớp bản xuất: {ten}"
                )

        self.nhan = doc_json(
            thu_muc / "face_shape_labels.json"
        )

        self.nguong = doc_json(
            thu_muc / "face_shape_class_thresholds.json"
        )

        config = doc_json(
            thu_muc / "inference_config.json"
        )

        calibration = doc_json(
            thu_muc / "calibration_config.json"
        )

        seal = doc_json(
            thu_muc / "test_seal.json"
        )

        if (
            self.nhan != list(TEN_DANG_MAT)
            or config["class_order"] != self.nhan
        ):
            raise LoiKetNoiColab(
                "Thứ tự nhãn AI không khớp."
            )

        if calibration != seal["calibration"]:
            raise LoiKetNoiColab(
                "Calibration không khớp bản đã chốt."
            )

        if (
            sha256(thu_muc / "model.keras")
            != seal["model_sha256"]
        ):
            raise LoiKetNoiColab(
                "Model không khớp bản đã chốt."
            )

        if (
            sha256(
                thu_muc / "face_shape_class_thresholds.json"
            )
            != seal["threshold_sha256"]
        ):
            raise LoiKetNoiColab(
                "Threshold không khớp bản đã chốt."
            )

        self.img = int(config["image_size"])
        self.tta = bool(calibration["use_tta"])

        if self.tta != bool(config["tta_flip"]):
            raise LoiKetNoiColab(
                "Cấu hình TTA không khớp."
            )

        self.margin = float(config["crop"]["margin"])
        self.mask = bool(config["crop"]["mask"])

        # Chỉ nạp thư viện nặng khi thực sự cần AI.
        import cv2
        import numpy as np
        import tensorflow as tf
        import mediapipe as mp

        from PIL import Image, ImageOps
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        self.cv2 = cv2
        self.np = np
        self.tf = tf
        self.mp = mp
        self.Image = Image
        self.ImageOps = ImageOps

        self.model = tf.keras.models.load_model(
            thu_muc / "model.keras",
            compile=False,
        )

        # Tạo một hàm suy luận cố định, dùng lại cho các lượt quét.
        @tf.function(
            input_signature=[
                tf.TensorSpec(
                    (1, self.img, self.img, 3),
                    tf.float32,
                )
            ],
            reduce_retracing=True,
        )
        def infer(batch):
            probs = tf.cast(
                self.model(batch, training=False),
                tf.float32,
            )

            if self.tta:
                flipped = tf.image.flip_left_right(batch)

                probs_flip = tf.cast(
                    self.model(flipped, training=False),
                    tf.float32,
                )

                probs = (probs + probs_flip) / 2.0

            return probs

        self.infer = infer

        thu = infer(
            tf.zeros(
                (1, self.img, self.img, 3),
                tf.float32,
            )
        ).numpy()

        if (
            thu.shape != (1, len(self.nhan))
            or not np.isfinite(thu).all()
        ):
            raise LoiKetNoiColab(
                "Model trả đầu ra không hợp lệ."
            )

        for ten in self.nhan:
            nguong = float(
                self.nguong[ten]["threshold"]
            )

            # Threshold có thể > 1 để từ chối một class,
            # đúng quy tắc đã lưu từ Colab.
            if not np.isfinite(nguong) or nguong < 0:
                raise LoiKetNoiColab(
                    f"Ngưỡng của {ten} không hợp lệ."
                )

        self.detector = (
            mp_vision.FaceLandmarker.create_from_options(
                mp_vision.FaceLandmarkerOptions(
                    base_options=mp_python.BaseOptions(
                        model_asset_path=str(
                            thu_muc / "face_landmarker.task"
                        )
                    ),
                    running_mode=mp_vision.RunningMode.IMAGE,
                    num_faces=2,
                    min_face_detection_confidence=0.5,
                    min_face_presence_confidence=0.5,
                )
            )
        )

        nhat_ky.info(
            "AI local đã sẵn sàng; đầu vào %s; TTA %s",
            self.img,
            self.tta,
        )

    def crop(self, rgb, pts):
        # Giữ nguyên thuật toán crop/align của Cell 3.
        np = self.np
        cv2 = self.cv2

        h, w = rgb.shape[:2]

        left = pts[33]
        right = pts[263]

        if left[0] > right[0]:
            left, right = right, left

        angle = float(
            np.degrees(
                np.arctan2(
                    right[1] - left[1],
                    right[0] - left[0],
                )
            )
        )

        center = tuple(
            ((left + right) / 2).astype(float)
        )

        matrix = cv2.getRotationMatrix2D(
            center,
            angle,
            1.0,
        )

        rotated = cv2.warpAffine(
            rgb,
            matrix,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

        rotated_pts = (
            matrix
            @ np.column_stack([
                pts,
                np.ones(
                    len(pts),
                    dtype=np.float32,
                ),
            ]).T
        ).T

        oval = rotated_pts[FACE_OVAL]

        x0, y0 = oval.min(axis=0)
        x1, y1 = oval.max(axis=0)

        bw = x1 - x0
        bh = y1 - y0

        if bw < 32 or bh < 32:
            return None

        if self.mask:
            face_mask = np.zeros(
                (h, w),
                dtype=np.uint8,
            )

            hull = cv2.convexHull(
                oval.astype(np.int32)
            )

            cv2.fillPoly(
                face_mask,
                [hull],
                255,
            )

            kernel = max(
                3,
                int(0.03 * bw) // 2 * 2 + 1,
            )

            face_mask = cv2.dilate(
                face_mask,
                np.ones(
                    (kernel, kernel),
                    dtype=np.uint8,
                ),
            )

            rotated = np.where(
                face_mask[..., None] > 0,
                rotated,
                0,
            ).astype(np.uint8)

        X0 = max(
            0,
            int(np.floor(x0 - self.margin * bw)),
        )

        Y0 = max(
            0,
            int(np.floor(y0 - self.margin * bh)),
        )

        X1 = min(
            w,
            int(np.ceil(x1 + self.margin * bw)),
        )

        Y1 = min(
            h,
            int(np.ceil(y1 + self.margin * bh)),
        )

        crop = rotated[Y0:Y1, X0:X1]

        if crop.shape[0] < 32 or crop.shape[1] < 32:
            return None

        return crop

    def predict(self, noi_dung):
        np = self.np
        tf = self.tf
        mp = self.mp
        Image = self.Image
        ImageOps = self.ImageOps

        if (
            not isinstance(noi_dung, (bytes, bytearray))
            or not noi_dung
        ):
            raise LoiKetNoiColab(
                "Chưa nhận được ảnh hợp lệ."
            )

        if len(noi_dung) > 8 * 1024 * 1024:
            raise LoiKetNoiColab(
                "Ảnh vượt quá dung lượng 8 MB."
            )

        with Image.open(io.BytesIO(noi_dung)) as anh:
            if (
                min(anh.size) < 48
                or anh.width * anh.height > 20_000_000
            ):
                raise LoiKetNoiColab(
                    "Kích thước ảnh không hợp lệ."
                )

            source = (
                ImageOps.exif_transpose(anh)
                .convert("RGB")
            )

            source.thumbnail(
                (1600, 1600),
                Image.Resampling.LANCZOS,
            )

            rgb = np.asarray(source).copy()

        result = self.detector.detect(
            mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=np.ascontiguousarray(rgb),
            )
        )

        if len(result.face_landmarks) != 1:
            reason = (
                "Không phát hiện khuôn mặt"
                if not result.face_landmarks
                else "Có nhiều khuôn mặt"
            )

            return phan_hoi(reason=reason)

        h, w = rgb.shape[:2]

        pts = np.array(
            [
                [p.x * w, p.y * h]
                for p in result.face_landmarks[0]
            ],
            dtype=np.float32,
        )

        crop = self.crop(rgb, pts)

        if crop is None:
            return phan_hoi(
                reason=(
                    "Khuôn mặt quá nhỏ hoặc crop không hợp lệ"
                )
            )

        # Giữ nguyên bước thumbnail và JPEG của Cell 17.
        anh_crop = Image.fromarray(crop)

        anh_crop.thumbnail(
            (512, 512),
            Image.Resampling.LANCZOS,
        )

        buffer = io.BytesIO()

        anh_crop.save(
            buffer,
            format="JPEG",
            quality=95,
        )

        tensor = tf.io.decode_jpeg(
            buffer.getvalue(),
            channels=3,
        )

        tensor = tf.image.resize_with_pad(
            tensor,
            self.img,
            self.img,
            method="bilinear",
        )

        # Model nhận RGB float32 trong khoảng 0–255.
        # Không chia cho 255.
        tensor = tf.cast(
            tf.cast(
                tf.clip_by_value(
                    tf.round(tensor),
                    0,
                    255,
                ),
                tf.uint8,
            ),
            tf.float32,
        )

        tensor = tf.ensure_shape(
            tensor,
            (self.img, self.img, 3),
        )[None, ...]

        probabilities = (
            self.infer(tensor).numpy()[0]
        )

        if not np.isfinite(probabilities).all():
            raise LoiKetNoiColab(
                "AI trả xác suất không hợp lệ."
            )

        index = int(np.argmax(probabilities))

        ten = self.nhan[index]
        confidence = float(probabilities[index])

        threshold = float(
            self.nguong[ten]["threshold"]
        )

        return phan_hoi(
            predicted=ten,
            confidence=confidence,
            threshold=threshold,
            accepted=confidence >= threshold,
            probabilities={
                ten_nhan: float(probabilities[i])
                for i, ten_nhan in enumerate(self.nhan)
            },
        )

    def close(self):
        if self.detector is not None:
            self.detector.close()
            self.detector = None


def phan_hoi(
    predicted=None,
    confidence=None,
    threshold=None,
    accepted=False,
    probabilities=None,
    reason="",
):
    # Giữ nguyên cấu trúc phản hồi mà web hiện tại đang dùng.
    return {
        "thanh_cong": True,
        "chap_nhan": bool(accepted),

        "dang_mat": (
            predicted if accepted else None
        ),

        "dang_mat_du_doan": predicted,

        "ten_dang_mat": (
            TEN_DANG_MAT.get(predicted)
        ),

        "nhan_hien_thi": (
            TEN_DANG_MAT.get(
                predicted,
                "Không chắc chắn",
            )
            if accepted
            else "Không chắc chắn"
        ),

        "do_tin_cay": confidence,
        "nguong_chap_nhan": threshold,
        "xac_suat": probabilities or {},
        "thong_bao": reason,
    }


def lay_bo_ai():
    # Luôn gọi hàm này bên trong khóa suy luận.
    global bo_ai

    if bo_ai is None:
        bo_ai = BoAILocal()

    return bo_ai


def kiem_tra_colab():
    """Kiểm tra AI local; không gọi Colab hay ngrok."""

    if not khoa_suy_luan.acquire(blocking=False):
        if bo_ai is not None:
            return {
                "thanh_cong": True,
                "san_sang": True,
                "thong_bao": (
                    "AI local đang xử lý ảnh."
                ),
            }

        raise LoiKetNoiColab(
            "AI local đang khởi tạo. "
            "Vui lòng chờ rồi thử lại."
        )

    try:
        lay_bo_ai()

        return {
            "thanh_cong": True,
            "san_sang": True,
            "thong_bao": (
                "AI trên máy đã sẵn sàng, không cần Colab."
            ),
        }

    except LoiKetNoiColab:
        raise

    except Exception as loi:
        nhat_ky.exception(
            "Không khởi tạo được AI local"
        )

        raise LoiKetNoiColab(
            "Không nạp được AI local. "
            "Xem lỗi trong Terminal Django."
        ) from loi

    finally:
        khoa_suy_luan.release()


def phan_tich_anh_colab(noi_dung_anh):
    """Giữ tên hàm cũ, dự đoán hoàn toàn trên máy."""

    if not khoa_suy_luan.acquire(blocking=False):
        raise LoiKetNoiColab(
            "AI đang xử lý ảnh khác. "
            "Vui lòng thử lại sau."
        )

    try:
        return lay_bo_ai().predict(noi_dung_anh)

    except LoiKetNoiColab:
        raise

    except Exception as loi:
        nhat_ky.exception(
            "Lỗi phân tích khuôn mặt bằng AI local"
        )

        raise LoiKetNoiColab(
            "Không phân tích được ảnh trên máy. "
            "Xem lỗi trong Terminal Django."
        ) from loi

    finally:
        khoa_suy_luan.release()


@atexit.register
def dong_bo_ai():
    with khoa_suy_luan:
        if bo_ai is not None:
            bo_ai.close()