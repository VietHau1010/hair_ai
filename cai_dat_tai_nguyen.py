from pathlib import Path
import os
import urllib.request

THU_MUC_GOC = Path(__file__).resolve().parent

if not (THU_MUC_GOC / "manage.py").is_file():
    raise SystemExit(
        "Đặt tệp cai_dat_tai_nguyen.py cùng thư mục với manage.py."
    )

THU_MUC_TAI_NGUYEN = (
    THU_MUC_GOC
    / "tai_nguyen"
    / "thu_toc"
    / "mediapipe"
)

PHIEN_BAN = "0.10.21"


def tai_tep(danh_sach_dia_chi, duong_dan):
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    tep_tam = duong_dan.with_name(duong_dan.name + ".part")
    loi_cuoi = None

    for dia_chi in danh_sach_dia_chi:
        try:
            yeu_cau = urllib.request.Request(
                dia_chi,
                headers={"User-Agent": "HAULONGHAIR/1.0"},
            )

            with urllib.request.urlopen(
                yeu_cau,
                timeout=120,
            ) as nguon:
                with tep_tam.open("wb") as tep:
                    while True:
                        khoi = nguon.read(1024 * 1024)

                        if not khoi:
                            break

                        tep.write(khoi)

            if tep_tam.stat().st_size < 100:
                raise RuntimeError("Tệp tải về chưa đầy đủ.")

            os.replace(tep_tam, duong_dan)

            print(
                "Đã tải:",
                duong_dan.relative_to(THU_MUC_GOC),
            )
            return

        except Exception as loi:
            loi_cuoi = loi
            tep_tam.unlink(missing_ok=True)

    raise RuntimeError(
        f"Không tải được {duong_dan.name}: {loi_cuoi}"
    )


CAC_TEP = [
    "vision_bundle.mjs",
    "wasm/vision_wasm_internal.js",
    "wasm/vision_wasm_internal.wasm",
    "wasm/vision_wasm_nosimd_internal.js",
    "wasm/vision_wasm_nosimd_internal.wasm",
]

for ten_tep in CAC_TEP:
    tai_tep(
        [
            (
                "https://cdn.jsdelivr.net/npm/"
                f"@mediapipe/tasks-vision@{PHIEN_BAN}/{ten_tep}"
            ),
            (
                "https://unpkg.com/"
                f"@mediapipe/tasks-vision@{PHIEN_BAN}/{ten_tep}"
            ),
        ],
        THU_MUC_TAI_NGUYEN / ten_tep,
    )

tai_tep(
    [
        (
            "https://storage.googleapis.com/mediapipe-models/"
            "face_landmarker/face_landmarker/"
            "float16/1/face_landmarker.task"
        ),
    ],
    THU_MUC_TAI_NGUYEN / "face_landmarker.task",
)

print("\nHOÀN TẤT: Đã tải bộ theo dõi khuôn mặt.")