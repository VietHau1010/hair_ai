"""Lưu và đọc ảnh riêng theo tài khoản."""

import io
import logging
import re
import uuid
import warnings

from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from django.conf import settings
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .models import AnhDaChup


nhat_ky = logging.getLogger(__name__)


def tra_loi(noi_dung, status=200):
    response = JsonResponse(
        noi_dung,
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )

    response["Cache-Control"] = "private, no-store"

    return response


def chua_dang_nhap(request):
    if not request.user.is_authenticated:
        return tra_loi(
            {
                "thanh_cong": False,
                "thong_bao": "Vui lòng đăng nhập lại.",
            },
            401,
        )

    return None


def thu_muc_anh():
    return Path(
        getattr(
            settings,
            "THU_MUC_ANH_CA_NHAN",
            Path(settings.BASE_DIR) / "anh_ca_nhan",
        )
    )


def duong_dan_tep(ten):
    if not re.fullmatch(r"[a-f0-9]{32}\.png", ten):
        raise Http404

    return thu_muc_anh() / ten


def du_lieu(anh):
    return {
        "ma": anh.pk,
        "ten": anh.ten,
        "kieu": anh.kieu,
        "chieu_rong": anh.chieu_rong,
        "chieu_cao": anh.chieu_cao,
        "tao_luc": anh.tao_luc.isoformat(),
        "dia_chi": reverse(
            "thu_toc:xem_anh_da_chup",
            args=[anh.pk],
        ),
        "dia_chi_xoa": reverse(
            "thu_toc:xoa_anh_da_chup",
            args=[anh.pk],
        ),
    }


@require_POST
def luu_anh_da_chup(request):
    loi = chua_dang_nhap(request)

    if loi is not None:
        return loi

    tep = request.FILES.get("anh")

    if tep is None or tep.size > 8 * 1024 * 1024:
        return tra_loi(
            {
                "thanh_cong": False,
                "thong_bao": "Chọn ảnh hợp lệ, tối đa 8 MB.",
            },
            400,
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(tep) as goc:
                if goc.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError

                if (
                    min(goc.size) < 48
                    or goc.width * goc.height > 20_000_000
                ):
                    raise ValueError

                anh = ImageOps.exif_transpose(goc).convert("RGB")
                anh.load()

                bo_dem = io.BytesIO()

                # Tái mã hóa, không giữ metadata ảnh đầu vào.
                anh.save(
                    bo_dem,
                    format="PNG",
                )

                rong, cao = anh.size

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return tra_loi(
            {
                "thanh_cong": False,
                "thong_bao": "Ảnh không hợp lệ hoặc quá lớn.",
            },
            400,
        )

    ten = uuid.uuid4().hex + ".png"
    dich = duong_dan_tep(ten)

    try:
        dich.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with dich.open("xb") as tep_luu:
            tep_luu.write(bo_dem.getvalue())

        anh_luu = AnhDaChup.objects.create(
            chu_so_huu=request.user,
            ten=(
                request.POST.get("ten")
                or "Ảnh thử tóc"
            )[:120],
            ten_tep=ten,
            kieu=(
                "khung"
                if request.POST.get("kieu") == "khung"
                else "don"
            ),
            chieu_rong=rong,
            chieu_cao=cao,
        )

    except Exception:
        dich.unlink(missing_ok=True)

        nhat_ky.exception(
            "Không lưu được ảnh đã chụp"
        )

        return tra_loi(
            {
                "thanh_cong": False,
                "thong_bao": (
                    "Chưa lưu được ảnh. Vui lòng thử lại."
                ),
            },
            500,
        )

    return tra_loi(
        {
            "thanh_cong": True,
            "anh": du_lieu(anh_luu),
        },
        201,
    )


@require_GET
def danh_sach_anh_da_chup(request):
    loi = chua_dang_nhap(request)

    if loi is not None:
        return loi

    danh_sach = AnhDaChup.objects.filter(
        chu_so_huu=request.user,
    )

    trang = Paginator(
        danh_sach,
        12,
    ).get_page(
        request.GET.get("trang", 1)
    )

    return tra_loi(
        {
            "thanh_cong": True,
            "cac_anh": [
                du_lieu(anh)
                for anh in trang
            ],
            "trang": trang.number,
            "trang_tiep": (
                trang.next_page_number()
                if trang.has_next()
                else None
            ),
        }
    )


@require_GET
def xem_anh_da_chup(request, ma):
    if not request.user.is_authenticated:
        raise Http404

    anh = get_object_or_404(
        AnhDaChup,
        pk=ma,
        chu_so_huu=request.user,
    )

    try:
        tep = duong_dan_tep(
            anh.ten_tep
        ).open("rb")

    except FileNotFoundError:
        raise Http404

    response = FileResponse(
        tep,
        content_type="image/png",
        as_attachment=(
            request.GET.get("tai") == "1"
        ),
        filename=f"anh-thu-toc-{anh.pk}.png",
    )

    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"

    return response


@require_POST
def xoa_anh_da_chup(request, ma):
    loi = chua_dang_nhap(request)

    if loi is not None:
        return loi

    anh = get_object_or_404(
        AnhDaChup,
        pk=ma,
        chu_so_huu=request.user,
    )

    try:
        duong_dan_tep(
            anh.ten_tep
        ).unlink(
            missing_ok=True
        )

        anh.delete()

    except OSError:
        return tra_loi(
            {
                "thanh_cong": False,
                "thong_bao": (
                    "Chưa xóa được ảnh. Vui lòng thử lại."
                ),
            },
            500,
        )

    return tra_loi(
        {
            "thanh_cong": True,
        }
    )