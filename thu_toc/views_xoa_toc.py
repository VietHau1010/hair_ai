"""API xóa tóc camera; giữ nguyên giao thức POST/GET của giao diện."""
import atexit
import base64
import json
import logging
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

nhat_ky = logging.getLogger(__name__)
_cac_tac_vu = {}
_khoa = threading.Lock()
_tac_vu_dang_chay = None
_tien_trinh = None
_tep_log = None

_MA_XU_LY = r'''
import json
import sys
import traceback
import warnings
from pathlib import Path

# Giữ stdout rảnh cho log; kết quả trao đổi qua tệp JSON ghi atomically.
import numpy as np
from PIL import Image, ImageOps
from thu_toc.xoa_toc import xoa_toc, LoiXoaToc

for line in sys.stdin:
    folder = None
    try:
        request_data = json.loads(line)
        folder = Path(request_data['folder'])
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(folder / 'input.jpg') as image:
                if min(image.size) < 128 or image.width*image.height > 20_000_000:
                    raise LoiXoaToc('Vùng đầu quá nhỏ hoặc kích thước ảnh quá lớn.')
                rgb = np.array(ImageOps.exif_transpose(image).convert('RGB'))
        result = xoa_toc(rgb, stream_id=request_data.get('stream_id'))
        if not result['chap_nhan']:
            raise LoiXoaToc(result['thong_bao'])
        # RGB chưa hòa + alpha mềm: trình duyệt hòa đúng một lần với camera.
        rgba = np.dstack((result['anh'], result['mat_na'].astype(np.uint8)))
        Image.fromarray(rgba).save(folder / 'result.png', format='PNG')
        data = {'thanh_cong': True, 'landmarks': result['landmarks'], 'giay': result['giay']}
    except Exception as exc:
        traceback.print_exc()
        data = {'thanh_cong': False, 'thong_bao': type(exc).__name__ + ': ' + str(exc)[:600]}
    if folder is not None:
        pending = folder / 'result.pending'
        pending.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        pending.replace(folder / 'result.json')
'''


def _thu_muc_ai():
    root = Path(settings.BASE_DIR) / 'tai_nguyen' / 'stable_hair_bald'
    (root / 'temp').mkdir(parents=True, exist_ok=True)
    (root / 'logs').mkdir(parents=True, exist_ok=True)
    return root


def _dong_tien_trinh():
    global _tien_trinh, _tep_log
    process, _tien_trinh = _tien_trinh, None
    if process is not None:
        if process.poll() is None:
            # Khi hủy/timeout, dừng cả worker CUDA con trên Windows.
            if os.name == 'nt':
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=15, check=False,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if process.stdin:
            process.stdin.close()
    if _tep_log is not None:
        _tep_log.close()
        _tep_log = None


atexit.register(_dong_tien_trinh)


def _lay_tien_trinh():
    global _tien_trinh, _tep_log
    if _tien_trinh is not None and _tien_trinh.poll() is None:
        return _tien_trinh
    _dong_tien_trinh()
    root = _thu_muc_ai()
    env = os.environ.copy()
    env.update({
        'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
        'TEMP': str(root / 'temp'), 'TMP': str(root / 'temp'),
        'USE_TF': '0',
    })
    _tep_log = (root / 'logs' / 'camera_worker.log').open('ab', buffering=0)
    try:
        _tien_trinh = subprocess.Popen(
            [sys.executable, '-X', 'utf8', '-u', '-c', _MA_XU_LY],
            cwd=str(settings.BASE_DIR), env=env,
            stdin=subprocess.PIPE, stdout=_tep_log, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', bufsize=1,
        )
    except Exception:
        _tep_log.close()
        _tep_log = None
        raise
    return _tien_trinh


def _xu_ly_tac_vu(ma_tac_vu, noi_dung_anh, stream_id):
    global _tac_vu_dang_chay
    ket_qua = {'trang_thai': 'loi', 'thong_bao': 'Không xử lý được tóc.'}
    try:
        root = _thu_muc_ai()
        with tempfile.TemporaryDirectory(prefix='camera_', dir=str(root / 'temp')) as name:
            folder = Path(name)
            (folder / 'input.jpg').write_bytes(noi_dung_anh)
            process = _lay_tien_trinh()
            process.stdin.write(json.dumps({'folder': str(folder), 'stream_id': stream_id}) + '\n')
            process.stdin.flush()
            deadline = time.monotonic() + 1200
            result_file = folder / 'result.json'
            while not result_file.is_file():
                if process.poll() is not None:
                    raise RuntimeError('Worker AI đã dừng. Xem tai_nguyen/stable_hair_bald/logs/camera_worker.log.')
                if time.monotonic() > deadline:
                    _dong_tien_trinh()
                    raise TimeoutError('AI xử lý quá 20 phút. Xem camera_worker.log.')
                time.sleep(0.025)
            data = json.loads(result_file.read_text(encoding='utf-8'))
            if not data.get('thanh_cong'):
                raise RuntimeError(data.get('thong_bao') or 'Không tạo được ảnh đầu trọc.')
            png = (folder / 'result.png').read_bytes()
            ket_qua = {
                'trang_thai': 'xong',
                'anh': 'data:image/png;base64,' + base64.b64encode(png).decode('ascii'),
                'landmarks': data['landmarks'], 'giay': data['giay'],
            }
    except Exception as exc:
        nhat_ky.exception('AI xóa tóc: %s', exc)
        ket_qua['thong_bao'] = str(exc)[:800]
    finally:
        with _khoa:
            if ma_tac_vu in _cac_tac_vu:
                _cac_tac_vu[ma_tac_vu].update(ket_qua, hoan_tat_luc=time.monotonic())
            if _tac_vu_dang_chay == ma_tac_vu:
                _tac_vu_dang_chay = None


@require_http_methods(['GET', 'POST'])
def xoa_toc_camera(request):
    global _tac_vu_dang_chay
    if not request.user.is_authenticated:
        return JsonResponse({'thanh_cong': False, 'thong_bao': 'Vui lòng đăng nhập lại.'}, status=401)
    now = time.monotonic()
    with _khoa:
        for key, job in list(_cac_tac_vu.items()):
            completed = job.get('hoan_tat_luc')
            if completed and now - completed > 20:
                del _cac_tac_vu[key]
    with _khoa:
        completed_jobs = sorted(
            ((key, value.get('hoan_tat_luc', 0)) for key,value in _cac_tac_vu.items()
             if value.get('hoan_tat_luc')), key=lambda item:item[1])
        for expired,_ in completed_jobs[:-12]:
            _cac_tac_vu.pop(expired, None)
    if request.method == 'GET':
        with _khoa:
            job = _cac_tac_vu.get(request.GET.get('id', ''))
            if not job or job['chu_so_huu'] != str(request.user.pk):
                return JsonResponse({'thanh_cong': False, 'thong_bao': 'Tác vụ hết hạn hoặc server đã khởi động lại.'}, status=404)
            data = {k: v for k, v in job.items() if k not in {'chu_so_huu', 'hoan_tat_luc'}}
        response = JsonResponse({'thanh_cong': True, **data}, json_dumps_params={'ensure_ascii': False})
        response['Cache-Control'] = 'no-store'
        return response
    session = request.POST.get('session', '')
    if len(session) > 64 or not all(c.isalnum() or c in '-_' for c in session):
        return JsonResponse({'thanh_cong': False, 'thong_bao': 'Phiên camera không hợp lệ.'}, status=400)
    stream_id = str(request.user.pk) + ':' + session if session else None
    image = request.FILES.get('anh')
    if not image or image.size > 8*1024*1024:
        return JsonResponse({'thanh_cong': False, 'thong_bao': 'Chưa nhận được ảnh hoặc ảnh vượt 8 MB.'}, status=400)
    with _khoa:
        if _tac_vu_dang_chay is not None:
            return JsonResponse({'thanh_cong': False, 'thong_bao': 'AI đang xử lý người trước.'}, status=429)
        key = secrets.token_urlsafe(24)
        _tac_vu_dang_chay = key
        _cac_tac_vu[key] = {'chu_so_huu': str(request.user.pk), 'trang_thai': 'dang_chay'}
    try:
        payload = image.read()
        threading.Thread(target=_xu_ly_tac_vu, args=(key, payload, stream_id), daemon=True).start()
    except Exception:
        with _khoa:
            _cac_tac_vu.pop(key, None)
            _tac_vu_dang_chay = None
        nhat_ky.exception('Không tạo được tác vụ xóa tóc')
        return JsonResponse({'thanh_cong': False, 'thong_bao': 'Không tạo được tác vụ AI.'}, status=503)
    return JsonResponse({'thanh_cong': True, 'id': key, 'trang_thai': 'dang_chay'}, status=202)
