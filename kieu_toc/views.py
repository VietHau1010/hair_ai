from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .kham_pha import toc_duoc_hien_thi
from .models import DangKhuonMat, KieuTocYeuThich


def danh_sach_kieu_toc(request):
    ma_dang_mat = request.GET.get("dang_mat", "")

    cac_ma_hop_le = {
        ma
        for ma, ten in DangKhuonMat.CAC_DANG_MAT
    }

    if ma_dang_mat not in cac_ma_hop_le:
        ma_dang_mat = ""

    cac_kieu_toc = (
        toc_duoc_hien_thi()
        .filter(nguoi_noi_tieng__isnull=True)
        .prefetch_related("dang_mat_phu_hop")
    )

    if ma_dang_mat:
        cac_kieu_toc = cac_kieu_toc.filter(
            dang_mat_phu_hop__ma=ma_dang_mat
        )

    cac_ma_yeu_thich = set()

    if request.user.is_authenticated:
        cac_ma_yeu_thich = set(
            KieuTocYeuThich.objects
            .filter(tai_khoan=request.user)
            .values_list("kieu_toc_id", flat=True)
        )

    return render(
        request,
        "kieu_toc/danh_sach_kieu_toc.html",
        {
            "cac_kieu_toc": cac_kieu_toc,
            "cac_dang_mat": DangKhuonMat.CAC_DANG_MAT,
            "dang_mat_da_chon": ma_dang_mat,
            "cac_ma_yeu_thich": cac_ma_yeu_thich,
            "la_trang_yeu_thich": False,
        },
    )


@login_required(login_url="tai_khoan:dang_nhap")
def danh_sach_yeu_thich(request):
    cac_kieu_toc = (
        toc_duoc_hien_thi()
        .filter(
            cac_luot_yeu_thich__tai_khoan=request.user,
        )
        .prefetch_related("dang_mat_phu_hop")
    )

    cac_ma_yeu_thich = set(
        cac_kieu_toc.values_list("pk", flat=True)
    )

    return render(
        request,
        "kieu_toc/danh_sach_kieu_toc.html",
        {
            "cac_kieu_toc": cac_kieu_toc,
            "cac_ma_yeu_thich": cac_ma_yeu_thich,
            "la_trang_yeu_thich": True,
        },
    )


@login_required(login_url="tai_khoan:dang_nhap")
@require_POST
def luu_yeu_thich(request, ma_toc):
    kieu_toc = get_object_or_404(
        toc_duoc_hien_thi(),
        pk=ma_toc,
    )

    KieuTocYeuThich.objects.get_or_create(
        tai_khoan=request.user,
        kieu_toc=kieu_toc,
    )

    messages.success(
        request,
        "Đã lưu kiểu tóc vào danh sách yêu thích.",
    )

    return redirect("kieu_toc:danh_sach")


@login_required(login_url="tai_khoan:dang_nhap")
@require_POST
def bo_yeu_thich(request, ma_toc):
    KieuTocYeuThich.objects.filter(
        tai_khoan=request.user,
        kieu_toc_id=ma_toc,
    ).delete()

    messages.success(
        request,
        "Đã bỏ kiểu tóc khỏi danh sách yêu thích.",
    )

    if request.POST.get("ve_trang") == "yeu_thich":
        return redirect("kieu_toc:yeu_thich")

    return redirect("kieu_toc:danh_sach")