from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def make_banner():
    img = Image.new("RGB", (1280, 500), "#f7f8fb")
    draw = ImageDraw.Draw(img)
    for x in range(1280):
        shade = int(247 - (x / 1280) * 10)
        draw.line([(x, 0), (x, 500)], fill=(shade, shade + 1, min(shade + 6, 255)))
    draw.rectangle((0, 0, 1280, 10), fill="#7f54b3")
    draw.ellipse((1040, -120, 1360, 200), fill="#e7ddf2")
    draw.ellipse((960, 300, 1220, 560), fill="#dff3ee")

    draw.text((76, 72), "WooCommerce Connector", fill="#1f2937", font=font(52, True))
    draw.text((78, 138), "for Odoo 19", fill="#7f54b3", font=font(34, True))
    draw.text((80, 210), "Products  |  Customers  |  Orders  |  Logs  |  Dashboard", fill="#374151", font=font(25))
    draw.text((80, 264), "Complete synchronization workflow by Odoo Wings", fill="#667085", font=font(24))

    rounded(draw, (80, 346, 355, 410), 8, "#7f54b3")
    draw.text((112, 363), "Multi Store Ready", fill="#ffffff", font=font(24, True))

    card_x, card_y = 760, 96
    rounded(draw, (card_x, card_y, card_x + 390, card_y + 292), 8, "#ffffff", "#d8dee8", 2)
    draw.text((card_x + 28, card_y + 26), "Sync Dashboard", fill="#1f2937", font=font(30, True))
    labels = [("Products", 84, "#7f54b3"), ("Customers", 42, "#00a09d"), ("Orders", 31, "#f59e0b")]
    y = card_y + 88
    for label, value, color in labels:
        rounded(draw, (card_x + 30, y, card_x + 334, y + 48), 8, "#f8fafc", "#e5e7eb")
        draw.rectangle((card_x + 30, y, card_x + 38, y + 48), fill=color)
        draw.text((card_x + 56, y + 12), label, fill="#374151", font=font(20, True))
        draw.text((card_x + 276, y + 10), str(value), fill=color, font=font(24, True))
        y += 66

    rounded(draw, (970, 382, 1170, 436), 8, "#ffffff", "#d8dee8", 2)
    draw.text((1004, 398), "Odoo Wings", fill="#1f2937", font=font(22, True))
    img.save(ROOT / "banner.png", "PNG")


def make_icon():
    img = Image.new("RGBA", (512, 512), "#7f54b3")
    draw = ImageDraw.Draw(img)
    rounded(draw, (70, 82, 442, 430), 48, "#ffffff")
    draw.text((126, 126), "W", fill="#7f54b3", font=font(150, True))
    draw.text((236, 150), "OO", fill="#00a09d", font=font(62, True))
    draw.rectangle((144, 308, 368, 326), fill="#7f54b3")
    draw.ellipse((160, 340, 216, 396), fill="#1f2937")
    draw.ellipse((300, 340, 356, 396), fill="#1f2937")
    img.save(ROOT / "icon.png", "PNG")


if __name__ == "__main__":
    make_banner()
    make_icon()
