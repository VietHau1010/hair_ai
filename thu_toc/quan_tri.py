from functools import wraps

from django.contrib import messages
from django.contrib.auth import (
    get_user_model,
    update_session_auth_hash,
)
from django.contrib.auth.models import Group
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from kieu_toc.models import DangKhuonMat, KieuToc

from .bieu_mau_quan_tri import (
    BieuMauDangMat,
    BieuMauNhomQuyen,
    BieuMauTaiKhoan,
    BieuMauToc,
)


CAC_MUC = {
    "toc": (
        KieuToc,
        BieuMauToc,
        "Kiểu tóc",
        "Ảnh, tư vấn và thông số mô phỏng tóc.",
    ),

    "dang-mat": (
        DangKhuonMat,
        BieuMauDangMat,
        "Dạng khuôn mặt",
        "Liên kết dạng mặt với kiểu tóc phù hợp.",
    ),

    "tai-khoan": (
        get_user_model(),
        BieuMauTaiKhoan,
        "Tài khoản",
        "Thông tin, trạng thái và quyền của người dùng.",
    ),

    "nhom-quyen": (
        Group,
        BieuMauNhomQuyen,
        "Nhóm quyền",
        "Phân quyền cho nhân sự quản trị.",
    ),
}


def can_quan_tri(ham):
    @wraps(ham)
    def xu_ly(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(),
                reverse("tai_khoan:dang_nhap"),
            )

        if (
            not request.user.is_active
            or not request.user.is_staff
        ):
            raise PermissionDenied(
                "Tài khoản chưa có quyền vào quản trị."
            )

        return ham(request, *args, **kwargs)

    return xu_ly


def co_quyen(nguoi, muc, hanh_dong):
    # Quản lý người dùng và quyền chỉ dành cho cấp cao.
    if muc in ("tai-khoan", "nhom-quyen"):
        return nguoi.is_superuser

    model = CAC_MUC[muc][0]

    ten = (
        f"{model._meta.app_label}."
        f"{hanh_dong}_{model._meta.model_name}"
    )

    if hanh_dong == "view":
        sua = (
            f"{model._meta.app_label}."
            f"change_{model._meta.model_name}"
        )

        return nguoi.has_perm(ten) or nguoi.has_perm(sua)

    return nguoi.has_perm(ten)


def lay_muc(request, muc, hanh_dong="view"):
    if muc not in CAC_MUC:
        raise Http404

    if not co_quyen(request.user, muc, hanh_dong):
        raise PermissionDenied(
            "Bạn chưa được cấp quyền thực hiện thao tác này."
        )

    return CAC_MUC[muc]


def du_lieu_chung(request, muc=""):
    menu = [
        {
            "ma": ma,
            "ten": cau_hinh[2],
            "mo_ta": cau_hinh[3],
        }
        for ma, cau_hinh in CAC_MUC.items()
        if co_quyen(request.user, ma, "view")
    ]

    return {
        "menu_quan_tri": menu,
        "muc_hien_tai": muc,
    }


@can_quan_tri
@require_http_methods(["GET"])
def tong_quan(request):
    du_lieu = du_lieu_chung(request)
    the = []

    for muc in du_lieu["menu_quan_tri"]:
        model = CAC_MUC[muc["ma"]][0]

        the.append({
            **muc,
            "so_luong": model.objects.count(),
        })

    du_lieu.update(
        tieu_de="Tổng quan quản trị",
        cac_the=the,
    )

    return render(
        request,
        "thu_toc/quan_tri/tong_quan.html",
        du_lieu,
    )


@can_quan_tri
@require_http_methods(["GET"])
def danh_sach(request, muc):
    model, _, ten, mo_ta = lay_muc(request, muc)

    qs = model.objects.all()

    tu_khoa = request.GET.get("q", "").strip()[:150]
    trang_thai = request.GET.get("trang_thai", "")
    dang_mat = request.GET.get("dang_mat", "")

    # Bổ sung dữ liệu chia nhóm cho riêng mục Kiểu tóc.
    nhom_toc = ""
    so_toc_quet_mat = 0
    so_toc_nguoi_noi_tieng = 0
    lien_ket_quet_mat = ""
    lien_ket_nguoi_noi_tieng = ""

    if muc == "toc":
        nhom_toc = request.GET.get(
            "nhom_toc",
            "quet-mat",
        )

        if nhom_toc not in {
            "quet-mat",
            "nguoi-noi-tieng",
        }:
            nhom_toc = "quet-mat"

        # Số lượng tổng của mỗi nhóm, trước khi áp dụng bộ lọc.
        so_toc_quet_mat = qs.filter(
            nguoi_noi_tieng__isnull=True,
        ).count()

        so_toc_nguoi_noi_tieng = qs.filter(
            nguoi_noi_tieng__isnull=False,
        ).count()

        # Không sửa dữ liệu; chỉ lọc danh sách theo tab.
        qs = qs.filter(
            nguoi_noi_tieng__isnull=(
                nhom_toc == "quet-mat"
            ),
        )

        qs = (
            qs.select_related("nguoi_noi_tieng")
            .prefetch_related("dang_mat_phu_hop")
        )

        # Đổi tab giữ bộ lọc hiện tại và quay về trang đầu.
        tham_so_tab = request.GET.copy()
        tham_so_tab.pop("trang", None)

        tham_so_tab["nhom_toc"] = "quet-mat"
        lien_ket_quet_mat = "?" + tham_so_tab.urlencode()

        tham_so_tab["nhom_toc"] = "nguoi-noi-tieng"
        lien_ket_nguoi_noi_tieng = (
            "?" + tham_so_tab.urlencode()
        )

        if tu_khoa:
            qs = qs.filter(
                Q(ten__icontains=tu_khoa)
                | Q(mo_ta__icontains=tu_khoa)
            )

        if trang_thai in ("1", "0"):
            qs = qs.filter(
                hien_thi=trang_thai == "1"
            )

        if dang_mat in dict(DangKhuonMat.CAC_DANG_MAT):
            qs = qs.filter(
                dang_mat_phu_hop__ma=dang_mat
            )

        qs = qs.order_by(
            "thu_tu",
            "ten",
            "pk",
        ).distinct()

    elif muc == "tai-khoan":
        if tu_khoa:
            qs = qs.filter(
                Q(username__icontains=tu_khoa)
                | Q(email__icontains=tu_khoa)
                | Q(first_name__icontains=tu_khoa)
                | Q(last_name__icontains=tu_khoa)
            )

        if trang_thai in ("1", "0"):
            qs = qs.filter(
                is_active=trang_thai == "1"
            )

        qs = qs.order_by("username", "pk")

    elif muc == "nhom-quyen":
        qs = (
            qs.prefetch_related("permissions")
            .filter(name__icontains=tu_khoa)
            .order_by("name", "pk")
        )

    else:
        qs = qs.order_by("ma", "pk")

        if tu_khoa:
            cac_ma = [
                ma
                for ma, nhan in DangKhuonMat.CAC_DANG_MAT
                if tu_khoa.casefold() in nhan.casefold()
            ]

            qs = qs.filter(
                Q(ma__icontains=tu_khoa)
                | Q(ma__in=cac_ma)
            )

    trang = Paginator(qs, 12).get_page(
        request.GET.get("trang")
    )

    tham_so = request.GET.copy()
    tham_so.pop("trang", None)

    if muc == "toc":
        tham_so["nhom_toc"] = nhom_toc

    du_lieu = du_lieu_chung(request, muc)

    du_lieu.update(
        tieu_de=ten,
        mo_ta=mo_ta,
        trang=trang,
        tu_khoa=tu_khoa,
        trang_thai=trang_thai,
        dang_mat=dang_mat,
        tham_so=tham_so.urlencode(),
        cac_dang_mat=DangKhuonMat.CAC_DANG_MAT,

        nhom_toc=nhom_toc,
        so_toc_quet_mat=so_toc_quet_mat,
        so_toc_nguoi_noi_tieng=so_toc_nguoi_noi_tieng,
        lien_ket_quet_mat=lien_ket_quet_mat,
        lien_ket_nguoi_noi_tieng=lien_ket_nguoi_noi_tieng,

        duoc_them=co_quyen(
            request.user, muc, "add"
        ),

        duoc_sua=co_quyen(
            request.user, muc, "change"
        ),

        duoc_xoa=co_quyen(
            request.user, muc, "delete"
        ),
    )

    return render(
        request,
        "thu_toc/quan_tri/danh_sach.html",
        du_lieu,
    )


def bao_ve_tai_khoan(
    request,
    muc,
    doi_tuong,
    bieu_mau=None,
):
    if muc != "tai-khoan" or not doi_tuong:
        return

    if doi_tuong.pk == request.user.pk:
        if bieu_mau is None:
            raise ValidationError(
                "Không thể xóa tài khoản đang đăng nhập."
            )

        if not all(
            bieu_mau.cleaned_data.get(ten)
            for ten in (
                "is_active",
                "is_staff",
                "is_superuser",
            )
        ):
            raise ValidationError(
                "Không thể tự khóa hoặc hạ quyền "
                "tài khoản đang đăng nhập."
            )

    if (
        doi_tuong.is_active
        and doi_tuong.is_staff
        and doi_tuong.is_superuser
    ):
        giu_quyen = (
            bieu_mau is not None
            and all(
                bieu_mau.cleaned_data.get(ten)
                for ten in (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                )
            )
        )

        con_quan_tri_khac = (
            get_user_model().objects.filter(
                is_active=True,
                is_staff=True,
                is_superuser=True,
            )
            .exclude(pk=doi_tuong.pk)
            .exists()
        )

        if not giu_quyen and not con_quan_tri_khac:
            raise ValidationError(
                "Phải giữ ít nhất một quản trị viên "
                "cấp cao đang hoạt động."
            )


@can_quan_tri
@require_http_methods(["GET", "POST"])
def bieu_mau(request, muc, ma=None):
    model, lop_form, ten, _ = lay_muc(
        request,
        muc,
        "change" if ma else "add",
    )

    doi_tuong = (
        get_object_or_404(model, pk=ma)
        if ma
        else None
    )

    form = lop_form(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=doi_tuong,
    )

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if muc == "tai-khoan" and ma:
                    list(
                        model.objects.select_for_update()
                        .filter(is_superuser=True)
                        .values_list("pk", flat=True)
                    )

                    doi_tuong = get_object_or_404(
                        model,
                        pk=ma,
                    )

                bao_ve_tai_khoan(
                    request,
                    muc,
                    doi_tuong,
                    form,
                )

                da_luu = form.save()

            if (
                muc == "tai-khoan"
                and da_luu.pk == request.user.pk
            ):
                update_session_auth_hash(
                    request,
                    da_luu,
                )

            messages.success(
                request,
                "Đã lưu " + ten.lower() + " thành công.",
            )

            return redirect(
                "admin:danh_sach",
                muc=muc,
            )

        except ValidationError as loi:
            form.add_error(None, loi)

    du_lieu = du_lieu_chung(request, muc)

    du_lieu.update(
        tieu_de=(
            ("Sửa " if ma else "Thêm ")
            + ten.lower()
        ),
        bieu_mau=form,
        doi_tuong=doi_tuong,
    )

    return render(
        request,
        "thu_toc/quan_tri/bieu_mau.html",
        du_lieu,
    )


@can_quan_tri
@require_http_methods(["POST"])
def xoa(request, muc, ma):
    model, _, ten, _ = lay_muc(
        request,
        muc,
        "delete",
    )

    doi_tuong = get_object_or_404(
        model,
        pk=ma,
    )

    if request.POST.get("xac_nhan") != "dong_y":
        messages.error(
            request,
            "Chưa xác nhận xóa dữ liệu.",
        )

        return redirect(
            "admin:danh_sach",
            muc=muc,
        )

    try:
        with transaction.atomic():
            if muc == "tai-khoan":
                list(
                    model.objects.select_for_update()
                    .filter(is_superuser=True)
                    .values_list("pk", flat=True)
                )

                doi_tuong = get_object_or_404(
                    model,
                    pk=ma,
                )

            bao_ve_tai_khoan(
                request,
                muc,
                doi_tuong,
            )

            doi_tuong.delete()

        messages.success(
            request,
            "Đã xóa " + ten.lower() + ".",
        )

    except (ValidationError, ProtectedError) as loi:
        messages.error(
            request,
            (
                loi.messages[0]
                if isinstance(loi, ValidationError)
                else (
                    "Dữ liệu đang được tham chiếu "
                    "nên không thể xóa."
                )
            ),
        )

    return redirect(
        "admin:danh_sach",
        muc=muc,
    )