"""Generate PWA icons matching favicon.svg design using Pillow."""
from PIL import Image, ImageDraw
import math

COLORS = {
    "bg": "#0e0f23",
    "accent": "#6366f1",
    "green": "#00d68f",
    "lines": "#94a3b8",
    "dark": "#07080f",
}


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def draw_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 64  # scale factor from 64x64 SVG viewBox

    # Background rounded rect
    r = 14 * s
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=hex_to_rgb(COLORS["bg"]))

    # Border stroke
    accent_rgb = hex_to_rgb(COLORS["accent"])
    border_color = tuple(int(c * 0.6) for c in accent_rgb) + (255,)
    sw = max(1, round(1.5 * s))
    draw.rounded_rectangle([sw // 2, sw // 2, size - 1 - sw // 2, size - 1 - sw // 2],
                           radius=r, outline=border_color, width=sw)

    # Document body
    dx, dy, dw, dh = 12 * s, 8 * s, 34 * s, 42 * s
    dr = 5 * s
    dark_rgb = hex_to_rgb(COLORS["dark"])
    draw.rounded_rectangle([dx, dy, dx + dw, dy + dh], radius=dr, fill=dark_rgb)

    # Document border
    doc_border = tuple(int(c * 0.5) for c in accent_rgb) + (255,)
    draw.rounded_rectangle([dx, dy, dx + dw, dy + dh], radius=dr, outline=doc_border, width=max(1, round(s)))

    # Document header (purple bar)
    header_color = tuple(int(c * 0.7) for c in accent_rgb) + (255,)
    hh = 10 * s
    # Draw header as rounded rect clipped to top
    draw.rounded_rectangle([dx, dy, dx + dw, dy + hh], radius=dr, fill=header_color)
    # Fill bottom half of header to remove bottom rounding
    draw.rectangle([dx, dy + dr, dx + dw, dy + hh], fill=header_color)

    # Document lines
    lines_rgb = hex_to_rgb(COLORS["lines"])
    line_data = [
        (18, 26, 22, 2.5, 0.5),
        (18, 32, 16, 2.5, 0.4),
        (18, 38, 19, 2.5, 0.3),
    ]
    for lx, ly, lw, lh, opacity in line_data:
        color = tuple(int(c * opacity) for c in lines_rgb) + (255,)
        lr = 1.5 * s
        draw.rounded_rectangle(
            [lx * s, ly * s, (lx + lw) * s, (ly + lh) * s],
            radius=lr, fill=color
        )

    # Green check circle
    cx, cy, cr = 46 * s, 46 * s, 12 * s
    green_rgb = hex_to_rgb(COLORS["green"])
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=green_rgb)

    # Checkmark path: M40,46 L44,50 L52,40
    check_points = [
        (40 * s, 46 * s),
        (44 * s, 50 * s),
        (52 * s, 40 * s),
    ]
    check_width = max(2, round(2.5 * s))
    draw.line(check_points, fill=dark_rgb, width=check_width, joint="curve")

    # Round the line caps manually by drawing circles at endpoints
    cap_r = check_width / 2
    for px, py in check_points:
        draw.ellipse([px - cap_r, py - cap_r, px + cap_r, py + cap_r], fill=dark_rgb)

    return img


if __name__ == "__main__":
    for sz in (192, 512):
        icon = draw_icon(sz)
        path = f"app/static/icon-{sz}.png"
        icon.save(path, "PNG")
        print(f"Saved {path} ({sz}x{sz})")
