"""Nạp AI trong tiến trình phục vụ web trước khi mở cổng HTTP."""

from time import perf_counter

from django.contrib.staticfiles.management.commands.runserver import (
    Command as RunserverCommand,
)
from django.core.management.base import CommandError


class Command(RunserverCommand):
    help = "Khởi động web sau khi AI local đã nạp và chạy thử thành công."

    def inner_run(self, *args, **options):
        from thu_toc.ket_noi_colab import kiem_tra_colab

        self.stdout.write(
            "Đang nạp và chạy thử AI local trước khi mở website…"
        )
        started = perf_counter()

        try:
            result = kiem_tra_colab()
        except Exception as error:
            raise CommandError(
                "Chưa mở website vì không chuẩn bị được AI: "
                + str(error)
            ) from error

        if (
            not isinstance(result, dict)
            or result.get("thanh_cong") is not True
            or result.get("san_sang") is not True
        ):
            raise CommandError(
                "Chưa mở website vì AI chưa sẵn sàng."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"AI đã sẵn sàng sau "
                f"{perf_counter() - started:.1f} giây. "
                "Giữ model trong RAM cho các lượt quét."
            )
        )

        return super().inner_run(*args, **options)