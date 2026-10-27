"""Video TikTok ~15 giay gioi thieu dich vu cat nhom theo yeu cau (dung anh ong nhom tron).

Chay:  python3 tao_video_dich_vu_cat.py
Ket qua: video-tiktok-dich-vu-cat.mp4
"""
import os

from tao_video import BGS, DIR, IMGS, load, make_bg
from tao_video_tiktok import cta_scene, cut_scene, hook_scene, render

OUT = os.path.join(DIR, "video-tiktok-dich-vu-cat.mp4")

for k, f in {"ong": "5-ong-cat-ngang.jpg", "ong_to": "6-ong-to.jpg", "bo_ong": "7-bo-ong.jpg"}.items():
    IMGS[k] = load(f)
    BGS[k] = make_bg(IMGS[k])

SCENES = [
    hook_scene(2.4, "bo_ong", "CẦN 1 ĐOẠN", "NGẮN THÔI?", "→ NHÔM PHÚC LÊ CẮT CHO BẠN!"),
    cut_scene("ong", "CẮT THEO YÊU CẦU", "Đúng kích thước khách cần"),
    cut_scene("ong_to", "MUA LẺ CŨNG CẮT", "Không cần mua nguyên cây"),
    cut_scene("cat", "ỐNG & TẢN NHIỆT", "Đều nhận cắt theo yêu cầu"),
    cut_scene("bo_ong", "BÁN SỈ & LẺ", "Báo giá nhanh qua Zalo"),
    cta_scene(3.8, "ong"),
]

if __name__ == "__main__":
    render(SCENES, OUT)
