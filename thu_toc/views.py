import io

from PIL import Image, UnidentifiedImageError

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from kieu_toc.kham_pha import (
    du_lieu_toc,
    toc_duoc_hien_thi,
)

from .ket_noi_colab import (
    LoiKetNoiColab,
    kiem_tra_colab,
    phan_tich_anh_colab,
)


def trang_chu(request):
    return render(
        request,
        "thu_toc/trang_chu.html",
    )


@login_required(login_url="tai_khoan:dang_nhap")
def phong_thu_toc(request):
    return render(
        request,
        "thu_toc/phong_thu_toc.html",
    )


@require_GET
def trang_thai_ai(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "thanh_cong": False,
                "thong_bao": "Vui lòng đăng nhập.",
            },
            status=401,
        )

    try:
        return JsonResponse(
            kiem_tra_colab(),
            json_dumps_params={"ensure_ascii": False},
        )

    except LoiKetNoiColab as loi:
        return JsonResponse(
            {
                "thanh_cong": False,
                "san_sang": False,
                "thong_bao": str(loi),
            },
            status=503,
            json_dumps_params={"ensure_ascii": False},
        )


def du_lieu_kieu_toc(toc):
    return du_lieu_toc(toc)


@require_POST
def quet_khuon_mat(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "thanh_cong": False,
                "thong_bao": (
                    "Phiên đăng nhập đã hết. "
                    "Vui lòng đăng nhập lại."
                ),
            },
            status=401,
        )

    tep_anh = request.FILES.get("anh")

    if tep_anh is None:
        return JsonResponse(
            {
                "thanh_cong": False,
                "thong_bao": "Chưa nhận được ảnh.",
            },
            status=400,
        )

    if tep_anh.size > 8 * 1024 * 1024:
        return JsonResponse(
            {
                "thanh_cong": False,
                "thong_bao": "Ảnh vượt quá dung lượng 8 MB.",
            },
            status=400,
        )

    noi_dung_anh = tep_anh.read()

    try:
        with Image.open(io.BytesIO(noi_dung_anh)) as anh:
            if (
                min(anh.size) < 48
                or anh.width * anh.height > 20_000_000
            ):
                raise ValueError(
                    "Kích thước ảnh không hợp lệ."
                )

            anh.verify()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return JsonResponse(
            {
                "thanh_cong": False,
                "thong_bao": (
                    "Ảnh không hợp lệ hoặc kích thước không phù hợp."
                ),
            },
            status=400,
        )

    try:
        ket_qua = phan_tich_anh_colab(noi_dung_anh)

    except LoiKetNoiColab as loi:
        return JsonResponse(
            {
                "thanh_cong": False,
                "thong_bao": str(loi),
            },
            status=503,
            json_dumps_params={"ensure_ascii": False},
        )

    cac_toc_goi_y = []
    cac_toc_pha_cach = []

    # Giữ nguyên ngưỡng chấp nhận của AI.
    if ket_qua.get("chap_nhan") is True:
        ma_dang_mat = ket_qua.get("dang_mat")

        if ma_dang_mat not in {
            "Heart",
            "Oblong",
            "Oval",
            "Round",
            "Square",
        }:
            return JsonResponse(
                {
                    "thanh_cong": False,
                    "thong_bao": "Dạng mặt trả về không hợp lệ.",
                },
                status=502,
            )

        # Hợp khuôn mặt: mẫu tóc thông thường,
        # có liên kết với dạng mặt vừa quét.
        cac_kieu_toc = (
            toc_duoc_hien_thi()
            .filter(
                nguoi_noi_tieng__isnull=True,
                dang_mat_phu_hop__ma=ma_dang_mat,
            )
            .distinct()
        )

        cac_toc_goi_y = [
            du_lieu_kieu_toc(toc)
            for toc in cac_kieu_toc
        ]

        # Phá cách:
        # - Chỉ mẫu tóc thông thường.
        # - Được bật hiển thị Phá cách.
        # - Có PNG thử tóc.
        # - Không được gán phù hợp với dạng mặt vừa quét.
        #
        # exclude trên quan hệ nhiều-nhiều sẽ loại cả mẫu
        # được gán nhiều dạng mặt nếu có dạng mặt hiện tại.
        cac_kieu_toc_pha_cach = (
            toc_duoc_hien_thi()
            .filter(
                nguoi_noi_tieng__isnull=True,
                hien_thi_pha_cach=True,
            )
            .exclude(
                dang_mat_phu_hop__ma=ma_dang_mat,
            )
            .exclude(anh_thu_toc="")
            .exclude(anh_thu_toc__isnull=True)
            .distinct()
        )

        cac_toc_pha_cach = [
            du_lieu_kieu_toc(toc)
            for toc in cac_kieu_toc_pha_cach
        ]

    ket_qua["cac_toc_goi_y"] = cac_toc_goi_y
    ket_qua["cac_toc_pha_cach"] = cac_toc_pha_cach

    return JsonResponse(
        ket_qua,
        json_dumps_params={"ensure_ascii": False},
    )