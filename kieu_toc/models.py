from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class DangKhuonMat(models.Model):
    CAC_DANG_MAT = [
        ("Heart", "Mặt trái tim"),
        ("Oblong", "Mặt dài"),
        ("Oval", "Mặt trái xoan"),
        ("Round", "Mặt tròn"),
        ("Square", "Mặt vuông"),
    ]

    ma = models.CharField(
        "Dạng khuôn mặt",
        max_length=20,
        choices=CAC_DANG_MAT,
        unique=True,
    )

    class Meta:
        verbose_name = "Dạng khuôn mặt"
        verbose_name_plural = "Dạng khuôn mặt"

    def __str__(self):
        return self.get_ma_display()


class NguoiNoiTieng(models.Model):
    ten = models.CharField(
        "Tên người nổi tiếng",
        max_length=150,
        db_index=True,
    )

    ten_khac = models.TextField(
        "Tên gọi khác",
        blank=True,
        help_text="Mỗi tên gọi hoặc nghệ danh khác ghi trên một dòng.",
    )

    anh_dai_dien = models.ImageField(
        "Ảnh đại diện",
        upload_to="nguoi_noi_tieng/anh_dai_dien/",
        blank=True,
    )

    thu_tu = models.PositiveIntegerField(
        "Thứ tự hiển thị",
        default=0,
    )

    hien_thi = models.BooleanField(
        "Hiển thị trên website",
        default=True,
    )

    ngay_tao = models.DateTimeField(
        "Ngày tạo",
        auto_now_add=True,
    )

    ngay_cap_nhat = models.DateTimeField(
        "Ngày cập nhật",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Người nổi tiếng"
        verbose_name_plural = "Người nổi tiếng"
        ordering = ["thu_tu", "ten", "pk"]

    def __str__(self):
        return self.ten


class KieuToc(models.Model):
    ten = models.CharField(
        "Tên kiểu tóc",
        max_length=150,
    )

    mo_ta = models.TextField("Mô tả")

    anh_gioi_thieu = models.ImageField(
        "Ảnh giới thiệu",
        upload_to="kieu_toc/anh_gioi_thieu/",
    )

    anh_thu_toc = models.ImageField(
        "Ảnh tóc nền trong suốt",
        upload_to="kieu_toc/anh_thu_toc/",
        blank=True,
        help_text=(
            "PNG chỉ chứa tóc và có nền trong suốt. "
            "Có thể bổ sung sau."
        ),
    )

    dang_mat_phu_hop = models.ManyToManyField(
        DangKhuonMat,
        verbose_name="Dạng khuôn mặt phù hợp",
        related_name="cac_kieu_toc",
        blank=True,
        help_text=(
            "Có thể để trống với tóc người nổi tiếng hoặc tóc phá cách. "
            "Chỉ tóc được liên kết dạng mặt mới được gợi ý theo dạng mặt đó."
        ),
    )

    nguoi_noi_tieng = models.ForeignKey(
        NguoiNoiTieng,
        verbose_name="Người nổi tiếng",
        on_delete=models.SET_NULL,
        related_name="cac_kieu_toc",
        null=True,
        blank=True,
        help_text="Để trống nếu đây là kiểu tóc thông thường.",
    )

    hien_thi_pha_cach = models.BooleanField(
        "Cho phép xuất hiện trong Phá cách",
        default=True,
        help_text=(
            "Khi mục Phá cách được triển khai, tóc này có thể xuất hiện "
            "nếu đang hiển thị và đã có ảnh thử tóc."
        ),
    )

    diem_neo_x = models.FloatField(
        "Điểm neo ngang trên ảnh tóc",
        default=0.5,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
        help_text="Từ 0 đến 1: mép trái là 0, mép phải là 1.",
    )

    diem_neo_y = models.FloatField(
        "Điểm neo dọc trên ảnh tóc",
        default=0.65,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
        help_text="Từ 0 đến 1: mép trên là 0, mép dưới là 1.",
    )

    ti_le_chieu_rong = models.FloatField(
        "Tỷ lệ chiều rộng tóc so với mặt",
        default=1.3,
        validators=[
            MinValueValidator(0.1),
            MaxValueValidator(5),
        ],
        help_text="Ví dụ 1,3 nghĩa là ảnh tóc rộng bằng 1,3 lần mặt.",
    )

    do_lech_x = models.FloatField(
        "Độ lệch ngang",
        default=0,
        validators=[
            MinValueValidator(-2),
            MaxValueValidator(2),
        ],
        help_text="Theo chiều rộng mặt: âm sang trái, dương sang phải.",
    )

    do_lech_y = models.FloatField(
        "Độ lệch dọc",
        default=0,
        validators=[
            MinValueValidator(-2),
            MaxValueValidator(2),
        ],
        help_text="Theo chiều cao mặt: âm lên trên, dương xuống dưới.",
    )

    thu_tu = models.PositiveIntegerField(
        "Thứ tự hiển thị",
        default=0,
        help_text="Số nhỏ hiển thị trước.",
    )

    hien_thi = models.BooleanField(
        "Hiển thị trên website",
        default=True,
    )

    ngay_tao = models.DateTimeField(
        "Ngày tạo",
        auto_now_add=True,
    )

    ngay_cap_nhat = models.DateTimeField(
        "Ngày cập nhật",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Kiểu tóc"
        verbose_name_plural = "Kiểu tóc"
        ordering = ["thu_tu", "ten", "pk"]

    def __str__(self):
        return self.ten


class KieuTocYeuThich(models.Model):
    tai_khoan = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cac_toc_yeu_thich",
        verbose_name="Tài khoản",
    )

    kieu_toc = models.ForeignKey(
        KieuToc,
        on_delete=models.CASCADE,
        related_name="cac_luot_yeu_thich",
        verbose_name="Kiểu tóc",
    )

    ngay_luu = models.DateTimeField(
        "Ngày lưu",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Kiểu tóc yêu thích"
        verbose_name_plural = "Kiểu tóc yêu thích"
        ordering = ["-ngay_luu"]
        constraints = [
            models.UniqueConstraint(
                fields=["tai_khoan", "kieu_toc"],
                name="moi_tai_khoan_luu_mot_kieu_toc",
            ),
        ]

    def __str__(self):
        return f"{self.tai_khoan} — {self.kieu_toc}"


class TacVuTachToc(models.Model):
    class TrangThai(models.TextChoices):
        CHO_XU_LY = "cho_xu_ly", "Chờ xử lý"
        DANG_XU_LY = "dang_xu_ly", "Đang xử lý"
        HOAN_TAT = "hoan_tat", "Hoàn tất"
        THAT_BAI = "that_bai", "Thất bại"

    nguoi_noi_tieng = models.ForeignKey(
        NguoiNoiTieng,
        verbose_name="Người nổi tiếng",
        on_delete=models.PROTECT,
        related_name="cac_tac_vu_tach_toc",
    )

    ten_kieu_toc = models.CharField(
        "Tên kiểu tóc",
        max_length=150,
    )

    anh_goc = models.ImageField(
        "Ảnh gốc",
        upload_to="nguoi_noi_tieng/anh_goc/",
    )

    kieu_toc = models.ForeignKey(
        KieuToc,
        verbose_name="Kiểu tóc nhận kết quả",
        on_delete=models.SET_NULL,
        related_name="cac_tac_vu_tach_toc",
        null=True,
        blank=True,
        help_text=(
            "Ảnh PNG và thông số ghép được lưu trong kiểu tóc này "
            "sau khi xử lý thành công."
        ),
    )

    trang_thai = models.CharField(
        "Trạng thái",
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.CHO_XU_LY,
        db_index=True,
    )

    buoc_hien_tai = models.CharField(
        "Bước hiện tại",
        max_length=150,
        blank=True,
    )

    thong_bao_loi = models.TextField(
        "Thông báo lỗi",
        blank=True,
    )

    so_lan_xu_ly = models.PositiveIntegerField(
        "Số lần xử lý",
        default=0,
    )

    ma_phien_xu_ly = models.UUIDField(
        "Mã phiên xử lý",
        null=True,
        blank=True,
        editable=False,
        help_text="Dùng để ngăn phiên xử lý cũ ghi đè kết quả mới.",
    )

    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người tạo",
        on_delete=models.SET_NULL,
        related_name="cac_tac_vu_tach_toc",
        null=True,
        blank=True,
    )

    bat_dau_luc = models.DateTimeField(
        "Bắt đầu lúc",
        null=True,
        blank=True,
    )

    ket_thuc_luc = models.DateTimeField(
        "Kết thúc lúc",
        null=True,
        blank=True,
    )

    ngay_tao = models.DateTimeField(
        "Ngày tạo",
        auto_now_add=True,
    )

    ngay_cap_nhat = models.DateTimeField(
        "Ngày cập nhật",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Tác vụ tách tóc"
        verbose_name_plural = "Tác vụ tách tóc"
        ordering = ["-ngay_tao", "-pk"]
        indexes = [
            models.Index(
                fields=["trang_thai", "ngay_tao"],
                name="tach_toc_hang_doi",
            ),
        ]

    def __str__(self):
        return f"{self.nguoi_noi_tieng} — {self.ten_kieu_toc}"