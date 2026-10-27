"""Ban TikTok: ngan ~15 giay, cau mo dau gay chu y, cat canh nhanh.

Moi chu deu nam trong "vung an toan" cua TikTok (khong bi nut like/binh luan/chu thich che).
Ten cua hang, hotline, dia chi lay chung tu phan CAU HINH trong tao_video.py.

Chay:  python3 tao_video_tiktok.py
Ket qua: video-tiktok-nhom-tan-nhiet.mp4
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter

from tao_video import (BGS, DIA_CHI, DIR, FPS, H, HOTLINE, IMGS, ORANGE, STEEL,
                       TEN_CUA_HANG, W, WHITE, draw_text, ease, font, make_music)

OUT = os.path.join(DIR, "video-tiktok-nhom-tan-nhiet.mp4")
XFADE = 0.25
# vung an toan TikTok: tren 180px, duoi tu 1380px, ben phai 140px bi giao dien che
SAFE_TOP, SAFE_BOTTOM = 180, 1380
CX = (W - 140 + 60) / 2  # tam ngang cua vung an toan


def cover(img, w, h, p, zoom_to=1.12, punch=0.3):
    """Anh lap day khung w x h; dau canh phong manh roi tu tu phong cham."""
    z = 1.0 + (zoom_to - 1.0) * p
    if p * 2.4 < punch:  # hieu ung 'dap' luc chuyen canh
        z += 0.12 * (1 - ease(p * 2.4 / punch))
    ar = w / h
    cw = min(img.width, img.height * ar) / z
    ch = cw / ar
    box = ((img.width - cw) / 2, (img.height - ch) / 2,
           (img.width + cw) / 2, (img.height + ch) / 2)
    return img.resize((w, h), Image.BILINEAR, box=box)


def label(layer, cx, cy, s, f, fg, bg, alpha, pad=(36, 18)):
    d = ImageDraw.Draw(layer)
    tw = d.textlength(s, font=f)
    a = int(255 * alpha)
    d.rounded_rectangle((cx - tw / 2 - pad[0], cy - f.size / 2 - pad[1],
                         cx + tw / 2 + pad[0], cy + f.size / 2 + pad[1]), 18, fill=bg + (a,))
    d.text((cx, cy), s, font=f, fill=fg + (a,), anchor="mm")


def hook_scene(dur=2.4):
    img, bg = IMGS["cat"], BGS["cat"]
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-200, 300, W + 200, 1300), fill=(255, 70, 0, 110))
    glow = glow.filter(ImageFilter.GaussianBlur(120))

    def render(t):
        p = t / dur
        frame = bg.copy()
        frame.paste(cover(img, W, 900, p, 1.2), (0, 520))
        frame.paste(glow, (0, 0), glow)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        a = ease(t / 0.25)
        draw_text(layer, (CX, 230 + 30 * (1 - a)), "THIẾT BỊ", font("Black", 110), WHITE, a, "ma")
        draw_text(layer, (CX, 360 + 30 * (1 - a)), "NÓNG QUÁ?", font("Black", 130), ORANGE, a, "ma")
        a = ease((t - 0.9) / 0.3)
        if a > 0:
            s = 1 + 0.25 * (1 - a)
            label(layer, CX, 1250, "→ DÙNG NHÔM TẢN NHIỆT!", font("Black", int(52 * s)),
                  (20, 20, 20), WHITE, a)
        frame.paste(layer, (0, 0), layer)
        return frame

    return dur, render


def cut_scene(key, big, small, dur=2.4):
    img, bg = IMGS[key], BGS[key]

    def render(t):
        p = t / dur
        frame = bg.copy()
        frame.paste(cover(img, W, 1000, p), (0, 470))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        a = ease(t / 0.3)
        ft = font("Bold", 30)
        tw = d.textlength(TEN_CUA_HANG, font=ft)
        d.rounded_rectangle((CX - tw / 2 - 26, SAFE_TOP + 10, CX + tw / 2 + 26, SAFE_TOP + 62), 26,
                            fill=ORANGE + (int(255 * a),))
        d.text((CX, SAFE_TOP + 36), TEN_CUA_HANG, font=ft, fill=WHITE + (int(255 * a),), anchor="mm")
        draw_text(layer, (CX - 50 * (1 - a), 300), big, font("Black", 96), WHITE, a, "ma")
        a2 = ease((t - 0.35) / 0.35)
        if a2 > 0:
            label(layer, CX, 1300, small, font("Bold", 52), WHITE, ORANGE, a2)
        frame.paste(layer, (0, 0), layer)
        return frame

    return dur, render


def cta_scene(dur=3.8):
    img = IMGS["mau"]
    base = Image.blend(BGS["mau"], Image.new("RGB", (W, H), (6, 10, 18)), 0.4)

    def render(t):
        frame = base.copy()
        th = cover(img, 880, 500, t / dur, 1.08, punch=0)
        m = Image.new("L", th.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, 879, 499), 26, fill=255)
        frame.paste(th, (int(CX - 440), 220), m)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        a = ease(t / 0.35)
        draw_text(layer, (CX, 770 + 30 * (1 - a)), TEN_CUA_HANG, font("Black", 104), WHITE, a, "ma")
        a = ease((t - 0.3) / 0.35)
        draw_text(layer, (CX, 900), "Gọi / Zalo báo giá ngay", font("SemiBold", 50), STEEL, a, "ma")
        a = ease((t - 0.55) / 0.35)
        pulse = 1 + 0.04 * abs(((t * 2.2) % 2) - 1) if t > 1 else 1
        bw, bh = 820 * pulse, 160 * pulse
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((CX - bw / 2, 1080 - bh / 2, CX + bw / 2, 1080 + bh / 2),
                            int(bh / 2), fill=ORANGE + (int(255 * a),))
        draw_text(layer, (CX, 1080), HOTLINE, font("Black", int(88 * pulse)), WHITE, a, "mm")
        a = ease((t - 0.85) / 0.35)
        draw_text(layer, (CX, 1220), DIA_CHI, font("SemiBold", 44), WHITE, a, "ma")
        frame.paste(layer, (0, 0), layer)
        return frame

    return dur, render


SCENES = [
    hook_scene(2.4),
    cut_scene("mau", "ĐỦ MẪU MÃ", "Nhiều kích thước, kiểu cánh"),
    cut_scene("cat", "CÁNH DÀY ĐỀU", "Tỏa nhiệt nhanh, ổn định"),
    cut_scene("rong", "BẢN RỘNG", "Biến tần • Inverter • Bộ nguồn"),
    cut_scene("dai", "THANH DÀI", "Cắt theo kích thước yêu cầu"),
    cta_scene(3.8),
]


def total_duration():
    return sum(d for d, _ in SCENES) - XFADE * (len(SCENES) - 1)


def frame_at(T):
    start, hits = 0.0, []
    for d, r in SCENES:
        if start <= T < start + d:
            hits.append((T - start, r))
        start += d - XFADE
    if not hits:
        d, r = SCENES[-1]
        return r(d - 1e-3)
    if len(hits) == 1:
        return hits[0][1](hits[0][0])
    (t1, r1), (t2, r2) = hits
    return Image.blend(r1(t1), r2(t2), t2 / XFADE)


def main():
    dur = total_duration()
    wav = os.path.join(DIR, "_nhac_tiktok.wav")
    make_music(wav, dur, bpm=124)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
           "-movflags", "+faststart", OUT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(dur * FPS)):
        proc.stdin.write(frame_at(i / FPS).tobytes())
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print("Xong:", OUT, f"({dur:.1f} giay)")


if __name__ == "__main__":
    main()
