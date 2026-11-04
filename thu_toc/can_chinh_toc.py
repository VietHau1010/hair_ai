import math

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from kieu_toc.models import KieuToc

from .quan_tri import can_quan_tri
from .quan_tri_nguoi_noi_tieng import hien_thi


CAC_THONG_SO = (
    "diem_neo_x",
    "diem_neo_y",
    "ti_le_chieu_rong",
    "do_lech_x",
    "do_lech_y",
)


class BieuMauCanToc(forms.Form):
    ti_le_chieu_rong = forms.FloatField(
        min_value=0.1,
        max_value=5,
    )

    do_lech_x = forms.FloatField(
        min_value=-2,
        max_value=2,
    )

    do_lech_y = forms.FloatField(
        min_value=-2,
        max_value=2,
    )

    def clean(self):
        du_lieu = super().clean()

        for ten, gia_tri in list(du_lieu.items()):
            if not math.isfinite(gia_tri):
                self.add_error(
                    ten,
                    "Thông số phải là số hữu hạn.",
                )

        return du_lieu


def thong_so_hien_tai(toc):
    return {
        ten: getattr(toc, ten)
        for ten in CAC_THONG_SO
    }


def du_lieu_trang(toc):
    return {
        "ma": toc.pk,
        "anh_png": (
            toc.anh_thu_toc.url
            if toc.anh_thu_toc
            else ""
        ),
        "ten_anh": toc.anh_thu_toc.name,
        "thong_so": thong_so_hien_tai(toc),
    }


@can_quan_tri
@require_http_methods(["GET", "POST"])
def can_toc(request, ma_toc):
    if not request.user.has_perm("kieu_toc.change_kieutoc"):
        raise PermissionDenied(
            "Bạn chưa có quyền chỉnh sửa kiểu tóc."
        )

    toc = get_object_or_404(
        KieuToc.objects.select_related("nguoi_noi_tieng"),
        pk=ma_toc,
    )

    if request.method == "GET":
        return hien_thi(
            request,
            "can_chinh_toc",
            tieu_de=f"Căn tóc: {toc.ten}",
            toc=toc,
            nguoi=toc.nguoi_noi_tieng,
            du_lieu_can=du_lieu_trang(toc),
        )

    bieu_mau = BieuMauCanToc(request.POST)

    if not bieu_mau.is_valid():
        return JsonResponse(
            {
                "thanh_cong": False,
                "thong_bao": "Thông số không hợp lệ.",
                "loi": bieu_mau.errors.get_json_data(),
            },
            status=400,
            json_dumps_params={"ensure_ascii": False},
        )

    with transaction.atomic():
        toc = get_object_or_404(
            KieuToc.objects.select_for_update(),
            pk=ma_toc,
        )

        if not toc.anh_thu_toc:
            return JsonResponse(
                {
                    "thanh_cong": False,
                    "thong_bao": (
                        "Kiểu tóc chưa có PNG. "
                        "Hãy bổ sung PNG trước."
                    ),
                },
                status=400,
                json_dumps_params={"ensure_ascii": False},
            )

        # Không ghi kết quả căn của PNG cũ lên PNG vừa được thay.
        if request.POST.get("ten_anh") != toc.anh_thu_toc.name:
            return JsonResponse(
                {
                    "thanh_cong": False,
                    "thong_bao": (
                        "PNG đã được thay ở trang khác. "
                        "Tải lại trang rồi căn lại."
                    ),
                },
                status=409,
                json_dumps_params={"ensure_ascii": False},
            )

        # Phát hiện thông số đã bị sửa ở tab khác.
        try:
            thong_so_cu = {
                ten: float(request.POST[f"cu_{ten}"])
                for ten in CAC_THONG_SO
            }

        except (KeyError, TypeError, ValueError):
            return JsonResponse(
                {
                    "thanh_cong": False,
                    "thong_bao": (
                        "Thiếu thông số gốc. "
                        "Tải lại trang trước khi lưu."
                    ),
                },
                status=400,
                json_dumps_params={"ensure_ascii": False},
            )

        if any(
            not math.isfinite(thong_so_cu[ten])
            or thong_so_cu[ten] != getattr(toc, ten)
            for ten in CAC_THONG_SO
        ):
            return JsonResponse(
                {
                    "thanh_cong": False,
                    "thong_bao": (
                        "Thông số đã thay đổi ở trang khác. "
                        "Tải lại trang để tránh ghi đè."
                    ),
                },
                status=409,
                json_dumps_params={"ensure_ascii": False},
            )

        for ten, gia_tri in bieu_mau.cleaned_data.items():
            setattr(toc, ten, gia_tri)

        # Chỉ cập nhật ba thông số căn chỉnh.
        # Không thay PNG, điểm neo, tên hoặc dữ liệu khác.
        toc.save(
            update_fields=[
                "ti_le_chieu_rong",
                "do_lech_x",
                "do_lech_y",
                "ngay_cap_nhat",
            ],
        )

    messages.success(
        request,
        "Đã lưu căn chỉnh mặc định của kiểu tóc.",
    )

    return JsonResponse(
        {
            "thanh_cong": True,
            "thong_bao": "Đã lưu căn chỉnh.",
            "thong_so": thong_so_hien_tai(toc),
        },
        json_dumps_params={"ensure_ascii": False},
    )