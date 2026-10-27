"""Tao video quang cao nhom tan nhiet (dinh dang doc 1080x1920 cho TikTok / Reels / Zalo).

Chay:  python3 tao_video.py
Ket qua: video-quang-cao-nhom-tan-nhiet.mp4 (cung thu muc)

Muon doi chu (hotline, ten cua hang...) chi can sua phan CAU HINH ben duoi roi chay lai.
"""
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ===================== CAU HINH =====================
TEN_CUA_HANG = "NHÔM PHÚC LÊ"
HOTLINE = "0912.345.678"
DIA_CHI = "Hà Nội  •  Giao hàng toàn quốc"
# ====================================================

W, H, FPS = 1080, 1920, 30
XFADE = 0.6
DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DIR, "video-quang-cao-nhom-tan-nhiet.mp4")
FONT_DIR = "/usr/share/fonts/opentype/inter"

ORANGE = (255, 122, 26)
WHITE = (255, 255, 255)
STEEL = (200, 212, 225)


def font(weight, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, f"Inter-{weight}.otf"), size)


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def load(name):
    return Image.open(os.path.join(DIR, "anh", name)).convert("RGB")


def make_bg(img):
    """Nen doc: anh phong to, lam mo va toi di."""
    s = max(W / img.width, H / img.height)
    big = img.resize((int(img.width * s) + 1, int(img.height * s) + 1), Image.BILINEAR)
    l, t = (big.width - W) // 2, (big.height - H) // 2
    big = big.crop((l, t, l + W, t + H)).filter(ImageFilter.GaussianBlur(40))
    dark = Image.new("RGB", (W, H), (8, 14, 24))
    return Image.blend(big, dark, 0.62)


IMGS = {k: load(v) for k, v in {
    "mau": "1-cac-mau.jpg", "dai": "2-thanh-dai.jpg",
    "cat": "3-mat-cat.jpg", "rong": "4-ban-rong.jpg"}.items()}
BGS = {k: make_bg(v) for k, v in IMGS.items()}

FG_W, FG_H, FG_Y = 1000, 760, 520
MASK = Image.new("L", (FG_W, FG_H), 0)
ImageDraw.Draw(MASK).rounded_rectangle((0, 0, FG_W - 1, FG_H - 1), 28, fill=255)


def ken_burns(img, p, zoom_from=1.0, zoom_to=1.18, pan=(0.0, 0.0)):
    """Cat 1 khung tu anh roi phong dan -> chuyen dong muot."""
    z = zoom_from + (zoom_to - zoom_from) * p
    ar = FG_W / FG_H
    cw = min(img.width, img.height * ar) / z
    ch = cw / ar
    cx = img.width / 2 + pan[0] * (img.width - cw) / 2 * p
    cy = img.height / 2 + pan[1] * (img.height - ch) / 2 * p
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return img.resize((FG_W, FG_H), Image.BILINEAR, box=box)


def text_w(draw, s, f):
    return draw.textlength(s, font=f)


def draw_text(layer, xy, s, f, fill, alpha=1.0, anchor="la", shadow=True):
    if alpha <= 0:
        return
    d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    if shadow:
        d.text((xy[0] + 3, xy[1] + 4), s, font=f, fill=(0, 0, 0, int(a * 0.6)), anchor=anchor)
    d.text(xy, s, font=f, fill=fill + (a,), anchor=anchor)


def top_tag(layer, t):
    """Nhan nho phia tren: ten cua hang."""
    a = ease(t / 0.5)
    d = ImageDraw.Draw(layer)
    f = font("Bold", 34)
    s = TEN_CUA_HANG
    tw = text_w(d, s, f)
    x0 = (W - tw) / 2 - 28
    d.rounded_rectangle((x0, 110, x0 + tw + 56, 172), 31, fill=ORANGE + (int(235 * a),))
    d.text((W / 2, 141), s, font=f, fill=WHITE + (int(255 * a),), anchor="mm")


def photo_scene(key, title, bullets, zoom=(1.0, 1.18), pan=(0, 0), dur=5.0):
    img, bg = IMGS[key], BGS[key]

    def render(t):
        p = t / dur
        frame = bg.copy()
        # anh chinh co vien bo goc + do bong
        fg = ken_burns(img, p, *zoom, pan=pan)
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).rounded_rectangle(
            (40, FG_Y + 18, 40 + FG_W, FG_Y + FG_H + 18), 28, fill=170)
        sh = sh.filter(ImageFilter.GaussianBlur(22))
        frame.paste((0, 0, 0), (0, 0), sh)
        frame.paste(fg, (40, FG_Y), MASK)
        ImageDraw.Draw(frame).rounded_rectangle(
            (40, FG_Y, 40 + FG_W, FG_Y + FG_H), 28, outline=(255, 255, 255), width=3)

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        top_tag(layer, t)
        # tieu de truot tu trai vao
        ft = font("Black", 76)
        y = 240
        for i, line in enumerate(title):
            a = ease((t - 0.15 - i * 0.15) / 0.55)
            draw_text(layer, (W / 2 - 60 * (1 - a), y), line, ft,
                      WHITE if i == 0 else ORANGE, a, anchor="ma")
            y += 92
        # cac y chinh hien lan luot
        fb = font("SemiBold", 46)
        y = FG_Y + FG_H + 80
        for i, b in enumerate(bullets):
            a = ease((t - 0.8 - i * 0.45) / 0.5)
            if a <= 0:
                continue
            x = 110 + 40 * (1 - a)
            d = ImageDraw.Draw(layer)
            d.ellipse((x - 46, y + 8, x - 14, y + 40), fill=ORANGE + (int(255 * a),))
            d.line((x - 39, y + 24, x - 32, y + 31, x - 21, y + 16),
                   fill=WHITE + (int(255 * a),), width=5)
            draw_text(layer, (x + 6, y), b, fb, WHITE, a)
            y += 86
        frame.paste(layer, (0, 0), layer)
        return frame

    return dur, render


def intro_scene(dur=4.0):
    img, bg = IMGS["cat"], BGS["cat"]

    def render(t):
        p = t / dur
        frame = bg.copy()
        # anh full chieu ngang, phong to dan
        z = 1.05 + 0.25 * p
        ch = img.height / z
        cw = ch * W / 1100
        cw = min(cw, img.width)
        box = ((img.width - cw) / 2, (img.height - ch) / 2,
               (img.width + cw) / 2, (img.height + ch) / 2)
        fg = img.resize((W, 1100), Image.BILINEAR, box=box)
        grad = Image.linear_gradient("L").resize((W, 1100))
        m = Image.eval(grad, lambda v: 255 if v < 128 else int(255 * (255 - v) / 127))
        m2 = Image.eval(grad.transpose(Image.FLIP_TOP_BOTTOM),
                        lambda v: 255 if v < 128 else int(255 * (255 - v) / 127))
        frame.paste(fg, (0, 420), Image.fromarray(
            np.minimum(np.asarray(m), np.asarray(m2))))

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        top_tag(layer, t)
        a1 = ease((t - 0.2) / 0.6)
        draw_text(layer, (W / 2, 250 - 40 * (1 - a1)), "NHÔM", font("Black", 150), WHITE, a1, "ma")
        a2 = ease((t - 0.5) / 0.6)
        draw_text(layer, (W / 2, 400 + 40 * (1 - a2)), "TẢN NHIỆT", font("Black", 130), ORANGE, a2, "ma")
        a3 = ease((t - 1.2) / 0.6)
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((90, 1560, W - 90, 1700), 70, fill=(10, 18, 30, int(215 * a3)),
                            outline=ORANGE + (int(255 * a3),), width=4)
        draw_text(layer, (W / 2, 1630), "Tản nhiệt nhanh  •  Bền bỉ  •  Giá tốt",
                  font("Bold", 46), WHITE, a3, "mm", shadow=False)
        # vet sang quet ngang
        sx = -400 + (W + 800) * ease((t - 1.6) / 1.2)
        if 1.6 < t < 2.8:
            shine = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(shine).polygon(
                [(sx, 420), (sx + 120, 420), (sx - 80, 1520), (sx - 200, 1520)],
                fill=(255, 255, 255, 60))
            shine = shine.filter(ImageFilter.GaussianBlur(25))
            frame.paste(shine, (0, 0), shine)
        frame.paste(layer, (0, 0), layer)
        return frame

    return dur, render


def outro_scene(dur=6.0):
    yy = np.linspace(0, 1, H)[:, None]
    col = np.array([14, 26, 44]) * (1 - yy) + np.array([4, 8, 14]) * yy
    base = Image.fromarray(np.repeat(col[:, None, :], W, axis=1).astype(np.uint8))
    thumbs = [IMGS[k].resize((470, 330), Image.LANCZOS) for k in ("mau", "cat", "rong", "dai")]

    def render(t):
        frame = base.copy()
        # luoi 4 anh nho
        for i, th in enumerate(thumbs):
            a = ease((t - i * 0.12) / 0.5)
            x = 50 + (i % 2) * 510
            y = 230 + (i // 2) * 370 + int(60 * (1 - a))
            m = Image.new("L", th.size, 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, th.width - 1, th.height - 1), 22,
                                                fill=int(255 * a))
            frame.paste(th, (x, y), m)

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        top_tag(layer, t)
        a = ease((t - 0.6) / 0.6)
        draw_text(layer, (W / 2, 1020), "LIÊN HỆ NGAY", font("Black", 104), WHITE, a, "ma")
        a = ease((t - 0.9) / 0.6)
        draw_text(layer, (W / 2, 1150), "Báo giá nhanh – Giá tận xưởng", font("SemiBold", 50), STEEL, a, "ma")
        # nut hotline nhap nhay
        a = ease((t - 1.3) / 0.6)
        pulse = 1 + 0.035 * math.sin(t * 6) if t > 1.9 else 1
        bw, bh = 860 * pulse, 170 * pulse
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((W / 2 - bw / 2, 1300 - bh / 2 + 85, W / 2 + bw / 2, 1300 + bh / 2 + 85),
                            int(bh / 2), fill=ORANGE + (int(255 * a),))
        draw_text(layer, (W / 2, 1385), HOTLINE,
                  font("Black", int(84 * pulse)), WHITE, a, "mm")
        draw_text(layer, (W / 2, 1265), "HOTLINE / ZALO", font("Bold", 38), WHITE, a, "mm")
        a = ease((t - 1.8) / 0.6)
        draw_text(layer, (W / 2, 1530), DIA_CHI, font("Medium", 44), STEEL, a, "ma")
        a = ease((t - 2.2) / 0.6)
        draw_text(layer, (W / 2, 1640), "Nhận cắt theo kích thước yêu cầu",
                  font("SemiBold", 44), ORANGE, a, "ma")
        frame.paste(layer, (0, 0), layer)
        return frame

    return dur, render


SCENES = [
    intro_scene(4.2),
    photo_scene("mau", ["ĐA DẠNG", "MẪU MÃ"],
                ["Nhiều kích thước, nhiều kiểu cánh", "Hàng có sẵn, giao nhanh", "Phù hợp mọi thiết bị"],
                zoom=(1.0, 1.15), pan=(0.3, 0.2), dur=5.0),
    photo_scene("cat", ["CÁNH TẢN", "DÀY & ĐỀU"],
                ["Tăng diện tích tỏa nhiệt", "Thoát nhiệt nhanh, ổn định", "Bề mặt nhôm sáng, đẹp"],
                zoom=(1.0, 1.2), pan=(0.2, 0.0), dur=5.0),
    photo_scene("rong", ["BẢN RỘNG", "CHO CÔNG SUẤT LỚN"],
                ["Biến tần, bộ nguồn, inverter", "Đèn LED, amply, tủ điện", "Máy hàn, sạc, thiết bị công nghiệp"],
                zoom=(1.0, 1.15), pan=(0.0, 0.3), dur=5.0),
    photo_scene("dai", ["THANH DÀI", "CẮT THEO YÊU CẦU"],
                ["Cắt đúng kích thước khách cần", "Đóng gói cẩn thận, chống trầy", "Giá tốt cho đơn sỉ & xưởng"],
                zoom=(1.0, 1.18), pan=(-0.3, 0.0), dur=5.0),
    outro_scene(6.0),
]


def total_duration():
    return sum(d for d, _ in SCENES) - XFADE * (len(SCENES) - 1)


def frame_at(T):
    start = 0.0
    hits = []
    for d, r in SCENES:
        if start <= T < start + d:
            hits.append((T - start, d, r))
        start += d - XFADE
    if not hits:
        d, r = SCENES[-1]
        return r(d - 1e-3)
    if len(hits) == 1:
        return hits[0][2](hits[0][0])
    (t1, _, r1), (t2, _, r2) = hits[0], hits[1]
    return Image.blend(r1(t1), r2(t2), ease(t2 / XFADE))


def make_music(path, dur, sr=44100):
    """Nhac nen tu tao (khong ban quyen): hop am Am-F-C-G, trong nhe, 100 BPM."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    beat = 60 / 100
    bar = beat * 4
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    for b in range(int(dur / bar) + 1):
        s, e = int(b * bar * sr), min(n, int((b + 1) * bar * sr))
        if s >= n:
            break
        tt = t[s:e] - b * bar
        env = np.minimum(1, tt / 0.3) * np.exp(-tt * 0.35)
        for m in chords[b % 4]:
            f = hz(m)
            out[s:e] += 0.07 * env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt))
        bass = hz(chords[b % 4][0] - 12)
        for k in range(8):  # bass not moc tam
            ss = s + int(k * beat / 2 * sr)
            ee = min(e, ss + int(beat / 2 * sr))
            if ss >= ee:
                continue
            ts = t[ss:ee] - t[ss]
            out[ss:ee] += 0.12 * np.exp(-ts * 6) * np.sin(2 * np.pi * bass * ts)
    rng = np.random.default_rng(1)
    for k in range(int(dur / beat * 2)):
        s = int(k * beat / 2 * sr)
        if s >= n:
            break
        if k % 2 == 0:  # trong kick
            L = min(n - s, int(0.25 * sr))
            ts = np.arange(L) / sr
            out[s:s + L] += 0.35 * np.exp(-ts * 18) * np.sin(2 * np.pi * (50 + 90 * np.exp(-ts * 40)) * ts)
        else:  # hi-hat
            L = min(n - s, int(0.05 * sr))
            ts = np.arange(L) / sr
            out[s:s + L] += 0.05 * np.exp(-ts * 80) * rng.uniform(-1, 1, L)
    fade = np.ones(n)
    fi, fo = int(0.5 * sr), int(2.0 * sr)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    out = out * fade
    out = out / np.max(np.abs(out)) * 0.8
    data = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


def main():
    dur = total_duration()
    wav = os.path.join(DIR, "_nhac.wav")
    make_music(wav, dur)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
           "-movflags", "+faststart", OUT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nframes = int(dur * FPS)
    for i in range(nframes):
        proc.stdin.write(frame_at(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"  {i}/{nframes} khung hinh")
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print("Xong:", OUT, f"({dur:.1f} giay)")


if __name__ == "__main__":
    main()
