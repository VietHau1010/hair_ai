import io
import logging
import uuid

from PIL import Image

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from kieu_toc.models import KieuToc, TacVuTachToc

from .tach_toc import (
    BoTachToc,
    GIOI_HAN_DUNG_LUONG,
    LoiTachToc,
    doc_anh,
)


nhat_ky = logging.getLogger(__name__)


class BoXuLyTachToc:
    def __init__(self):
        self.bo_tach = None

    def close(self):
        if self.bo_tach is not None:
            self.bo_tach.close()
            self.bo_tach = None

    def nhan_tac_vu(self, ma=None):
        """
        Chỉ nhận tác vụ đang chờ.
        Cập nhật có điều kiện để tránh hai tiến trình nhận cùng tác vụ.
        """
        hang_doi = TacVuTachToc.objects.filter(
            trang_thai=TacVuTachToc.TrangThai.CHO_XU_LY,
        )

        if ma is not None:
            hang_doi = hang_doi.filter(pk=ma)

        ung_vien = (
            hang_doi
            .order_by("ngay_tao", "pk")
            .values_list("pk", flat=True)
            .first()
        )

        if ung_vien is None:
            return None

        ma_phien = uuid.uuid4()
        bay_gio = timezone.now()

        from django.db.models import F

        so_dong = TacVuTachToc.objects.filter(
            pk=ung_vien,
            trang_thai=TacVuTachToc.TrangThai.CHO_XU_LY,
        ).update(
            trang_thai=TacVuTachToc.TrangThai.DANG_XU_LY,
            ma_phien_xu_ly=ma_phien,
            buoc_hien_tai="Đang kiểm tra ảnh và tách tóc",
            thong_bao_loi="",
            so_lan_xu_ly=F("so_lan_xu_ly") + 1,
            bat_dau_luc=bay_gio,
            ket_thuc_luc=None,
            ngay_cap_nhat=bay_gio,
        )

        if so_dong != 1:
            return None

        return TacVuTachToc.objects.select_related(
            "nguoi_noi_tieng",
        ).get(
            pk=ung_vien,
            ma_phien_xu_ly=ma_phien,
        )

    def cap_nhat_buoc(self, tac_vu, noi_dung):
        so_dong = TacVuTachToc.objects.filter(
            pk=tac_vu.pk,
            ma_phien_xu_ly=tac_vu.ma_phien_xu_ly,
            trang_thai=TacVuTachToc.TrangThai.DANG_XU_LY,
        ).update(
            buoc_hien_tai=noi_dung,
            ngay_cap_nhat=timezone.now(),
        )

        if so_dong != 1:
            raise LoiTachToc(
                "Tác vụ đã thay đổi. Dừng phiên xử lý hiện tại."
            )

    def bao_loi(self, tac_vu, noi_dung):
        bay_gio = timezone.now()

        TacVuTachToc.objects.filter(
            pk=tac_vu.pk,
            ma_phien_xu_ly=tac_vu.ma_phien_xu_ly,
            trang_thai=TacVuTachToc.TrangThai.DANG_XU_LY,
        ).update(
            trang_thai=TacVuTachToc.TrangThai.THAT_BAI,
            buoc_hien_tai="Xử lý chưa hoàn tất",
            thong_bao_loi=str(noi_dung)[:2000],
            ma_phien_xu_ly=None,
            ket_thuc_luc=bay_gio,
            ngay_cap_nhat=bay_gio,
        )

    def xu_ly(self, tac_vu):
        cac_tep_da_luu = []

        try:
            # Bản này tạo tóc mới, không ghi đè tóc đã có.
            if tac_vu.kieu_toc_id is not None:
                raise LoiTachToc(
                    "Tác vụ đã liên kết kiểu tóc. "
                    "Không tự ghi đè kết quả cũ."
                )

            ten_toc = tac_vu.ten_kieu_toc.strip()

            if not ten_toc:
                raise LoiTachToc("Chưa có tên kiểu tóc.")

            if not tac_vu.anh_goc:
                raise LoiTachToc("Tác vụ chưa có ảnh gốc.")

            with tac_vu.anh_goc.open("rb") as tep:
                noi_dung = tep.read(GIOI_HAN_DUNG_LUONG + 1)

            if len(noi_dung) > GIOI_HAN_DUNG_LUONG:
                raise LoiTachToc("Ảnh không được vượt quá 8 MB.")

            if self.bo_tach is None:
                self.bo_tach = BoTachToc()

            ket_qua = self.bo_tach.tach(noi_dung)
            thong_so = ket_qua["thong_so"]

            if len(ket_qua["anh_png"]) > GIOI_HAN_DUNG_LUONG:
                raise LoiTachToc(
                    "PNG kết quả vượt quá 8 MB. "
                    "Hãy dùng ảnh đầu vào nhỏ hơn."
                )

            self.cap_nhat_buoc(
                tac_vu,
                "Đang lưu ảnh tóc và thông tin",
            )

            # Tạo ảnh giới thiệu sạch, đúng chiều EXIF.
            rgb = doc_anh(noi_dung)
            tep_gioi_thieu = io.BytesIO()

            Image.fromarray(rgb).save(
                tep_gioi_thieu,
                format="JPEG",
                quality=92,
                optimize=True,
            )

            toc = KieuToc(
                ten=ten_toc,
                mo_ta=(
                    f"Kiểu tóc {ten_toc}, "
                    f"phong cách {tac_vu.nguoi_noi_tieng.ten}."
                ),
                nguoi_noi_tieng_id=tac_vu.nguoi_noi_tieng_id,
                hien_thi_pha_cach=True,
                hien_thi=True,
                diem_neo_x=thong_so["diem_neo_x"],
                diem_neo_y=thong_so["diem_neo_y"],
                ti_le_chieu_rong=thong_so["ti_le_chieu_rong"],
                do_lech_x=thong_so["do_lech_x"],
                do_lech_y=thong_so["do_lech_y"],
            )

            # Mỗi phiên có tên tệp riêng, không đè ảnh cũ.
            ten_tep = uuid.uuid4().hex

            anh_gioi_thieu = toc.anh_gioi_thieu
            ten_luu = anh_gioi_thieu.storage.save(
                anh_gioi_thieu.field.generate_filename(
                    toc,
                    f"{ten_tep}.jpg",
                ),
                ContentFile(tep_gioi_thieu.getvalue()),
            )

            cac_tep_da_luu.append(
                (anh_gioi_thieu.storage, ten_luu)
            )

            toc.anh_gioi_thieu = ten_luu

            anh_thu_toc = toc.anh_thu_toc
            ten_luu = anh_thu_toc.storage.save(
                anh_thu_toc.field.generate_filename(
                    toc,
                    f"{ten_tep}.png",
                ),
                ContentFile(ket_qua["anh_png"]),
            )

            cac_tep_da_luu.append(
                (anh_thu_toc.storage, ten_luu)
            )

            toc.anh_thu_toc = ten_luu

            # Chỉ hoàn tất khi phiên xử lý vẫn còn hiệu lực.
            with transaction.atomic():
                toc.full_clean()
                toc.save()

                bay_gio = timezone.now()

                so_dong = TacVuTachToc.objects.filter(
                    pk=tac_vu.pk,
                    ma_phien_xu_ly=tac_vu.ma_phien_xu_ly,
                    trang_thai=TacVuTachToc.TrangThai.DANG_XU_LY,
                    kieu_toc__isnull=True,
                ).update(
                    kieu_toc_id=toc.pk,
                    trang_thai=TacVuTachToc.TrangThai.HOAN_TAT,
                    buoc_hien_tai="Đã tạo kiểu tóc",
                    thong_bao_loi="",
                    ma_phien_xu_ly=None,
                    ket_thuc_luc=bay_gio,
                    ngay_cap_nhat=bay_gio,
                )

                if so_dong != 1:
                    raise LoiTachToc(
                        "Tác vụ đã thay đổi, không lưu kết quả phiên cũ."
                    )

            return toc

        except BaseException as loi:
            # Database rollback không tự xóa tệp đã ghi.
            for kho_luu, ten_tep in cac_tep_da_luu:
                try:
                    kho_luu.delete(ten_tep)
                except Exception:
                    nhat_ky.exception(
                        "Không dọn được tệp kết quả: %s",
                        ten_tep,
                    )

            if isinstance(loi, (KeyboardInterrupt, SystemExit)):
                self.bao_loi(
                    tac_vu,
                    "Tiến trình xử lý đã dừng. Có thể chạy lại tác vụ.",
                )
                raise

            self.bao_loi(tac_vu, loi)
            raise