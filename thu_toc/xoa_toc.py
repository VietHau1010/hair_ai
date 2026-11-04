"""Stable-Hair stage1 adapter cho camera Django.

Nguồn: https://github.com/Xiaojiu-z/Stable-Hair (Apache-2.0).

Giữ nguyên thông tin giấy phép trong mã nguồn tải về.

"""
import argparse
import atexit
import gc
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
ROOT = Path(__file__).resolve().parent.parent
HOME_AI = ROOT / 'tai_nguyen' / 'stable_hair_bald'
BASE = HOME_AI / 'sd15'
REPO = HOME_AI / 'source'
WEIGHT = HOME_AI / 'stage1' / 'pytorch_model.bin'
FACE = ROOT / 'tai_nguyen' / 'ai_khuon_mat' / 'face_landmarker.task'
HAIR = ROOT / 'tai_nguyen' / 'ai_xoa_toc' / 'selfie_multiclass_256x256.tflite'
WORKER_PY = ROOT / '.venv_xoa_toc' / 'Scripts' / 'python.exe'
COMMIT = '5d52249de8430a07a04a9f14a577925f26c422d7'
DRIVE = 'https://drive.google.com/drive/folders/1E-8Udfw8S8IorCWhBgS4FajIbqlrWRbQ'
MODEL_ID = 'stable-diffusion-v1-5/stable-diffusion-v1-5'
MODEL_REVISION = '451f4fe16113bff5a5d2269ed5ad43b0592e9a14'
CFG = {'steps': 30, 'scales': [0.9, 1.0], 'seed': 42, 'hair_threshold': 0.45, 'max_residual': 0.1, 'timeout': 1200, 'max_side': 1280}
FILES = {'utils/pipeline_cn.py': '66c6b1bcb118c1670c5c4715181e1102b1f59f2f4c2ba2e921d0912247e468c7', 'ref_encoder/latent_controlnet.py': '7602a031029113f6d7d75f0f1bd4d7b9a1497efcae1843cd65454d8578935ec5', 'LICENSE': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4'}

class LoiXoaToc(RuntimeError):
    pass

def configure():
    """UTF-8 và các thư mục cache/tạm trong dự án."""
    for stream in (sys.stdout, sys.stderr):
        if callable(getattr(stream, 'reconfigure', None)):
            try:
                stream.reconfigure(encoding='utf-8', errors='backslashreplace')
            except (OSError, ValueError):
                pass
    cache = HOME_AI / 'cache'
    temp = HOME_AI / 'temp'
    cache.mkdir(parents=True, exist_ok=True)
    temp.mkdir(parents=True, exist_ok=True)
    os.environ.update({'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8:backslashreplace', 'HF_HOME': str(cache), 'HF_HUB_CACHE': str(cache / 'hub'), 'TORCH_HOME': str(cache / 'torch'), 'XDG_CACHE_HOME': str(cache), 'TEMP': str(temp), 'TMP': str(temp), 'USE_TF': '0', 'PIP_CACHE_DIR': str(cache / 'pip')})
    tempfile.tempdir = str(temp)

def log(message):
    """Thông báo xử lý đi qua stderr, không phá giao thức worker."""
    try:
        print(message, file=sys.stderr, flush=True)
    except (OSError, UnicodeError, ValueError):
        pass

def tai_model():
    """Tải mã nguồn chính thức, SD1.5 và checkpoint Bald Converter."""
    configure()
    for relative, expected in FILES.items():
        target = REPO / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        url = f'https://raw.githubusercontent.com/Xiaojiu-z/Stable-Hair/{COMMIT}/{relative}'
        log(f'Downloading source: {relative}')
        data = urllib.request.urlopen(url, timeout=120).read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise LoiXoaToc(f'Source checksum mismatch: {relative}')
        target.write_bytes(data)
    for folder in ('utils', 'ref_encoder'):
        (REPO / folder / '__init__.py').touch()
    from huggingface_hub import snapshot_download
    log('Downloading SD 1.5 base. This is NOT the old inpainting model.')
    snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=str(BASE), cache_dir=str(HOME_AI / 'cache' / 'hub'), allow_patterns=['model_index.json', 'scheduler/*', 'tokenizer/*', 'unet/config.json', 'unet/*.fp16.safetensors', 'vae/config.json', 'vae/*.fp16.safetensors', 'text_encoder/config.json', 'text_encoder/*.fp16.safetensors'])
    WEIGHT.parent.mkdir(parents=True, exist_ok=True)
    if not WEIGHT.is_file():
        gdown = importlib.import_module('gdown')
        log('Downloading official stage1 checkpoint only.')
        part = WEIGHT.with_suffix('.part')
        downloaded = gdown.download(id='1oYNoKPEN0mZpRhZ7s3_xSDlaO209vFn4', output=str(part), quiet=False, use_cookies=False, resume=True)
        if not downloaded or part.stat().st_size < 1000000:
            raise LoiXoaToc("Checkpoint download incomplete. Download stage1/pytorch_model.bin from the authors' Drive to the stage1 folder.")
        part.replace(WEIGHT)
    log(f'Setup complete: {HOME_AI}')

def make_pipeline():
    """Nạp đúng Latent ControlNet và pipeline stage1 của Stable-Hair."""
    configure()
    import torch
    if not torch.cuda.is_available():
        raise LoiXoaToc('Worker CUDA is unavailable. Check .venv_xoa_toc.')
    sys.path.insert(0, str(REPO))
    from diffusers import UNet2DConditionModel, UniPCMultistepScheduler
    ControlNetModel = importlib.import_module('ref_encoder.latent_controlnet').ControlNetModel
    spec = importlib.util.spec_from_file_location('haulong_pipeline_cn', REPO / 'utils' / 'pipeline_cn.py')
    if spec is None or spec.loader is None:
        raise LoiXoaToc('Không nạp được pipeline Stable-Hair trên máy.')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    log('Loading official Stable-Hair Bald Converter...')
    unet = UNet2DConditionModel.from_pretrained(str(BASE), subfolder='unet', variant='fp16', torch_dtype=torch.float16, use_safetensors=True, local_files_only=True)
    if unet.config.in_channels != 4:
        raise LoiXoaToc('Wrong base: Bald Converter requires SD1.5 with 4 input channels.')
    control = ControlNetModel.from_unet(unet).to(dtype=torch.float16)
    state = torch.load(str(WEIGHT), map_location='cpu', weights_only=True)
    if 'state_dict' in state:
        state = state['state_dict']
    control.load_state_dict(state, strict=True)
    del state, unet
    gc.collect()
    pipe = module.StableDiffusionControlNetPipeline.from_pretrained(str(BASE), controlnet=control, safety_checker=None, feature_extractor=None, requires_safety_checker=False, variant='fp16', torch_dtype=torch.float16, use_safetensors=True, local_files_only=True, low_cpu_mem_usage=True)
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
    pipe.set_progress_bar_config(disable=True)
    pipe.enable_vae_slicing()
    pipe.enable_vae_tiling()
    pipe.enable_sequential_cpu_offload(gpu_id=0)
    log('Ready: ' + torch.cuda.get_device_name(0))
    return pipe

def worker():
    """Tiến trình riêng giữ model để dùng lại cho các yêu cầu sau."""
    configure()
    protocol = sys.stdout
    sys.stdout = sys.stderr
    import torch
    from PIL import Image

    def reply(value):
        protocol.write(json.dumps(value, ensure_ascii=True) + '\n')
        protocol.flush()
    try:
        pipe = make_pipeline()
        reply({'ready': True})
    except Exception:
        traceback.print_exc()
        reply({'error': traceback.format_exc()})
        return
    for line in sys.stdin:
        try:
            request = json.loads(line)
            torch.manual_seed(int(request['seed']))
            torch.cuda.manual_seed_all(int(request['seed']))
            with Image.open(request['input']) as opened:
                image = opened.convert('RGB')
            with torch.inference_mode():
                result = pipe(prompt='', negative_prompt='', image=image, width=512, height=512, num_inference_steps=CFG['steps'], guidance_scale=1.5, controlnet_conditioning_scale=float(request['scale']), generator=torch.Generator(device='cpu').manual_seed(int(request['seed'])))
            result.images[0].save(request['output'])
            reply({'ok': True})
            del result
        except Exception:
            traceback.print_exc()
            torch.cuda.empty_cache()
            reply({'error': traceback.format_exc()})

class WorkerClient:

    def __init__(self):
        self.process = None
        self.responses = queue.Queue()
        self.logfile = None

    def _read(self, process, responses):
        try:
            for line in process.stdout:
                try:
                    responses.put(json.loads(line))
                except json.JSONDecodeError:
                    log('Worker output: ' + line.strip())
        except (OSError, ValueError):
            pass
        finally:
            responses.put({'error': 'Worker stopped. Read worker.log.'})

    def receive(self):
        try:
            response = self.responses.get(timeout=CFG['timeout'])
        except queue.Empty:
            self.close()
            raise LoiXoaToc('Xử lý quá thời gian. Xem tai_nguyen/stable_hair_bald/worker.log.') from None
        if 'error' in response:
            message = response['error'][-1800:]
            self.close()
            raise LoiXoaToc('Stable-Hair lỗi: ' + message)
        return response

    def start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.close()
        if not WORKER_PY.is_file():
            raise LoiXoaToc('Chưa tạo môi trường .venv_xoa_toc bằng Python 3.11.')
        if not WEIGHT.is_file() or not (BASE / 'model_index.json').is_file():
            raise LoiXoaToc('Thiếu model Stable-Hair. Chạy --tai-model bằng .venv_xoa_toc.')
        self.responses = queue.Queue()
        self.logfile = (HOME_AI / 'worker.log').open('a', encoding='utf-8')
        self.process = subprocess.Popen([str(WORKER_PY), '-X', 'utf8', str(Path(__file__).resolve()), '--worker'], cwd=str(ROOT), env=os.environ.copy(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.logfile, text=True, encoding='utf-8', errors='replace', bufsize=1, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        threading.Thread(target=self._read, args=(self.process, self.responses), daemon=True).start()
        try:
            self.receive()
        except Exception:
            self.close()
            raise

    def generate(self, image, scale, seed):
        self.start()
        from PIL import Image
        import numpy as np
        with tempfile.TemporaryDirectory(prefix='bald_') as temp:
            src = Path(temp) / 'input.png'
            dst = Path(temp) / 'output.png'
            Image.fromarray(image).save(src)
            request = {'input': str(src), 'output': str(dst), 'scale': scale, 'seed': seed}
            try:
                self.process.stdin.write(json.dumps(request) + '\n')
                self.process.stdin.flush()
                self.receive()
                with Image.open(dst) as result:
                    return np.asarray(result.convert('RGB')).copy()
            except (BrokenPipeError, OSError) as exc:
                self.close()
                raise LoiXoaToc('Worker bị dừng. Xem worker.log.') from exc

    def close(self):
        if self.process is not None:
            proc = self.process
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            for stream in (proc.stdin, proc.stdout):
                if stream:
                    stream.close()
            self.process = None
        if self.logfile:
            self.logfile.close()
            self.logfile = None

def align_head(image, pts, hair_mask=None):
    """Căn chỉnh kiểu FFHQ từ mắt/miệng bằng affine đảo ngược được."""
    import cv2
    import numpy as np
    left, right = sorted(((pts[33] + pts[133]) / 2, (pts[263] + pts[362]) / 2), key=lambda p: p[0])
    middle = (left + right) / 2
    eye = right - left
    mouth = (pts[61] + pts[291]) / 2
    toward_mouth = mouth - middle
    axis = eye - np.array([-toward_mouth[1], toward_mouth[0]])
    norm = float(np.linalg.norm(axis))
    if norm < 1 or np.linalg.norm(eye) < 25:
        raise LoiXoaToc('Mặt quá nhỏ. Tiến gần camera và nhìn thẳng.')
    direction = axis / norm
    perpendicular = np.array([-direction[1], direction[0]])
    half_size = max(float(np.linalg.norm(eye)) * 2, float(np.linalg.norm(toward_mouth)) * 1.8)
    center = middle + toward_mouth * 0.1
    if hair_mask is not None:
        if hair_mask.shape != image.shape[:2]:
            raise LoiXoaToc('Kích thước mặt nạ tóc không khớp ảnh camera.')
        yy, xx = np.nonzero(hair_mask)
        if len(xx):
            delta = np.column_stack((xx, yy)).astype(np.float64) - center
            extent = max(float(np.abs(delta @ direction).max()), float(np.abs(delta @ perpendicular).max()))
            padding = max(12.0, float(np.linalg.norm(eye)) * 0.12)
            half_size = max(half_size, extent + padding)
    axis = direction * half_size
    vertical = perpendicular * half_size
    corners = np.float32([center - axis - vertical, center + axis - vertical, center - axis + vertical])
    matrix = cv2.getAffineTransform(corners, np.float32([[0, 0], [511, 0], [0, 511]]))
    crop = cv2.warpAffine(image, matrix, (512, 512), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return (crop, matrix)

def make_mask(prob, pts):
    """Lấy vùng tóc liên quan đến đầu và tạo biên ghép mềm."""
    import cv2
    import numpy as np
    if not np.isfinite(prob).all() or not np.isfinite(pts).all():
        raise LoiXoaToc('Dữ liệu phân vùng tóc không hợp lệ.')
    h, w = prob.shape
    a, b = sorted((pts[33], pts[263]), key=lambda p: p[0])
    distance = float(np.linalg.norm(b - a))
    if distance < 25:
        raise LoiXoaToc('Mặt quá nhỏ để tách tóc.')
    ex = (b - a) / distance
    ey = np.array([-ex[1], ex[0]])
    center = (a + b) / 2
    yy, xx = np.mgrid[:h, :w]
    dx = xx - center[0]
    dy = yy - center[1]
    u = (dx * ex[0] + dy * ex[1]) / distance
    v = (dx * ey[0] + dy * ey[1]) / distance
    seed = (abs(u) < 1.1) & (v > -1.8) & (v < -0.12)
    binary = (prob >= CFG['hair_threshold']).astype('uint8')
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    hair = np.zeros((h, w), 'uint8')
    minimum = max(15, round(distance * distance * 0.006))
    selected = []
    for idx in range(1, count):
        component = labels == idx
        overlap = int(np.count_nonzero(component & seed))
        if stats[idx, cv2.CC_STAT_AREA] >= minimum and overlap >= minimum:
            selected.append((idx, overlap))
    if not selected:
        raise LoiXoaToc('Chưa nhận diện rõ tóc. Nhìn thẳng và tăng ánh sáng trước mặt.')
    principal = max(selected, key=lambda item: item[1])[0]
    hair[labels == principal] = 255
    for idx, overlap in selected:
        if idx != principal and overlap >= minimum * 2:
            hair[labels == idx] = 255
    if np.count_nonzero(hair) > h * w * 0.55:
        raise LoiXoaToc('Phân vùng đang lẫn tóc với nền. Cần nền tương phản hơn.')
    band = max(1, round(distance * 0.015))
    edges = [np.any(hair[:band] > 0, axis=0), np.any(hair[-band:] > 0, axis=0), np.any(hair[:, :band] > 0, axis=1), np.any(hair[:, -band:] > 0, axis=1)]

    def longest_run(edge):
        padded = np.pad(edge.astype('int8'), (1, 1))
        transitions = np.diff(padded)
        starts = np.flatnonzero(transitions == 1)
        ends = np.flatnonzero(transitions == -1)
        return int(np.max(ends - starts)) if len(starts) else 0
    significant = max(5, round(distance * 0.1))
    if any((longest_run(edge) >= significant for edge in edges)):
        raise LoiXoaToc('Vùng tóc sát mép ảnh camera. Lùi nhẹ để thấy trọn đầu; nếu vẫn báo lỗi cần mở rộng vùng ảnh giao diện gửi lên.')
    close_radius = max(1, round(distance * 0.015))
    hair = cv2.morphologyEx(hair, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
            (close_radius*2+1, close_radius*2+1)))
    protected = np.zeros_like(hair)
    contour = [70, 63, 105, 66, 107, 9, 336, 296, 334, 293, 300, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127]
    cv2.fillPoly(protected, [pts[contour].astype('int32')], 255)
    radius = max(3, round(distance * 0.08))
    expanded = cv2.dilate(hair, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1)))
    expanded[protected > 0] = 0
    original = (hair > 0) & (protected == 0)
    if np.count_nonzero(original) < 30:
        raise LoiXoaToc('Vùng tóc quá ít hoặc bị che khuất.')
    alpha = cv2.GaussianBlur(expanded.astype('float32') / 255, (0, 0), max(0.8, distance * 0.012))
    alpha[original] = 1.0
    alpha[protected > 0] = 0
    alpha[alpha < 0.01] = 0
    return (hair, alpha, protected)

def restore_background(source, unknown, channels, protected, distance):
    """Ước lượng nền chưa quan sát từ nền hiện có, không dùng da/áo làm mẫu."""
    import cv2
    import numpy as np
    h, w = unknown.shape
    if not np.any(unknown):
        return source.astype(np.float32).copy()
    bg = channels[0]
    other = np.maximum.reduce(channels[1:])
    # Vẫn phải là lớp nền thắng rõ; không dùng màu tối để xác định tóc/nền.
    safe = (bg >= 0.60) & (bg-other >= 0.20) & (protected == 0) & ~unknown
    safe = cv2.erode(safe.astype(np.uint8), np.ones((3,3),np.uint8)) > 0
    samples = np.zeros((h,w), bool)
    # Dải 7 pixel cũ quá hẹp và thường hoàn toàn nằm trong mép chưa chắc chắn.
    for fraction in (0.10, 0.22, 0.45, 0.85, 1.5):
        r = max(5, round(distance*fraction))
        local = cv2.dilate(unknown.astype(np.uint8),
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r*2+1,r*2+1))) > 0
        samples = local & safe
        if np.count_nonzero(samples) >= 50:
            break
    if np.count_nonzero(samples) < 8:
        # Toàn khung không có mẫu nền đáng tin thì không có dữ liệu để lấp.
        raise LoiXoaToc('Không tìm được vùng nền nhìn thấy đủ tin cậy để khôi phục tóc ngoài đầu.')
    colors = source[samples].astype(np.float32)
    center = np.median(colors, axis=0)
    deviation = np.linalg.norm(colors-center,axis=1)
    # Fit trên cụm màu nền chính để tránh một vật thể lẻ làm lệch màu tường.
    keep = deviation <= max(8.0, float(np.percentile(deviation,85)))
    y, x = np.nonzero(samples)
    x, y, colors = x[keep], y[keep], colors[keep]
    result = source.astype(np.float32).copy()
    variation = float(np.percentile(np.linalg.norm(colors-np.median(colors,axis=0),axis=1),85))
    if len(colors) >= 8 and variation <= 30:
        # Nền đơn giản: bảo toàn chuyển sáng thay vì tô một màu cố định.
        A = np.column_stack((np.ones(len(x)), x/w, y/h))
        penalty = np.diag([0., 0.05, 0.05])
        coeff = np.linalg.solve(A.T@A + penalty + np.eye(3)*1e-6, A.T@colors)
        uy, ux = np.nonzero(unknown)
        predicted = np.column_stack((np.ones(len(ux)), ux/w, uy/h)) @ coeff
        lo,hi = np.percentile(colors,[2,98],axis=0)
        result[unknown] = np.clip(predicted,lo-8,hi+8)
    else:
        # Nền nhiều chi tiết: ngoại suy từ các pixel nền gần nhất.
        # Không kéo màu da, áo hay tóc vào vùng khuyết. Đây vẫn là ước lượng.
        _, labels = cv2.distanceTransformWithLabels(
            (~samples).astype(np.uint8), cv2.DIST_L2, 5,
            labelType=cv2.DIST_LABEL_PIXEL)
        lookup = np.zeros((int(labels.max())+1,3),np.float32)
        lookup[labels[samples]] = source[samples]
        result[unknown] = lookup[labels[unknown]]
    return result

def render_basic_bald(source, pts, prob, hair, protected, state, channels):
    """Mô phỏng nhanh: da trong vòm sọ, inpainting ngoài vòm sọ.

    Đây là ước lượng hình học, không phải mô hình khôi phục sọ/cơ thể.
    Không dùng ngưỡng màu tối để nhận diện tóc.
    """
    import cv2
    import numpy as np

    h, w = source.shape[:2]
    left, right = sorted((pts[33], pts[263]), key=lambda p: p[0])
    distance = float(np.linalg.norm(right - left))
    ex = (right - left) / distance
    ey = np.array([-ex[1], ex[0]])
    origin = (left + right) * 0.5
    yy, xx = np.mgrid[:h, :w]
    u = ((xx-origin[0])*ex[0] + (yy-origin[1])*ex[1]) / distance
    v = ((xx-origin[0])*ey[0] + (yy-origin[1])*ey[1]) / distance

    # Vòm sọ dựa trên bề ngang mặt; không dùng đỉnh mặt nạ tóc.
    face_width = float(np.linalg.norm(pts[234] - pts[454])) / distance
    rx = float(np.clip(face_width * 0.51, 0.84, 1.18))
    if 'radius' in state:
        rx = float(state['radius'])*0.2 + rx*0.8
    state['radius'] = rx
    ry = rx * 1.12
    cy = -0.43
    ellipse = (u / rx)**2 + ((v-cy) / ry)**2
    head = (ellipse <= 1.0) & (v < 0.15)

    # Lấy mẫu da từ hai má và trán; loại vùng có xác suất tóc.
    samples = np.zeros((h, w), np.uint8)
    for polygon in ([50, 101, 205, 206, 187, 123],
                    [280, 330, 425, 426, 411, 352],
                    [10, 109, 67, 105, 66, 107, 9, 336, 296, 334, 297, 338]):
        cv2.fillConvexPoly(samples, cv2.convexHull(pts[polygon].astype(np.int32)), 255)
    valid = (samples > 0) & (prob < 0.12) & (channels[3] > 0.65)
    pixels = source[valid].astype(np.float32)
    if len(pixels) < 32:
        raise LoiXoaToc('Chưa lấy được vùng da sạch để dựng da đầu. Cần thấy rõ hai má.')
    luminance = pixels @ np.array([0.2126, 0.7152, 0.0722])
    lo, hi = np.percentile(luminance, [15, 85])
    pixels = pixels[(luminance >= lo) & (luminance <= hi)]
    skin = np.median(pixels, axis=0)
    # Loại màu ngoại lai trong vùng lấy mẫu bằng khoảng cách màu robust.
    deviations = np.linalg.norm(pixels - skin, axis=1)
    pixels = pixels[deviations <= max(12.0, float(np.percentile(deviations, 75)))]
    skin = np.median(pixels, axis=0)

    radius = max(2, round(distance * 0.025))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1, radius*2+1))
    remove = cv2.dilate(hair, kernel) > 0
    remove[protected > 0] = False

    # Không đưa nền vào tóc che vai/cổ: không có mô hình khôi phục cơ thể.
    exterior = remove & ~head
    lower = exterior & (v > 0.45)
    if np.count_nonzero(lower) > max(20, distance*distance*0.02):
        raise LoiXoaToc('Tóc che tai/cổ/vai: bản hiện tại không có model tái tạo cơ thể bị che; giữ camera gốc.')
    filled = source.astype(np.float32).copy()
    known = state['known']
    background = state['background']
    filled[exterior & known] = background[exterior & known]
    unknown = exterior & ~known
    if np.any(unknown):
        restored_background = restore_background(
            source, unknown, channels, protected, distance)
        filled[unknown] = restored_background[unknown]

    # Ưu tiên da trán sạch để nối màu với trán thật, dùng má khi tóc mái che.
    forehead = valid & (abs(u) < 0.65) & (v < -0.13) & (v > -0.85)
    sample_region = forehead if np.count_nonzero(forehead) >= 48 else valid
    colors = source[sample_region].astype(np.float32)
    lightness = colors @ np.array([0.2126, 0.7152, 0.0722])
    low, high = np.percentile(lightness, [18, 82])
    keep = (lightness >= low) & (lightness <= high)
    skin = np.median(colors[keep], axis=0)

    if 'skin' in state and np.linalg.norm(state['skin']-skin) < 35:
        skin = state['skin']*0.25 + skin*0.75
    state['skin'] = skin.copy()

    # Truyền biến thiên màu từ da thật; giới hạn độ dốc để không kéo
    # bóng mắt hoặc má hồng lên toàn bộ vòm đầu.
    coord_u = u[sample_region][keep]
    coord_v = v[sample_region][keep]
    design = np.column_stack((np.ones(len(coord_u)), coord_u, coord_v))
    coefficients, _, _, _ = np.linalg.lstsq(design, colors[keep], rcond=None)
    coefficients[1:] = np.clip(coefficients[1:], -5.0, 5.0)
    middle_u, middle_v = float(np.median(coord_u)), float(np.median(coord_v))
    scalp = (skin[None, None, :]
             + (u-middle_u)[:, :, None]*coefficients[1]
             + (v-middle_v)[:, :, None]*coefficients[2])
    scalp = np.clip(scalp, skin-14, skin+14)
    shade = 1.005 - 0.025*np.clip((u/rx)**2, 0, 1)
    scalp *= shade[:, :, None]

    # Lấy vân từ mảng da thật sạch, không dùng sóng sin vẽ giả vân da.
    # Chọn một đĩa da mà tóc được phân đoạn có xác suất thấp.
    safe = sample_region.astype(np.uint8)
    distances = cv2.distanceTransform(safe, cv2.DIST_L2, 5)
    _, patch_radius, _, patch_center = cv2.minMaxLoc(distances)
    if patch_radius >= 3:
        size = max(3, int(patch_radius * 1.2))
        if size % 2 == 0:
            size -= 1
        tile = cv2.getRectSubPix(source, (size, size), tuple(map(float, patch_center))).astype(np.float32)
        detail = tile - cv2.GaussianBlur(tile, (0, 0), 1.2)
        # Phản chiếu lặp thay vì nối cứng; hệ tọa độ theo đầu.
        size_y, size_x = detail.shape[:2]
        map_x = ((u*distance) % max(1, 2*(size_x-1))).astype(np.float32)
        map_y = ((v*distance) % max(1, 2*(size_y-1))).astype(np.float32)
        map_x = np.minimum(map_x, 2*(size_x-1)-map_x)
        map_y = np.minimum(map_y, 2*(size_y-1)-map_y)
        texture = cv2.remap(detail, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        scalp += np.clip(texture, -3, 3) * 0.5
    boundary = np.clip((1.0-ellipse) / 0.045, 0, 1) * head
    filled[head & remove] = scalp[head & remove]

    # RGB nguyên + alpha mềm riêng. Không hòa vào camera cũ trước,
    # nên mép lớp ảnh không mang theo một dải nền cứng khi đầu di chuyển.
    outside_distance = cv2.distanceTransform((~remove).astype(np.uint8), cv2.DIST_L2, 5)
    feather = max(1.0, distance*0.015)
    soft = np.clip(1-outside_distance/feather, 0, 1)
    soft[remove] = 1.0
    soft[protected > 0] = 0.0
    soft[soft < 0.02] = 0.0
    overlay = np.rint(soft*255).astype(np.uint8)
    candidate = np.clip(np.rint(filled), 0, 255).astype(np.uint8)
    candidate[overlay == 0] = source[overlay == 0]
    return candidate, overlay

def update_state(state, source, pts, channels):
    """Làm mượt sau khi căn chuyển động; nền lưu trong hệ camera cố định."""
    import cv2
    import numpy as np
    now = time.monotonic()
    h, w = source.shape[:2]
    last = state.get('time', 0)
    valid_previous = (now-last < 0.8 and state.get('shape') == (h, w))
    prob = channels[1].copy()
    if valid_previous and 'points' in state:
        ids = [33, 263, 152]
        matrix = cv2.getAffineTransform(state['points'][ids], pts[ids])
        previous = cv2.warpAffine(state['prob'], matrix, (w, h))
        # Không giữ vùng tóc cũ khi mô hình hiện tại xác nhận đó là da/nền.
        uncertain = (prob > 0.20) & (prob < 0.8)
        prob[uncertain] = prob[uncertain]*0.85 + previous[uncertain]*0.15
    else:
        state.pop('skin', None)
        state.pop('radius', None)
    background = channels[0] > 0.97
    if not valid_previous:
        state['background'] = source.astype(np.float32).copy()
        state['known'] = np.zeros((h, w), bool)
    elif np.count_nonzero(background & state['known']) > 1000:
        common = background & state['known']
        discrepancy = np.median(np.abs(source[common].astype(np.float32)-state['background'][common]))
        # Khi camera/nền dịch chuyển rõ, bỏ nền cũ thay vì dán sai vị trí.
        if discrepancy > 14:
            state['known'][:] = False
    old = background & state['known']
    new = background & ~state['known']
    state['background'][old] = state['background'][old]*0.75 + source[old]*0.25
    state['background'][new] = source[new]
    state['known'][background] = True
    state.update(time=now, shape=(h, w), points=pts.copy(), prob=prob.copy())
    return prob

class BoXoaToc:

    def __init__(self):
        self.lock = threading.Lock()
        self.face = None
        self.segmenter = None
        self.mp = None
        self.client = WorkerClient()
        self.states = {}

    def nap(self):
        if self.face is not None:
            return
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        if not FACE.is_file() or not HAIR.is_file():
            raise LoiXoaToc('Thiếu face_landmarker.task hoặc selfie_multiclass_256x256.tflite. Cần tải model bổ sung theo hướng dẫn.')
        face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(FACE)), running_mode=vision.RunningMode.IMAGE, num_faces=2, min_face_detection_confidence=0.6, min_face_presence_confidence=0.6))
        try:
            segmenter = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(base_options=python.BaseOptions(model_asset_path=str(HAIR)), running_mode=vision.RunningMode.IMAGE, output_confidence_masks=True, output_category_mask=False))
        except Exception:
            face.close()
            raise
        self.mp = mp
        self.face = face
        self.segmenter = segmenter

    def phan_vung(self, image):
        import cv2
        import numpy as np
        result = self.segmenter.segment(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(image)))
        if not result.confidence_masks or len(result.confidence_masks) != 6:
            raise LoiXoaToc('Model phân vùng tóc không trả đủ 6 lớp.')
        prob = result.confidence_masks[1].numpy_view().copy().squeeze()
        return cv2.resize(prob, (image.shape[1], image.shape[0]))

    def xoa(self, rgb, stream_id=None):
        configure()
        import cv2
        import numpy as np
        from PIL import Image
        if not self.lock.acquire(blocking=False):
            raise LoiXoaToc('Bộ xóa tóc đang xử lý khung hình trước.')
        started = time.perf_counter()
        try:
            arr = np.asarray(rgb)
            if arr.ndim != 3 or arr.shape[2] != 3 or arr.dtype != np.uint8:
                raise LoiXoaToc('Ảnh phải là RGB uint8.')
            if min(arr.shape[:2]) < 128 or arr.shape[0]*arr.shape[1] > 20_000_0000:
                raise LoiXoaToc('Kích thước ảnh không hợp lệ.')
            image = Image.fromarray(arr)
            image.thumbnail((640, 650))
            source = np.asarray(image).copy()
            self.nap()
            frame = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(source))
            faces = self.face.detect(frame).face_landmarks
            if len(faces) != 1:
                if stream_id:
                    self.states.pop(stream_id, None)
                raise LoiXoaToc('Cần đúng một người trong khung để xóa tóc.')
            h, w = source.shape[:2]
            pts = np.float32([[p.x*w, p.y*h] for p in faces[0]])
            distance = float(np.linalg.norm(pts[33]-pts[263]))
            if distance < 25:
                raise LoiXoaToc('Mặt quá nhỏ để phân vùng tóc.')
            midpoint = (pts[33]+pts[263])/2
            axis = (pts[263]-pts[33])/distance
            yaw = abs(float(np.dot(pts[1]-midpoint, axis)/distance))
            if yaw > 0.24:
                raise LoiXoaToc('Góc quay quá lớn để ước lượng vòm sọ ổn định.')
            segmented = self.segmenter.segment(frame)
            if not segmented.confidence_masks or len(segmented.confidence_masks) != 6:
                raise LoiXoaToc('Cần đúng model SelfieMulticlass sáu lớp.')
            channels = [cv2.resize(m.numpy_view().copy().squeeze(), (w,h)) for m in segmented.confidence_masks]
            state = {}
            if stream_id:
                self.states = {key: value for key,value in self.states.items()
                               if time.monotonic()-value.get('time',0) < 30}
                if stream_id not in self.states and len(self.states) >= 4:
                    oldest = min(self.states, key=lambda key:self.states[key].get('time',0))
                    del self.states[oldest]
                state = self.states.setdefault(stream_id, {})
            prob = update_state(state, source, pts, channels)
            hair, alpha, protected = make_mask(prob, pts)
            semantic_protection = np.maximum.reduce([channels[i] for i in (2,3,4,5)]) > 0.55
            semantic_protection &= channels[1] < 0.65
            protected[semantic_protection] = 255
            candidate, overlay = render_basic_bald(source, pts, prob, hair, protected, state, channels)
            return {
                'anh': candidate, 'anh_goc': source, 'mat_na': overlay,
                'chap_nhan': True, 'ty_le_toc_sot': None,
                'giay': round(time.perf_counter()-started,3), 'thiet_bi': 'cpu',
                'thong_bao': 'Mô phỏng tóc ngắn, camera cố định; không phải mô hình GAN của TikTok.',
                'landmarks': [{'x':float(p[0]/w), 'y':float(p[1]/h)} for p in pts],
            }
        finally:
            self.lock.release()

    def close(self):
        with self.lock:
            self.client.close()
            if self.face is not None:
                self.face.close()
            if self.segmenter is not None:
                self.segmenter.close()
            self.face = None
            self.segmenter = None
_engine = None
_init_lock = threading.Lock()

def xoa_toc(rgb, stream_id=None):
    """Hàm Django gọi, giữ giao diện như bản cũ."""
    global _engine
    with _init_lock:
        if _engine is None:
            _engine = BoXoaToc()
            atexit.register(_engine.close)
        engine = _engine
    return engine.xoa(rgb, stream_id=stream_id)

def main():
    configure()
    parser = argparse.ArgumentParser(description='Stable-Hair cho camera Django')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--tai-model', action='store_true')
    parser.add_argument('--kiem-tra-worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker()
    elif args.tai_model:
        tai_model()
    elif args.kiem_tra_worker:
        client = WorkerClient()
        try:
            client.start()
            log('PASS: checkpoint loaded, worker CUDA ready.')
        finally:
            client.close()
    else:
        log('File này xử lý ảnh RGB do camera trên web gửi tới.')
        log('Chạy web bằng lệnh:')
        log(f"{ROOT / '.venv' / 'Scripts' / 'python.exe'} -X utf8 {ROOT / 'manage.py'} runserver --noreload")
        log('Mở http://127.0.0.1:8000/phong-thu-toc/ và bấm Bật camera.')
if __name__ == '__main__':
    main()---
