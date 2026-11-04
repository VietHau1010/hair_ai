import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from kieu_toc.models import TacVuTachToc


class Command(BaseCommand):
    help = "Xử lý hàng đợi tách tóc người nổi tiếng."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mot-lan",
            action="store_true",
            help="Xử lý tối đa một tác vụ rồi thoát.",
        )

        parser.add_argument(
            "--ma",
            type=int,
            help="Chỉ xử lý một tác vụ đang chờ theo mã.",
        )

    def handle(self, *args, **options):
        # Import tại đây để các lệnh Django khác không phải tải MediaPipe.
        from thu_toc.xu_ly_tach_toc import BoXuLyTachToc

        ma = options["ma"]
        mot_lan = options["mot_lan"] or ma is not None

        if ma is not None:
            if not TacVuTachToc.objects.filter(pk=ma).exists():
                raise CommandError(f"Không có tác vụ mã {ma}.")

        bo_xu_ly = BoXuLyTachToc()

        self.stdout.write(
            "Hàng đợi tách tóc đang chạy. Nhấn Ctrl+C để dừng."
        )

        try:
            while True:
                close_old_connections()

                tac_vu = bo_xu_ly.nhan_tac_vu(ma=ma)

                if tac_vu is None:
                    if mot_lan:
                        self.stdout.write(
                            "Không có tác vụ đang chờ phù hợp."
                        )
                        break

                    time.sleep(2)
                    continue

                self.stdout.write(
                    f"Đang xử lý #{tac_vu.pk}: "
                    f"{tac_vu.nguoi_noi_tieng.ten} — "
                    f"{tac_vu.ten_kieu_toc}"
                )

                try:
                    toc = bo_xu_ly.xu_ly(tac_vu)

                except Exception as loi:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Tác vụ #{tac_vu.pk} thất bại: {loi}"
                        )
                    )

                    if mot_lan:
                        raise CommandError(
                            "Chưa xử lý thành công tác vụ."
                        ) from loi

                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Hoàn tất #{tac_vu.pk}. "
                            f"Đã tạo kiểu tóc mã {toc.pk}."
                        )
                    )

                if mot_lan:
                    break

        except KeyboardInterrupt:
            self.stdout.write("\nĐã dừng hàng đợi.")

        finally:
            bo_xu_ly.close()
            close_old_connections()




            