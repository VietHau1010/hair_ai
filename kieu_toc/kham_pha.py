import unicodedata

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import KieuToc, NguoiNoiTieng


def bo_dau(chuoi):
    chuoi = str(chuoi).casefold().replace("đ", "d")

    return "".join(
        ky_tu
        for ky_tu in unicodedata.normalize("NFD", chuoi)
        if not unicodedata.combining(ky_tu)
    )


def toc_duoc_hien_thi():
    return (
        KieuToc.objects
        .filter(hien_thi=True)
        .filter(
            Q(nguoi_noi_tieng__isnull=True)
            | Q(nguoi_noi_tieng__hien_thi=True)
        )
        .select_related("nguoi_noi_tieng")
    )


def du_lieu_toc(toc):
    nguoi = toc.nguoi_noi_tieng

    return {
        "ma": toc.pk,
        "ten": toc.ten,
        "mo_ta": toc.mo_ta,

        "anh_gioi_thieu": (
            toc.anh_gioi_thieu.url
            if toc.anh_gioi_thieu
            else None
        ),

        "anh_thu_toc": (
            toc.anh_thu_toc.url
            if toc.anh_thu_toc
            else None
        ),

        "co_the_thu": bool(toc.anh_thu_toc),

        "diem_neo_x": toc.diem_neo_x,
        "diem_neo_y": toc.diem_neo_y,
        "ti_le_chieu_rong": toc.ti_le_chieu_rong,
        "do_lech_x": toc.do_lech_x,
        "do_lech_y": toc.do_lech_y,

        "nguoi_noi_tieng": (
            {
                "ma": nguoi.pk,
                "ten": nguoi.ten,
            }
            if nguoi
            else None
        ),
    }


def tim_toc_nguoi_noi_tieng(request):
    tu_khoa = request.GET.get("q", "").strip()[:100]

    cac_toc = (
        toc_duoc_hien_thi()
        .filter(nguoi_noi_tieng__isnull=False)
        .exclude(anh_thu_toc="")
        .exclude(anh_thu_toc__isnull=True)
    )

    ma_toc = request.GET.get("ma", "").strip()

    if ma_toc:
        if (
            not ma_toc.isascii()
            or not ma_toc.isdigit()
            or len(ma_toc) > 18
        ):
            cac_toc = cac_toc.none()
        else:
            cac_toc = cac_toc.filter(pk=int(ma_toc))

    if tu_khoa:
        cac_tu = bo_dau(tu_khoa).split()

        cac_ma = [
            ma
            for ma, ten, ten_khac in (
                NguoiNoiTieng.objects
                .filter(hien_thi=True)
                .values_list("pk", "ten", "ten_khac")
                .iterator()
            )
            if all(
                tu in bo_dau(f"{ten} {ten_khac}")
                for tu in cac_tu
            )
        ]

        cac_toc = cac_toc.filter(
            Q(nguoi_noi_tieng_id__in=cac_ma)
            | Q(ten__icontains=tu_khoa)
        )

    cac_toc = cac_toc.order_by(
        "nguoi_noi_tieng__thu_tu",
        "nguoi_noi_tieng__ten",
        "nguoi_noi_tieng_id",
        "thu_tu",
        "ten",
        "pk",
    )

    trang = Paginator(cac_toc, 12).get_page(
        request.GET.get("trang", 1)
    )

    return tu_khoa, trang


@require_GET
def nguoi_noi_tieng(request):
    tu_khoa, trang = tim_toc_nguoi_noi_tieng(request)

    return render(
        request,
        "kieu_toc/nguoi_noi_tieng.html",
        {
            "tu_khoa": tu_khoa,
            "trang": trang,
        },
    )


@require_GET
def du_lieu_nguoi_noi_tieng(request):
    tu_khoa, trang = tim_toc_nguoi_noi_tieng(request)

    return JsonResponse(
        {
            "thanh_cong": True,
            "tu_khoa": tu_khoa,

            "cac_kieu_toc": [
                du_lieu_toc(toc)
                for toc in trang
            ],

            "trang": trang.number,
            "tong_trang": trang.paginator.num_pages,
            "tong_so": trang.paginator.count,
            "co_truoc": trang.has_previous(),
            "co_sau": trang.has_next(),
        },
        json_dumps_params={"ensure_ascii": False},
    )