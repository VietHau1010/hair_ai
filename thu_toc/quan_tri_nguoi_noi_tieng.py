from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)

from kieu_toc.models import (
    KieuToc,
    NguoiNoiTieng,
    TacVuTachToc,
)

from .bieu_mau_nguoi_noi_tieng import (
    BieuMauNguoiNoiTieng,
    BieuMauThemToc,
)
from .quan_tri import can_quan_tri, du_lieu_chung


def co_quyen(user, model, hanh_dong):
    ten = model._meta.model_name

    return user.has_perm(
        f"kieu_toc.{hanh_dong}_{ten}"
    ) or (
        hanh_dong == "view"
        and user.has_perm(f"kieu_toc.change_{ten}")
    )


def bat_buoc(user, model, hanh_dong):
    if not co_quyen(user, model, hanh_dong):
        raise PermissionDenied(
            "Bạn chưa có quyền thực hiện thao tác này."
        )


def duoc_them(user):
    return all([
        co_quyen(user, NguoiNoiTieng, "view"),
        co_quyen(user, TacVuTachToc, "view"),
        co_quyen(user, TacVuTachToc, "add"),
        co_quyen(user, KieuToc, "add"),
    ])


def hien_thi(request, tep, **du_lieu):
    chung = du_lieu_chung(
        request,
        "nguoi-noi-tieng",
    )

    chung.update(
        duoc_them=duoc_them(request.user),
        duoc_sua=co_quyen(
            request.user,
            NguoiNoiTieng,
            "change",
        ),
        duoc_xoa=co_quyen(
            request.user,
            NguoiNoiTieng,
            "delete",
        ),
        duoc_sua_toc=co_quyen(
            request.user,
            KieuToc,
            "change",
        ),
        duoc_xem_toc=co_quyen(
            request.user,
            KieuToc,
            "view",
        ),
        duoc_xem_tac_vu=co_quyen(
            request.user,
            TacVuTachToc,
            "view",
        ),
    )

    chung.update(du_lieu)

    return render(
        request,
        f"thu_toc/quan_tri/{tep}.html",
        chung,
    )


@can_quan_tri
@require_GET
def danh_sach(request):
    bat_buoc(
        request.user,
        NguoiNoiTieng,
        "view",
    )

    q = request.GET.get("q", "").strip()[:150]

    ds = NguoiNoiTieng.objects.annotate(
        so_toc=Count("cac_kieu_toc"),
    )

    if q:
        ds = ds.filter(
            Q(ten__icontains=q)
            | Q(ten_khac__icontains=q)
        )

    trang = Paginator(
        ds.order_by("thu_tu", "ten", "pk"),
        12,
    ).get_page(request.GET.get("trang"))

    return hien_thi(
        request,
        "danh_sach_nguoi_noi_tieng",
        tieu_de="Người nổi tiếng",
        trang=trang,
        tu_khoa=q,
    )


@can_quan_tri
@require_GET
def chi_tiet(request, ma):
    bat_buoc(
        request.user,
        NguoiNoiTieng,
        "view",
    )

    nguoi = get_object_or_404(
        NguoiNoiTieng,
        pk=ma,
    )

    if co_quyen(request.user, KieuToc, "view"):
        toc = KieuToc.objects.filter(
            nguoi_noi_tieng=nguoi,
        )
    else:
        toc = KieuToc.objects.none()

    if co_quyen(request.user, TacVuTachToc, "view"):
        tac_vu = TacVuTachToc.objects.filter(
            nguoi_noi_tieng=nguoi,
        )
    else:
        tac_vu = TacVuTachToc.objects.none()

    return hien_thi(
        request,
        "chi_tiet_nguoi_noi_tieng",
        tieu_de=nguoi.ten,
        nguoi=nguoi,
        trang=Paginator(
            toc,
            12,
        ).get_page(request.GET.get("trang")),
        cac_tac_vu=tac_vu[:20],
    )


@can_quan_tri
@require_http_methods(["GET", "POST"])
def them_toc(request, ma=None):
    if not duoc_them(request.user):
        raise PermissionDenied(
            "Cần quyền xem người nổi tiếng, "
            "xem/thêm tác vụ và thêm kiểu tóc."
        )

    nguoi = (
        get_object_or_404(NguoiNoiTieng, pk=ma)
        if ma is not None
        else None
    )

    form = BieuMauThemToc(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        nguoi=nguoi,
    )

    if request.method == "POST" and form.is_valid():
        da_chon = nguoi

        if da_chon is None:
            trung_ten = list(
                NguoiNoiTieng.objects.filter(
                    ten__iexact=form.cleaned_data["ten_nguoi"],
                )[:2]
            )

            if len(trung_ten) > 1:
                form.add_error(
                    "ten_nguoi",
                    "Có nhiều người trùng tên. "
                    "Hãy mở đúng hồ sơ rồi chọn Thêm kiểu tóc.",
                )

            elif trung_ten:
                da_chon = trung_ten[0]

            elif not co_quyen(
                request.user,
                NguoiNoiTieng,
                "add",
            ):
                form.add_error(
                    "ten_nguoi",
                    "Bạn chưa có quyền tạo người nổi tiếng mới.",
                )

        if not form.errors:
            tac_vu = None

            try:
                with transaction.atomic():
                    if da_chon is None:
                        da_chon = NguoiNoiTieng.objects.create(
                            ten=form.cleaned_data["ten_nguoi"],
                        )

                    tac_vu = TacVuTachToc(
                        nguoi_noi_tieng=da_chon,
                        ten_kieu_toc=form.cleaned_data[
                            "ten_kieu_toc"
                        ],
                        nguoi_tao=request.user,
                        anh_goc=form.cleaned_data["anh_goc"],
                    )

                    tac_vu.full_clean()
                    tac_vu.save()

            except Exception:
                if (
                    tac_vu is not None
                    and tac_vu.anh_goc
                    and getattr(
                        tac_vu.anh_goc,
                        "_committed",
                        False,
                    )
                ):
                    tac_vu.anh_goc.delete(save=False)

                raise

            messages.success(
                request,
                "Đã nhận ảnh và đưa vào hàng đợi tách tóc.",
            )

            return redirect(
                "admin:ket_qua_tach_toc",
                ma=tac_vu.pk,
            )

    return hien_thi(
        request,
        "bieu_mau_nguoi_noi_tieng",
        tieu_de="Thêm kiểu tóc người nổi tiếng",
        bieu_mau=form,
        nguoi=nguoi,
        la_them_toc=True,
    )


@can_quan_tri
@require_http_methods(["GET", "POST"])
def sua(request, ma):
    bat_buoc(
        request.user,
        NguoiNoiTieng,
        "change",
    )

    nguoi = get_object_or_404(
        NguoiNoiTieng,
        pk=ma,
    )

    form = BieuMauNguoiNoiTieng(
        request.POST if request.method == "POST" else None,
        instance=nguoi,
    )

    if request.method == "POST" and form.is_valid():
        form.save()

        messages.success(
            request,
            "Đã cập nhật người nổi tiếng.",
        )

        return redirect(
            "admin:chi_tiet_nguoi_noi_tieng",
            ma=nguoi.pk,
        )

    return hien_thi(
        request,
        "bieu_mau_nguoi_noi_tieng",
        tieu_de="Sửa người nổi tiếng",
        bieu_mau=form,
        nguoi=nguoi,
        la_them_toc=False,
    )


@can_quan_tri
@require_POST
def xoa(request, ma):
    bat_buoc(
        request.user,
        NguoiNoiTieng,
        "delete",
    )

    nguoi = get_object_or_404(
        NguoiNoiTieng,
        pk=ma,
    )

    if request.POST.get("xac_nhan") != "dong_y":
        messages.error(
            request,
            "Chưa xác nhận xóa.",
        )

    else:
        with transaction.atomic():
            nguoi = get_object_or_404(
                NguoiNoiTieng.objects.select_for_update(),
                pk=ma,
            )

            if (
                nguoi.cac_kieu_toc.exists()
                or nguoi.cac_tac_vu_tach_toc.exists()
            ):
                messages.error(
                    request,
                    "Hồ sơ đã có tóc hoặc tác vụ. "
                    "Hãy sửa và bỏ chọn Hiển thị trên website để ẩn.",
                )

            else:
                nguoi.delete()

                messages.success(
                    request,
                    "Đã xóa hồ sơ trống.",
                )

                return redirect(
                    "admin:nguoi_noi_tieng",
                )

    return redirect(
        "admin:chi_tiet_nguoi_noi_tieng",
        ma=ma,
    )


@can_quan_tri
@require_GET
def ket_qua(request, ma):
    bat_buoc(
        request.user,
        NguoiNoiTieng,
        "view",
    )

    bat_buoc(
        request.user,
        TacVuTachToc,
        "view",
    )

    tac_vu = get_object_or_404(
        TacVuTachToc.objects.select_related(
            "nguoi_noi_tieng",
            "kieu_toc",
        ),
        pk=ma,
    )

    return hien_thi(
        request,
        "ket_qua_tach_toc",
        tieu_de="Kết quả tách tóc",
        tac_vu=tac_vu,
        dang_cho=tac_vu.trang_thai in {
            "cho_xu_ly",
            "dang_xu_ly",
        },
        duoc_thu_lai=(
            co_quyen(
                request.user,
                TacVuTachToc,
                "change",
            )
            and co_quyen(
                request.user,
                KieuToc,
                "add",
            )
        ),
    )


@can_quan_tri
@require_GET
def trang_thai(request, ma):
    bat_buoc(
        request.user,
        NguoiNoiTieng,
        "view",
    )

    bat_buoc(
        request.user,
        TacVuTachToc,
        "view",
    )

    tac_vu = get_object_or_404(
        TacVuTachToc,
        pk=ma,
    )

    phan_hoi = JsonResponse(
        {
            "trang_thai": tac_vu.trang_thai,
            "nhan": tac_vu.get_trang_thai_display(),
            "buoc": tac_vu.buoc_hien_tai,
            "loi": tac_vu.thong_bao_loi,
            "ket_thuc": tac_vu.trang_thai in {
                "hoan_tat",
                "that_bai",
            },
        },
        json_dumps_params={"ensure_ascii": False},
    )

    phan_hoi["Cache-Control"] = "no-store"

    return phan_hoi


@can_quan_tri
@require_POST
def thu_lai(request, ma):
    bat_buoc(
        request.user,
        NguoiNoiTieng,
        "view",
    )

    bat_buoc(
        request.user,
        TacVuTachToc,
        "view",
    )

    bat_buoc(
        request.user,
        TacVuTachToc,
        "change",
    )

    bat_buoc(
        request.user,
        KieuToc,
        "add",
    )

    get_object_or_404(
        TacVuTachToc,
        pk=ma,
    )

    so_dong = TacVuTachToc.objects.filter(
        pk=ma,
        trang_thai="that_bai",
        kieu_toc__isnull=True,
    ).update(
        trang_thai="cho_xu_ly",
        buoc_hien_tai="Chờ xử lý lại",
        thong_bao_loi="",
        ma_phien_xu_ly=None,
        bat_dau_luc=None,
        ket_thuc_luc=None,
        ngay_cap_nhat=timezone.now(),
    )

    if so_dong:
        messages.success(
            request,
            "Đã đưa tác vụ vào hàng đợi lần nữa.",
        )

    else:
        messages.error(
            request,
            "Chỉ chạy lại tác vụ thất bại "
            "và chưa tạo kiểu tóc.",
        )

    return redirect(
        "admin:ket_qua_tach_toc",
        ma=ma,
    )