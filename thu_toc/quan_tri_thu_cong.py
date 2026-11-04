import warnings

from PIL import Image

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from kieu_toc.models import (
    KieuToc,
    NguoiNoiTieng,
    TacVuTachToc,
)

from .bieu_mau_quan_tri import BieuMauToc
from .bieu_mau_nguoi_noi_tieng import BieuMauNguoiNoiTieng
from .quan_tri import can_quan_tri
from .quan_tri_nguoi_noi_tieng import (
    bat_buoc,
    co_quyen,
    hien_thi,
)


class BieuMauTocThuCong(BieuMauToc):
    """
    Dùng lại toàn bộ trường và kiểm tra ảnh của biểu mẫu tóc cũ.
    Chỉ bổ sung yêu cầu PNG sẵn sàng để thử tóc.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["anh_thu_toc"].required = False

        self.fields["anh_thu_toc"].help_text = (
            "PNG đã tách tóc ở ngoài, có nền trong suốt. "
            "Tối đa 8 MB và 20 triệu điểm ảnh. "
            "Hệ thống giữ nguyên ảnh bạn tải lên."
        )

        self.fields["anh_thu_toc"].widget.attrs["accept"] = "image/png"

        self.fields["anh_gioi_thieu"].widget.attrs["accept"] = (
            "image/jpeg,image/png,image/webp"
        )

    def clean(self):
        du_lieu = super().clean()

        tep = self.files.get("anh_thu_toc")

        if not tep or "anh_thu_toc" in self.errors:
            return du_lieu

        try:
            tep.seek(0)

            with warnings.catch_warnings():
                warnings.simplefilter(
                    "error",
                    Image.DecompressionBombWarning,
                )

                with Image.open(tep) as anh:
                    if getattr(anh, "is_animated", False):
                        raise ValueError("Hãy chọn PNG tĩnh.")

                    alpha = (
                        anh.convert("RGBA")
                        .getchannel("A")
                        .getextrema()
                    )

                    if alpha[1] == 0:
                        raise ValueError(
                            "Ảnh hoàn toàn trong suốt, không có tóc."
                        )

        except (
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as loi:
            self.add_error("anh_thu_toc", str(loi))

        finally:
            tep.seek(0)

        return du_lieu


def kiem_tra_quyen_toc(user, hanh_dong):
    bat_buoc(user, NguoiNoiTieng, "view")
    bat_buoc(user, KieuToc, hanh_dong)


@can_quan_tri
@require_http_methods(["GET", "POST"])
def them_nguoi(request):
    bat_buoc(request.user, NguoiNoiTieng, "add")
    bat_buoc(request.user, NguoiNoiTieng, "view")

    bieu_mau = BieuMauNguoiNoiTieng(
        request.POST if request.method == "POST" else None,
    )

    if request.method == "POST" and bieu_mau.is_valid():
        nguoi = bieu_mau.save()

        messages.success(
            request,
            "Đã tạo hồ sơ. Bạn có thể thêm nhiều kiểu tóc cho người này.",
        )

        return redirect(
            "admin:chi_tiet_nguoi_noi_tieng",
            ma=nguoi.pk,
        )

    return hien_thi(
        request,
        "bieu_mau_toc_thu_cong",
        tieu_de="Thêm người nổi tiếng",
        bieu_mau=bieu_mau,
        la_ho_so=True,
        nhan_luu="Tạo hồ sơ",
    )


@can_quan_tri
@require_http_methods(["GET", "POST"])
def toc_thu_cong(request, ma, ma_toc=None):
    hanh_dong = "change" if ma_toc is not None else "add"

    kiem_tra_quyen_toc(request.user, hanh_dong)

    nguoi = get_object_or_404(
        NguoiNoiTieng,
        pk=ma,
    )

    toc = (
        get_object_or_404(
            KieuToc,
            pk=ma_toc,
            nguoi_noi_tieng=nguoi,
        )
        if ma_toc is not None
        else None
    )

    bieu_mau = BieuMauTocThuCong(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=toc,
    )

    if request.method == "POST" and bieu_mau.is_valid():
        with transaction.atomic():
            # Khóa hồ sơ trong lúc lưu để phối hợp với thao tác xóa.
            nguoi = get_object_or_404(
                NguoiNoiTieng.objects.select_for_update(),
                pk=ma,
            )

            if ma_toc is not None:
                # Không khôi phục lại một kiểu tóc vừa bị xóa.
                toc_hien_tai = get_object_or_404(
                    KieuToc.objects.select_for_update(),
                    pk=ma_toc,
                    nguoi_noi_tieng=nguoi,
                )

                bieu_mau = BieuMauTocThuCong(
                    request.POST,
                    request.FILES,
                    instance=toc_hien_tai,
                )

                if not bieu_mau.is_valid():
                    return hien_thi(
                        request,
                        "bieu_mau_toc_thu_cong",
                        tieu_de="Sửa kiểu tóc",
                        bieu_mau=bieu_mau,
                        nguoi=nguoi,
                        toc=toc_hien_tai,
                        nhan_luu="Lưu thay đổi",
                    )

            ket_qua = bieu_mau.save(commit=False)

            # Luôn thuộc người đang mở; không nhận ID từ biểu mẫu.
            ket_qua.nguoi_noi_tieng = nguoi
            ket_qua.save()
            bieu_mau.save_m2m()

        messages.success(
            request,
            (
                "Đã cập nhật kiểu tóc."
                if ma_toc is not None
                else "Đã thêm tóc bằng PNG, không chạy tách tóc."
            ),
        )

        return redirect(
            "admin:chi_tiet_nguoi_noi_tieng",
            ma=nguoi.pk,
        )

    return hien_thi(
        request,
        "bieu_mau_toc_thu_cong",
        tieu_de=(
            "Sửa kiểu tóc"
            if ma_toc is not None
            else "Thêm tóc bằng PNG đã tách"
        ),
        bieu_mau=bieu_mau,
        nguoi=nguoi,
        toc=toc,
        nhan_luu="Lưu thay đổi" if ma_toc is not None else "Thêm kiểu tóc",
    )


@can_quan_tri
@require_http_methods(["GET", "POST"])
def xoa_toc(request, ma, ma_toc):
    kiem_tra_quyen_toc(request.user, "delete")

    nguoi = get_object_or_404(NguoiNoiTieng, pk=ma)

    toc = get_object_or_404(
        KieuToc,
        pk=ma_toc,
        nguoi_noi_tieng=nguoi,
    )

    if request.method == "POST":
        if request.POST.get("xac_nhan") != "dong_y":
            messages.error(request, "Bạn chưa xác nhận xóa.")

        else:
            with transaction.atomic():
                nguoi = get_object_or_404(
                    NguoiNoiTieng.objects.select_for_update(),
                    pk=ma,
                )

                toc = get_object_or_404(
                    KieuToc.objects.select_for_update(),
                    pk=ma_toc,
                    nguoi_noi_tieng=nguoi,
                )

                # Giữ lịch sử hoàn tất/thất bại.
                # Hủy các tác vụ còn có thể ghi lại tóc đang xóa.
                cac_viec = TacVuTachToc.objects.filter(
                    kieu_toc=toc,
                    trang_thai__in=[
                        TacVuTachToc.TrangThai.CHO_XU_LY,
                        TacVuTachToc.TrangThai.DANG_XU_LY,
                    ],
                )

                if cac_viec.exists():
                    bat_buoc(
                        request.user,
                        TacVuTachToc,
                        "change",
                    )

                    from django.utils import timezone

                    bay_gio = timezone.now()

                    cac_viec.update(
                        trang_thai=TacVuTachToc.TrangThai.THAT_BAI,
                        ma_phien_xu_ly=None,
                        buoc_hien_tai="Đã dừng vì kiểu tóc bị xóa",
                        thong_bao_loi="Kiểu tóc liên kết đã bị quản trị viên xóa.",
                        ket_thuc_luc=bay_gio,
                        ngay_cap_nhat=bay_gio,
                    )

                toc.delete()

            messages.success(request, "Đã xóa kiểu tóc.")

            return redirect(
                "admin:chi_tiet_nguoi_noi_tieng",
                ma=ma,
            )

    return hien_thi(
        request,
        "xac_nhan_xoa_nguoi_va_toc",
        tieu_de="Xóa kiểu tóc",
        nguoi=nguoi,
        toc=toc,
    )


@can_quan_tri
@require_http_methods(["GET", "POST"])
def xoa_ho_so(request, ma):
    # Xóa trọn hồ sơ gồm cả tóc và tác vụ:
    # kiểm tra riêng quyền của từng loại dữ liệu.
    for model in (NguoiNoiTieng, KieuToc, TacVuTachToc):
        bat_buoc(request.user, model, "delete")

    bat_buoc(request.user, NguoiNoiTieng, "view")

    nguoi = get_object_or_404(NguoiNoiTieng, pk=ma)

    if request.method == "POST":
        if request.POST.get("xac_nhan") != "dong_y":
            messages.error(request, "Bạn chưa xác nhận xóa.")

        else:
            with transaction.atomic():
                nguoi = get_object_or_404(
                    NguoiNoiTieng.objects.select_for_update(),
                    pk=ma,
                )

                # Xóa tác vụ trước để gỡ PROTECT.
                # Phiên worker cũ mất tác vụ/token nên không thể hoàn tất.
                nguoi.cac_tac_vu_tach_toc.all().delete()

                # Không để SET_NULL biến tóc người nổi tiếng thành tóc thường.
                nguoi.cac_kieu_toc.all().delete()

                nguoi.delete()

            messages.success(
                request,
                "Đã xóa hồ sơ cùng các kiểu tóc và tác vụ của hồ sơ.",
            )

            return redirect("admin:nguoi_noi_tieng")

    return hien_thi(
        request,
        "xac_nhan_xoa_nguoi_va_toc",
        tieu_de="Xóa toàn bộ hồ sơ",
        nguoi=nguoi,
        xoa_ca_ho_so=True,
        so_toc=nguoi.cac_kieu_toc.count(),
        so_tac_vu=nguoi.cac_tac_vu_tach_toc.count(),
    )