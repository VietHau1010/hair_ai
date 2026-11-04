import argparse
import io
import json
import math
import uuid
import warnings

from pathlib import Path
from urllib.request import urlopen

import cv2
import mediapipe as mp
import numpy as np

from PIL import Image, ImageOps, UnidentifiedImageError
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


PHIEN_BAN = "tach_toc_khoi_chinh_bo_mai_thua_20261019_04"

THU_MUC_GOC = Path(__file__).resolve().parent.parent

THU_MUC_MO_HINH = (
    THU_MUC_GOC / "tai_nguyen" / "tach_toc"
)

MO_HINH_TOC = THU_MUC_MO_HINH / "phan_tich_toc.onnx"

MO_HINH_MAT = (
    THU_MUC_GOC
    / "tai_nguyen"
    / "thu_toc"
    / "mediapipe"
    / "face_landmarker.task"
)

DIA_CHI_MO_HINH = (
    "https://github.com/yakhyo/face-parsing/"
    "releases/download/weights/resnet18.onnx"
)

GIOI_HAN_DUNG_LUONG = 8 * 1024 * 1024
GIOI_HAN_DIEM_ANH = 20_000_000

CANH_XU_LY_TOI_DA = 2560
CANH_NHAN_DIEN_MAT = 1280
CANH_MATTING_TOI_DA = 900

CO_MAT_TOI_THIEU = 48

SO_LOP = 19
LOP_TOC = 17

CAC_LOP_LONG_MAY = (2, 3)

CAC_LOP_CO_THE = (
    1,
    2, 3,
    4, 5,
    6,
    7, 8,
    9,
    10,
    11,
    12, 13,
    14,
    15,
    16,
)

# Chế độ dành cho tóc nam ngắn:
# bỏ phần mai dài, mỏng và thưa ở hai bên.
CAT_MAI_CAN_DOI = True

# Khoảng giữ mai dưới đường mắt.
# 0.06 ngắn hơn bản trước là 0.12.
DO_DAI_MAI = 0.06


class LoiTachToc(Exception):
    pass


def _doc_mang_mo_hinh(duong_dan):
    return np.frombuffer(
        duong_dan.read_bytes(),
        dtype=np.uint8,
    )


def tai_mo_hinh():
    if MO_HINH_TOC.is_file():
        return MO_HINH_TOC

    THU_MUC_MO_HINH.mkdir(
        parents=True,
        exist_ok=True,
    )

    tep_tam = (
        THU_MUC_MO_HINH
        / f"{uuid.uuid4().hex}.tam"
    )

    try:
        tong = 0

        with urlopen(
            DIA_CHI_MO_HINH,
            timeout=120,
        ) as phan_hoi:
            with tep_tam.open("xb") as tep:
                while True:
                    khoi = phan_hoi.read(1024 * 1024)

                    if not khoi:
                        break

                    tong += len(khoi)

                    if tong > 120 * 1024 * 1024:
                        raise LoiTachToc(
                            "Tệp mô hình tải về lớn bất thường."
                        )

                    tep.write(khoi)

        if tong < 1024 * 1024:
            raise LoiTachToc(
                "Mô hình tải về không đầy đủ."
            )

        bo_thu = cv2.dnn.readNetFromONNX(
            _doc_mang_mo_hinh(tep_tam)
        )

        if bo_thu.empty():
            raise LoiTachToc(
                "Mô hình ONNX không hợp lệ."
            )

        del bo_thu
        tep_tam.replace(MO_HINH_TOC)

    except LoiTachToc:
        raise

    except Exception as loi:
        raise LoiTachToc(
            f"Không tải được mô hình: {loi}"
        ) from loi

    finally:
        tep_tam.unlink(missing_ok=True)

    return MO_HINH_TOC


def doc_anh(noi_dung):
    if not isinstance(noi_dung, bytes) or not noi_dung:
        raise LoiTachToc(
            "Dữ liệu ảnh trống hoặc không hợp lệ."
        )

    if len(noi_dung) > GIOI_HAN_DUNG_LUONG:
        raise LoiTachToc("Ảnh vượt quá 8 MB.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(io.BytesIO(noi_dung)) as anh:
                if anh.format not in {"JPEG", "PNG", "WEBP"}:
                    raise LoiTachToc(
                        "Chỉ nhận JPEG, PNG hoặc WEBP."
                    )

                if getattr(anh, "is_animated", False):
                    raise LoiTachToc("Chỉ nhận ảnh tĩnh.")

                if min(anh.size) < 128:
                    raise LoiTachToc(
                        "Mỗi chiều ảnh phải từ 128 pixel."
                    )

                if anh.width * anh.height > GIOI_HAN_DIEM_ANH:
                    raise LoiTachToc(
                        "Ảnh vượt quá 20 triệu điểm ảnh."
                    )

                anh.verify()

            with Image.open(io.BytesIO(noi_dung)) as anh:
                anh = ImageOps.exif_transpose(anh)

                anh.thumbnail(
                    (CANH_XU_LY_TOI_DA,) * 2,
                    Image.Resampling.LANCZOS,
                )

                anh = anh.convert("RGBA")

                nen = Image.new(
                    "RGBA",
                    anh.size,
                    (240, 240, 240, 255),
                )

                anh = Image.alpha_composite(
                    nen,
                    anh,
                ).convert("RGB")

                return np.array(
                    anh,
                    dtype=np.uint8,
                    copy=True,
                    order="C",
                )

    except LoiTachToc:
        raise

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as loi:
        raise LoiTachToc(
            "Không đọc được ảnh hợp lệ."
        ) from loi


def _cat_dau(rgb, diem):
    cao, rong = rgb.shape[:2]

    rong_mat = float(
        np.linalg.norm(diem[454] - diem[234])
    )

    cao_mat = float(
        np.linalg.norm(diem[152] - diem[10])
    )

    if min(rong_mat, cao_mat) < CO_MAT_TOI_THIEU:
        raise LoiTachToc(
            f"Kích thước khuôn mặt: "
            f"{rong_mat:.0f} × {cao_mat:.0f} pixel. "
            f"Tối thiểu {CO_MAT_TOI_THIEU} pixel."
        )

    neo_x, neo_y = diem[10]

    trai = max(
        0,
        math.floor(neo_x - 1.35 * rong_mat),
    )

    phai = min(
        rong,
        math.ceil(neo_x + 1.35 * rong_mat),
    )

    tren = max(
        0,
        math.floor(neo_y - 1.05 * cao_mat),
    )

    duoi = min(
        cao,
        math.ceil(diem[152, 1] + 0.45 * cao_mat),
    )

    if phai <= trai or duoi <= tren:
        raise LoiTachToc(
            "Không xác định được vùng đầu."
        )

    anh_cat = np.ascontiguousarray(
        rgb[tren:duoi, trai:phai]
    )

    diem_cat = diem - np.array(
        [trai, tren],
        dtype=np.float32,
    )

    return anh_cat, diem_cat, rong_mat


def _giu_cum_toc(mask, diem, rong_mat):
    so_vung, nhan, thong_ke, _ = (
        cv2.connectedComponentsWithStats(
            mask.astype(np.uint8),
            connectivity=8,
        )
    )

    if so_vung <= 1:
        raise LoiTachToc(
            "Không tìm thấy tóc rõ trong ảnh."
        )

    yy, xx = np.ogrid[
        :mask.shape[0],
        :mask.shape[1],
    ]

    neo_x, neo_y = diem[10]

    gan_dau = (
        (np.abs(xx - neo_x) < rong_mat * 1.1)
        & (yy < neo_y + rong_mat * 0.65)
    )

    diem_so = np.bincount(
        nhan[gan_dau].ravel(),
        minlength=so_vung,
    )

    diem_so[0] = 0
    chinh = int(np.argmax(diem_so))

    if (
        chinh == 0
        or thong_ke[chinh, cv2.CC_STAT_AREA] < 50
    ):
        raise LoiTachToc(
            "Vùng tóc quá nhỏ hoặc không gắn với đầu."
        )

    giu = nhan == chinh

    khoang_cach = cv2.distanceTransform(
        (~giu).astype(np.uint8),
        cv2.DIST_L2,
        5,
    )

    for ma in range(1, so_vung):
        if ma == chinh:
            continue

        if thong_ke[ma, cv2.CC_STAT_AREA] < 3:
            continue

        vung = nhan == ma

        if (
            np.any(vung & gan_dau)
            and float(khoang_cach[vung].min())
            < max(2, rong_mat * 0.08)
        ):
            giu |= vung

    # Không lấp các khe da nằm trong tóc.
    return giu


def _loc_bien(rgb, alpha, ban_kinh=1):
    anh_xam = cv2.cvtColor(
        rgb.astype(np.float32) / 255.0,
        cv2.COLOR_RGB2GRAY,
    )

    alpha = alpha.astype(np.float32)
    canh = 2 * ban_kinh + 1

    def tb(x):
        return cv2.boxFilter(
            x,
            -1,
            (canh, canh),
            borderType=cv2.BORDER_REFLECT,
        )

    mi = tb(anh_xam)
    ma = tb(alpha)

    var = np.maximum(
        tb(anh_xam * anh_xam) - mi * mi,
        0,
    )

    cov = tb(anh_xam * alpha) - mi * ma

    a = cov / (var + 1e-4)
    b = ma - a * mi

    return np.clip(
        tb(a) * anh_xam + tb(b),
        0,
        1,
    )


def _co_mask(mask, ban_kinh):
    canh = 2 * ban_kinh + 1

    return cv2.erode(
        mask.astype(np.uint8),
        np.ones((canh, canh), dtype=np.uint8),
        borderType=cv2.BORDER_CONSTANT,
        borderValue=0,
    ).astype(bool)


def _tao_trimap(rgb, du_lieu, diem, rong_mat):
    p_toc = du_lieu["toc"]
    p_da = du_lieu["da"]
    p_co_the = du_lieu["co_the"]
    p_khac = du_lieu["khac"]
    nhan = du_lieu["nhan"]

    giu = _giu_cum_toc(
        (nhan == LOP_TOC) & (p_toc >= 0.30),
        diem,
        rong_mat,
    )

    if any((
        np.any(giu[0]),
        np.any(giu[-1]),
        np.any(giu[:, 0]),
        np.any(giu[:, -1]),
    )):
        raise LoiTachToc(
            "Tóc chạm mép ảnh hoặc vùng xử lý. "
            "Hãy dùng ảnh có khoảng trống quanh tóc."
        )

    ngoai = cv2.distanceTransform(
        (~giu).astype(np.uint8),
        cv2.DIST_L2,
        5,
    )

    bien = float(
        np.clip(rong_mat * 0.015, 2, 7)
    )

    ho_tro = ngoai <= bien

    da_chac = (
        (p_da >= 0.65)
        & (p_da > p_toc + 0.20)
    )

    co_the_chac = (
        (p_co_the >= 0.75)
        & (p_co_the > p_toc + 0.25)
    )

    long_may = np.isin(
        nhan,
        CAC_LOP_LONG_MAY,
    )

    nen_chac = (
        (~ho_tro)
        | ((p_toc < 0.04) & (p_khac >= 0.85))
        | da_chac
        | co_the_chac
        | long_may
    )

    toc_chac = _co_mask(
        giu
        & (p_toc >= 0.90)
        & (p_toc > p_khac + 0.40)
        & (~nen_chac),
        1,
    )

    if np.count_nonzero(toc_chac) < 12:
        toc_chac = _co_mask(
            giu
            & (p_toc >= 0.72)
            & (p_toc > p_khac + 0.25)
            & (~nen_chac),
            1,
        )

    if np.count_nonzero(toc_chac) < 6:
        raise LoiTachToc(
            "Không có vùng tóc đủ chắc chắn. "
            "Hãy chọn ảnh rõ tóc hơn."
        )

    return {
        "toc_chac": toc_chac,
        "nen_chac": nen_chac,
        "ho_tro": ho_tro,
        "giu": giu,
        "long_may": long_may,
    }


def _matting(rgb, du_lieu, diem, rong_mat):
    try:
        from pymatting import estimate_alpha_cf

    except ImportError as loi:
        raise LoiTachToc(
            "Thiếu pymatting. Chạy: "
            ".\\.venv\\Scripts\\python.exe "
            "-m pip install pymatting"
        ) from loi

    vung = _tao_trimap(
        rgb,
        du_lieu,
        diem,
        rong_mat,
    )

    cao, rong = rgb.shape[:2]

    ti_le = min(
        1.0,
        CANH_MATTING_TOI_DA / max(cao, rong),
    )

    kich_thuoc = (
        max(1, round(rong * ti_le)),
        max(1, round(cao * ti_le)),
    )

    anh_nho = cv2.resize(
        rgb,
        kich_thuoc,
        interpolation=cv2.INTER_AREA,
    ).astype(np.float64) / 255.0

    if ti_le < 1:
        fg = cv2.resize(
            vung["toc_chac"].astype(np.float32),
            kich_thuoc,
            interpolation=cv2.INTER_AREA,
        ) >= 0.95

        bg = cv2.resize(
            vung["nen_chac"].astype(np.float32),
            kich_thuoc,
            interpolation=cv2.INTER_AREA,
        ) >= 0.75

    else:
        fg = vung["toc_chac"].copy()
        bg = vung["nen_chac"].copy()

    fg &= ~bg

    if not np.any(fg) or not np.any(bg):
        raise LoiTachToc(
            "Không tạo được vùng tóc và nền chắc chắn."
        )

    trimap = np.full(
        anh_nho.shape[:2],
        0.5,
        dtype=np.float64,
    )

    trimap[bg] = 0
    trimap[fg] = 1

    try:
        alpha_nho = estimate_alpha_cf(
            np.ascontiguousarray(anh_nho),
            np.ascontiguousarray(trimap),
        )

        if not np.isfinite(alpha_nho).all():
            raise ValueError("Alpha không hợp lệ.")

    except Exception as loi:
        raise LoiTachToc(
            f"Không giải được alpha matting: {loi}"
        ) from loi

    alpha = cv2.resize(
        np.clip(alpha_nho, 0, 1).astype(np.float32),
        (rong, cao),
        interpolation=cv2.INTER_LINEAR,
    )

    alpha = _loc_bien(
        rgb,
        alpha,
        ban_kinh=1,
    )

    alpha[vung["nen_chac"]] = 0
    alpha[vung["toc_chac"]] = 1
    alpha[~vung["ho_tro"]] = 0
    alpha[vung["long_may"]] = 0

    khoang_ngoai = cv2.distanceTransform(
        (~vung["giu"]).astype(np.uint8),
        cv2.DIST_L2,
        5,
    )

    be_rong = float(
        np.clip(rong_mat * 0.006, 0.8, 1.8)
    )

    suy_giam = np.clip(
        1.0
        - np.maximum(
            khoang_ngoai - be_rong,
            0,
        ) / be_rong,
        0,
        1,
    )

    alpha *= suy_giam

    so_vung, nhan_alpha = cv2.connectedComponents(
        (alpha > 0.008).astype(np.uint8),
        connectivity=8,
    )

    if so_vung <= 1:
        raise LoiTachToc(
            "Không tạo được vùng tóc sau xử lý biên."
        )

    cac_nhan = np.unique(
        nhan_alpha[
            vung["giu"] & (alpha > 0.008)
        ]
    )

    cac_nhan = cac_nhan[cac_nhan != 0]

    alpha[~np.isin(nhan_alpha, cac_nhan)] = 0
    alpha[alpha < 0.008] = 0

    # Không làm mờ hoặc tái tạo RGB của tóc.
    return rgb.copy(), np.clip(alpha, 0, 1)


def _bo_mai_mong(alpha, du_lieu, diem, rong_mat):
    """
    Chỉ lọc phần mai hai bên:
    - Rút ngắn theo cùng cao độ mặt.
    - Bỏ phần mai thưa, bán trong suốt và lẫn da.
    - Bỏ nhánh mai quá mỏng.
    - Giữ phần mái giữa và khối tóc phía trên.
    """

    if not CAT_MAI_CAN_DOI:
        return alpha

    cao, rong = alpha.shape

    cao_mat = float(
        np.linalg.norm(diem[152] - diem[10])
    )

    mat_trai = diem[33].astype(np.float32)
    mat_phai = diem[263].astype(np.float32)

    if mat_trai[0] > mat_phai[0]:
        mat_trai, mat_phai = mat_phai, mat_trai

    truc = mat_phai - mat_trai
    do_dai = float(np.linalg.norm(truc))

    if do_dai < 1 or cao_mat < 1:
        return alpha

    ux, uy = truc / do_dai
    tam = (mat_trai + mat_phai) / 2

    yy, xx = np.ogrid[:cao, :rong]

    dx = xx.astype(np.float32) - float(tam[0])
    dy = yy.astype(np.float32) - float(tam[1])

    ngang = dx * ux + dy * uy
    doc = -dx * uy + dy * ux

    # Chỉ vùng bên ngoài hai thái dương.
    trong_so_ben = np.clip(
        (np.abs(ngang) - rong_mat * 0.32)
        / max(2.0, rong_mat * 0.035),
        0,
        1,
    )

    # Chuyển tiếp từ vùng tóc chính sang vùng mai.
    # Không lọc nhánh mỏng trên đỉnh tóc.
    trong_so_duoi = np.clip(
        (doc + cao_mat * 0.12)
        / max(2.0, cao_mat * 0.08),
        0,
        1,
    )

    trong_so_mai = (
        trong_so_ben * trong_so_duoi
    ).astype(np.float32)

    ket_qua = alpha.astype(np.float32).copy()

    # 1. Rút ngắn mai theo cùng mức hai bên.
    mem = float(
        np.clip(rong_mat * 0.006, 0.8, 1.8)
    )

    muc_cat = cao_mat * DO_DAI_MAI

    giu_doc = np.clip(
        (muc_cat + mem - doc) / (2 * mem),
        0,
        1,
    )

    giu_doc = giu_doc * giu_doc * (3 - 2 * giu_doc)

    ket_qua *= (
        1 - trong_so_ben
        + trong_so_ben * giu_doc
    ).astype(np.float32)

    # 2. Loại tóc thưa lẫn da trong vùng mai.
    p_toc = du_lieu["toc"]
    p_da = du_lieu["da"]
    p_co_the = du_lieu["co_the"]

    tin_cay_toc = np.clip(
        (p_toc - 0.45) / 0.35,
        0,
        1,
    )

    khong_lan_da = np.clip(
        (p_toc - p_da + 0.05) / 0.40,
        0,
        1,
    )

    khong_lan_co_the = np.clip(
        (p_toc - p_co_the + 0.05) / 0.40,
        0,
        1,
    )

    giu_mau_mai = np.minimum(
        tin_cay_toc,
        np.minimum(
            khong_lan_da,
            khong_lan_co_the,
        ),
    )

    ket_qua *= (
        1 - trong_so_mai
        + trong_so_mai * giu_mau_mai
    )

    # 3. Tách bỏ những nhánh mai quá mỏng.
    # Opening chỉ dùng làm mặt nạ giới hạn ở vùng mai,
    # không áp lên khối tóc và không lấp khe da.
    ban_kinh = int(
        np.clip(
            round(rong_mat * 0.018),
            2,
            6,
        )
    )

    hat = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (
            2 * ban_kinh + 1,
            2 * ban_kinh + 1,
        ),
    )

    khoi_day = cv2.morphologyEx(
        (alpha >= 0.55).astype(np.uint8),
        cv2.MORPH_OPEN,
        hat,
        borderType=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    if np.any(khoi_day):
        cach_khoi_day = cv2.distanceTransform(
            (khoi_day == 0).astype(np.uint8),
            cv2.DIST_L2,
            5,
        )

        # Chỉ giữ mép mềm rất hẹp quanh vùng mai đủ dày.
        giu_day = np.clip(
            1 - cach_khoi_day / max(1.0, mem),
            0,
            1,
        )

        ket_qua *= (
            1 - trong_so_mai
            + trong_so_mai * giu_day
        )

    # 4. Không giữ lớp mai mờ, nhưng để một khoảng
    # chuyển tiếp nhỏ tránh cắt viền kiểu răng cưa.
    mai_gon = np.clip(
        (ket_qua - 0.20) / 0.65,
        0,
        1,
    )

    mai_gon = (
        mai_gon * mai_gon
        * (3 - 2 * mai_gon)
    )

    ket_qua = (
        ket_qua * (1 - trong_so_mai)
        + mai_gon * trong_so_mai
    )

    ket_qua[ket_qua < 0.008] = 0

    return np.clip(ket_qua, 0, 1)


def _xuat_png(rgb, alpha, diem, rong_mat):
    yy, xx = np.where(alpha > 0.008)

    if xx.size < 50:
        raise LoiTachToc(
            "Không tạo được ảnh tóc đủ rõ."
        )

    cao, rong = alpha.shape
    neo_x, neo_y = map(float, diem[10])

    if not (
        0 <= neo_x < rong
        and 0 <= neo_y < cao
    ):
        raise LoiTachToc(
            "Điểm neo nằm ngoài vùng xử lý."
        )

    dem = max(3, round(rong_mat * 0.03))

    trai = max(
        0,
        math.floor(
            min(float(xx.min()), neo_x) - dem
        ),
    )

    tren = max(
        0,
        math.floor(
            min(float(yy.min()), neo_y) - dem
        ),
    )

    phai = min(
        rong,
        math.ceil(
            max(
                float(xx.max()) + 1,
                neo_x + 1,
            ) + dem
        ),
    )

    duoi = min(
        cao,
        math.ceil(
            max(
                float(yy.max()) + 1,
                neo_y + 1,
            ) + dem
        ),
    )

    rgba = np.dstack([
        rgb,
        np.rint(alpha * 255).astype(np.uint8),
    ])[tren:duoi, trai:phai].copy()

    rgba[rgba[:, :, 3] == 0, :3] = 0

    chieu_cao, chieu_rong = rgba.shape[:2]
    ti_le = chieu_rong / rong_mat

    if not 0.1 <= ti_le <= 5:
        raise LoiTachToc(
            "Tỷ lệ tóc ngoài giới hạn ghép."
        )

    tep = io.BytesIO()

    Image.fromarray(rgba).save(
        tep,
        format="PNG",
        optimize=True,
    )

    noi_dung = tep.getvalue()

    if len(noi_dung) > GIOI_HAN_DUNG_LUONG:
        raise LoiTachToc(
            "PNG kết quả vượt quá 8 MB."
        )

    return {
        "anh_png": noi_dung,
        "thong_so": {
            "diem_neo_x": round(
                (neo_x - trai) / chieu_rong,
                6,
            ),
            "diem_neo_y": round(
                (neo_y - tren) / chieu_cao,
                6,
            ),
            "ti_le_chieu_rong": round(ti_le, 6),
            "do_lech_x": 0,
            "do_lech_y": 0,
            "chieu_rong": chieu_rong,
            "chieu_cao": chieu_cao,
        },
    }


class BoTachToc:
    def __init__(self):
        self.bo_mat = None
        self.bo_toc = None

        print(
            f"[TÁCH TÓC] {PHIEN_BAN}",
            flush=True,
        )

        if not MO_HINH_MAT.is_file():
            raise LoiTachToc(
                f"Thiếu mô hình khuôn mặt: {MO_HINH_MAT}"
            )

        tai_mo_hinh()

        try:
            self.bo_toc = cv2.dnn.readNetFromONNX(
                _doc_mang_mo_hinh(MO_HINH_TOC)
            )

            if self.bo_toc.empty():
                raise LoiTachToc(
                    "Mô hình ONNX không sử dụng được."
                )

            self.bo_toc.setPreferableBackend(
                cv2.dnn.DNN_BACKEND_OPENCV
            )

            self.bo_toc.setPreferableTarget(
                cv2.dnn.DNN_TARGET_CPU
            )

            self.bo_mat = (
                vision.FaceLandmarker.create_from_options(
                    vision.FaceLandmarkerOptions(
                        base_options=python.BaseOptions(
                            model_asset_buffer=(
                                MO_HINH_MAT.read_bytes()
                            ),
                        ),
                        running_mode=vision.RunningMode.IMAGE,
                        num_faces=2,
                        min_face_detection_confidence=0.6,
                        min_face_presence_confidence=0.6,
                    )
                )
            )

        except Exception as loi:
            self.close()

            raise LoiTachToc(
                f"Không khởi tạo được bộ tách tóc: {loi}"
            ) from loi

    def close(self):
        self.bo_toc = None

        if self.bo_mat is not None:
            bo = self.bo_mat
            self.bo_mat = None
            bo.close()

    def __enter__(self):
        return self

    def __exit__(self, loai_loi, loi, vet):
        self.close()

    def _phan_tich(self, rgb):
        anh = cv2.resize(
            rgb,
            (512, 512),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.float32) / 255.0

        mean = np.array(
            [0.485, 0.456, 0.406],
            dtype=np.float32,
        )

        std = np.array(
            [0.229, 0.224, 0.225],
            dtype=np.float32,
        )

        anh = (anh - mean) / std

        blob = np.ascontiguousarray(
            anh.transpose(2, 0, 1)[None]
        )

        self.bo_toc.setInput(blob)
        dau_ra = self.bo_toc.forward()

        if (
            dau_ra.ndim != 4
            or dau_ra.shape[:2] != (1, SO_LOP)
            or not np.isfinite(dau_ra).all()
        ):
            raise LoiTachToc(
                "Đầu ra không đúng mô hình "
                "phân tích mặt 19 lớp."
            )

        logits = dau_ra[0]

        nhan = logits.argmax(
            axis=0
        ).astype(np.uint8)

        exp = np.exp(
            logits
            - logits.max(
                axis=0,
                keepdims=True,
            )
        )

        prob = exp / np.maximum(
            exp.sum(axis=0, keepdims=True),
            1e-8,
        )

        cao, rong = rgb.shape[:2]

        def phong(x):
            return cv2.resize(
                x.astype(np.float32),
                (rong, cao),
                interpolation=cv2.INTER_LINEAR,
            )

        p_khac = np.max(
            np.concatenate([
                prob[:LOP_TOC],
                prob[LOP_TOC + 1:],
            ], axis=0),
            axis=0,
        )

        return {
            "toc": phong(prob[LOP_TOC]),
            "da": phong(prob[1]),
            "co_the": phong(
                prob[list(CAC_LOP_CO_THE)].max(axis=0)
            ),
            "khac": phong(p_khac),
            "nhan": cv2.resize(
                nhan,
                (rong, cao),
                interpolation=cv2.INTER_NEAREST,
            ),
        }

    def tach(self, noi_dung):
        if self.bo_mat is None or self.bo_toc is None:
            raise LoiTachToc(
                "Bộ tách tóc đã đóng."
            )

        rgb = doc_anh(noi_dung)
        cao, rong = rgb.shape[:2]

        ti_le = min(
            1.0,
            CANH_NHAN_DIEN_MAT / max(cao, rong),
        )

        anh_nho = cv2.resize(
            rgb,
            (
                max(1, round(rong * ti_le)),
                max(1, round(cao * ti_le)),
            ),
            interpolation=cv2.INTER_AREA,
        )

        try:
            cac_mat = self.bo_mat.detect(
                mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=np.ascontiguousarray(anh_nho),
                )
            ).face_landmarks

            if not cac_mat:
                raise LoiTachToc(
                    "Không nhận diện được khuôn mặt. "
                    "Hãy dùng ảnh rõ mặt và đủ sáng."
                )

            if len(cac_mat) != 1:
                raise LoiTachToc(
                    "Ảnh có nhiều khuôn mặt. "
                    "Chỉ dùng ảnh một người."
                )

            diem = np.array(
                [
                    (p.x * rong, p.y * cao)
                    for p in cac_mat[0]
                ],
                dtype=np.float32,
            )

            if (
                diem.ndim != 2
                or diem.shape[0] < 455
                or diem.shape[1] != 2
                or not np.isfinite(diem).all()
            ):
                raise LoiTachToc(
                    "Điểm khuôn mặt không hợp lệ."
                )

            rgb, diem, rong_mat = _cat_dau(
                rgb,
                diem,
            )

            du_lieu = self._phan_tich(rgb)

            rgb_toc, alpha = _matting(
                rgb,
                du_lieu,
                diem,
                rong_mat,
            )

            alpha = _bo_mai_mong(
                alpha,
                du_lieu,
                diem,
                rong_mat,
            )

            return _xuat_png(
                rgb_toc,
                alpha,
                diem,
                rong_mat,
            )

        except LoiTachToc:
            raise

        except Exception as loi:
            raise LoiTachToc(
                f"[{PHIEN_BAN}] "
                f"Không xử lý được ảnh tóc: {loi}"
            ) from loi


def chay_thu():
    lenh = argparse.ArgumentParser(
        description=(
            "Tách khối tóc chính, bỏ mai mỏng "
            "và xuất PNG trong suốt."
        ),
    )

    lenh.add_argument(
        "--kiem-tra",
        action="store_true",
    )

    lenh.add_argument(
        "--tai-mo-hinh",
        action="store_true",
    )

    lenh.add_argument("--anh", type=Path)
    lenh.add_argument("--xuat", type=Path)

    tham_so = lenh.parse_args()

    try:
        if tham_so.kiem_tra:
            try:
                import pymatting
                co_matting = True
            except ImportError:
                co_matting = False

            print(json.dumps(
                {
                    "phien_ban": PHIEN_BAN,
                    "file": str(Path(__file__).resolve()),
                    "nguong_mat": CO_MAT_TOI_THIEU,
                    "mo_hinh": str(MO_HINH_TOC),
                    "da_co_mo_hinh": MO_HINH_TOC.is_file(),
                    "da_co_pymatting": co_matting,
                    "canh_matting_toi_da": CANH_MATTING_TOI_DA,
                    "cat_mai_can_doi": CAT_MAI_CAN_DOI,
                    "do_dai_mai": DO_DAI_MAI,
                },
                ensure_ascii=False,
                indent=2,
            ))

        if tham_so.tai_mo_hinh:
            print(
                f"Mô hình sẵn sàng: {tai_mo_hinh()}"
            )

        if tham_so.anh is None:
            if not (
                tham_so.kiem_tra
                or tham_so.tai_mo_hinh
            ):
                lenh.error(
                    "Cần --kiem-tra, --tai-mo-hinh hoặc --anh."
                )
            return

        if tham_so.xuat is None:
            lenh.error("Cần --xuat.")

        anh_vao = tham_so.anh.resolve()
        anh_ra = tham_so.xuat.resolve()
        tep_thong_so = anh_ra.with_suffix(".json")

        if (
            anh_ra.suffix.lower() != ".png"
            or anh_vao in {anh_ra, tep_thong_so}
        ):
            raise LoiTachToc(
                "Chọn tên PNG xuất khác ảnh gốc."
            )

        if anh_ra.exists() or tep_thong_so.exists():
            raise LoiTachToc(
                "Kết quả đã tồn tại. Chọn tên xuất mới."
            )

        with anh_vao.open("rb") as tep:
            noi_dung = tep.read(
                GIOI_HAN_DUNG_LUONG + 1
            )

        with BoTachToc() as bo:
            ket_qua = bo.tach(noi_dung)

        anh_ra.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        da_tao = []

        try:
            with anh_ra.open("xb") as tep:
                da_tao.append(anh_ra)
                tep.write(ket_qua["anh_png"])

            with tep_thong_so.open(
                "x",
                encoding="utf-8",
            ) as tep:
                da_tao.append(tep_thong_so)

                json.dump(
                    ket_qua["thong_so"],
                    tep,
                    ensure_ascii=False,
                    indent=2,
                )

        except Exception:
            for tep in da_tao:
                tep.unlink(missing_ok=True)
            raise

        print(f"Ảnh tóc: {anh_ra}")
        print(f"Thông số: {tep_thong_so}")

    except (LoiTachToc, OSError) as loi:
        lenh.exit(1, f"Lỗi: {loi}\n")


if __name__ == "__main__":
    chay_thu()