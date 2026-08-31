from pathlib import Path
import math

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf"
WIDTH, HEIGHT = 1440, 540  # 1920x720 ratio, friendly for Canva import.

THEME = {
    "green": colors.HexColor("#10b981"),
    "green_dark": colors.HexColor("#047857"),
    "green_soft": colors.HexColor("#d1fae5"),
    "ink": colors.HexColor("#0f172a"),
    "slate": colors.HexColor("#64748b"),
    "muted": colors.HexColor("#94a3b8"),
    "line": colors.HexColor("#e2e8f0"),
    "paper": colors.HexColor("#f8fafc"),
    "white": colors.white,
    "red": colors.HexColor("#dc2626"),
    "red_soft": colors.HexColor("#fee2e2"),
    "blue": colors.HexColor("#2563eb"),
    "blue_soft": colors.HexColor("#dbeafe"),
    "amber": colors.HexColor("#f59e0b"),
    "amber_soft": colors.HexColor("#fef3c7"),
    "teal": colors.HexColor("#0d9488"),
}


def rounded_rect(c, x, y, w, h, r=18, fill=None, stroke=None, sw=1):
    c.setLineWidth(sw)
    if fill:
        c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
    c.roundRect(x, y, w, h, r, fill=1 if fill else 0, stroke=1 if stroke else 0)


def draw_gradient_bands(c, base, accent, variant=0):
    c.setFillColor(base)
    c.rect(0, 0, WIDTH, HEIGHT, fill=1, stroke=0)
    c.saveState()
    c.setFillColor(accent)
    c.setFillAlpha(0.08)
    for i in range(7):
        x = -180 + i * 260 + variant * 18
        c.rotate(0)
        p = c.beginPath()
        p.moveTo(x, -40)
        p.lineTo(x + 180, -40)
        p.lineTo(x + 460, HEIGHT + 40)
        p.lineTo(x + 280, HEIGHT + 40)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
    c.restoreState()


def brand_mark(c, x, y, scale=1.0, dark=False):
    size = 42 * scale
    rounded_rect(c, x, y, size, size, 12 * scale, THEME["white"], THEME["line"])
    c.setFillColor(THEME["red"])
    c.circle(x + 25 * scale, y + 25 * scale, 12 * scale, fill=1, stroke=0)
    c.setFillColor(THEME["white"])
    c.circle(x + 25 * scale, y + 25 * scale, 6 * scale, fill=1, stroke=0)
    c.setFillColor(THEME["red"])
    c.circle(x + 36 * scale, y + 35 * scale, 7 * scale, fill=1, stroke=0)
    c.setStrokeColor(THEME["red"])
    c.setLineWidth(4 * scale)
    c.arc(x + 6 * scale, y + 10 * scale, x + 32 * scale, y + 38 * scale, 115, 225)
    c.setFont("Helvetica-Bold", 21 * scale)
    c.setFillColor(THEME["ink"] if dark else THEME["white"])
    c.drawString(x + size + 14 * scale, y + 18 * scale, "Ava Pharmacy")


def label(c, text, x, y, bg, fg, pad_x=15, pad_y=7, size=14):
    c.setFont("Helvetica-Bold", size)
    w = stringWidth(text, "Helvetica-Bold", size) + pad_x * 2
    h = size + pad_y * 2
    rounded_rect(c, x, y, w, h, h / 2, bg, None)
    c.setFillColor(fg)
    c.drawString(x + pad_x, y + pad_y + 2, text)
    return w


def placeholder_product(c, x, y, w, h, title, color):
    rounded_rect(c, x, y, w, h, 26, colors.white, THEME["line"], 1.2)
    c.setFillColor(color)
    c.setFillAlpha(0.13)
    c.circle(x + w * 0.5, y + h * 0.62, min(w, h) * 0.28, fill=1, stroke=0)
    c.setFillAlpha(1)
    rounded_rect(c, x + w * 0.34, y + h * 0.35, w * 0.32, h * 0.42, 14, colors.white, color, 2)
    c.setFillColor(color)
    c.rect(x + w * 0.41, y + h * 0.66, w * 0.18, h * 0.035, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 15)
    c.setFillColor(THEME["ink"])
    c.drawCentredString(x + w * 0.5, y + 30, title)


def draw_safe_frame(c):
    c.saveState()
    c.setStrokeColor(THEME["line"])
    c.setDash(8, 8)
    c.setLineWidth(1)
    c.roundRect(60, 48, WIDTH - 120, HEIGHT - 96, 24, fill=0, stroke=1)
    c.restoreState()


def draw_template_one(path):
    c = canvas.Canvas(str(path), pagesize=(WIDTH, HEIGHT))
    draw_gradient_bands(c, colors.HexColor("#f8fafc"), THEME["green"], 0)
    c.setFillColor(THEME["green_soft"])
    c.setFillAlpha(0.5)
    c.circle(1220, 420, 230, fill=1, stroke=0)
    c.setFillAlpha(1)

    brand_mark(c, 76, 446, 1.0, dark=True)
    label(c, "PRODUCT SPOTLIGHT TEMPLATE", 76, 382, THEME["green_soft"], THEME["green_dark"])
    c.setFillColor(THEME["ink"])
    c.setFont("Helvetica-Bold", 58)
    c.drawString(76, 304, "Feature a hero")
    c.drawString(76, 244, "product here")
    c.setFont("Helvetica", 24)
    c.setFillColor(THEME["slate"])
    c.drawString(78, 197, "Use this area for product benefits, delivery notes,")
    c.drawString(78, 164, "price messaging, or a short promotion line.")
    rounded_rect(c, 78, 82, 244, 54, 18, THEME["green"], None)
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(colors.white)
    c.drawCentredString(200, 101, "SHOP NOW")

    placeholder_product(c, 770, 100, 235, 330, "Main product", THEME["green"])
    placeholder_product(c, 1032, 150, 180, 245, "Add-on", THEME["blue"])
    placeholder_product(c, 1225, 118, 150, 205, "Bundle", THEME["amber"])
    draw_safe_frame(c)
    c.showPage()
    c.save()


def draw_template_two(path):
    c = canvas.Canvas(str(path), pagesize=(WIDTH, HEIGHT))
    c.setFillColor(THEME["green"])
    c.rect(0, 0, WIDTH, HEIGHT, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#ecfdf5"))
    p = c.beginPath()
    p.moveTo(735, 0)
    p.lineTo(WIDTH, 0)
    p.lineTo(WIDTH, HEIGHT)
    p.lineTo(900, HEIGHT)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFillAlpha(0.14)
    for i in range(11):
        c.circle(120 + i * 122, 65 + (i % 3) * 150, 42 + (i % 2) * 18, fill=1, stroke=0)
    c.setFillAlpha(1)

    brand_mark(c, 76, 446, 1.0, dark=False)
    label(c, "PROMOTION BANNER TEMPLATE", 76, 382, colors.white, THEME["green_dark"])
    c.setFont("Helvetica-Bold", 64)
    c.setFillColor(colors.white)
    c.drawString(76, 303, "Seasonal offers")
    c.setFont("Helvetica", 25)
    c.drawString(80, 250, "Replace this copy with campaign name, date,")
    c.drawString(80, 214, "discount, or category promotion.")
    rounded_rect(c, 78, 116, 330, 58, 18, colors.white, None)
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(THEME["green_dark"])
    c.drawCentredString(243, 136, "ADD OFFER DETAILS")

    rounded_rect(c, 935, 105, 330, 330, 42, colors.white, None)
    c.setFillColor(THEME["red_soft"])
    c.circle(1100, 270, 118, fill=1, stroke=0)
    c.setFillColor(THEME["red"])
    c.setFont("Helvetica-Bold", 74)
    c.drawCentredString(1100, 282, "%")
    c.setFont("Helvetica-Bold", 25)
    c.drawCentredString(1100, 226, "PROMO BADGE")
    rounded_rect(c, 895, 66, 430, 62, 18, THEME["amber_soft"], THEME["amber"], 1.4)
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.HexColor("#92400e"))
    c.drawCentredString(1110, 87, "PLACE PRICE / COUPON / SAVINGS HERE")
    draw_safe_frame(c)
    c.showPage()
    c.save()


def draw_template_three(path):
    c = canvas.Canvas(str(path), pagesize=(WIDTH, HEIGHT))
    draw_gradient_bands(c, colors.HexColor("#f0fdfa"), THEME["teal"], 2)
    c.setFillColor(THEME["blue_soft"])
    c.setFillAlpha(0.56)
    c.circle(1250, 80, 260, fill=1, stroke=0)
    c.setFillAlpha(1)

    brand_mark(c, 76, 446, 1.0, dark=True)
    label(c, "WELLNESS + SERVICES TEMPLATE", 76, 382, colors.HexColor("#ccfbf1"), THEME["teal"])
    c.setFont("Helvetica-Bold", 54)
    c.setFillColor(THEME["ink"])
    c.drawString(76, 305, "Health essentials")
    c.drawString(76, 248, "for every day")
    c.setFont("Helvetica", 23)
    c.setFillColor(THEME["slate"])
    c.drawString(78, 203, "Use for wellness categories, pharmacy services,")
    c.drawString(78, 171, "care bundles, diagnostics, and repeat purchases.")

    for i, (txt, col) in enumerate(
        [("Fast delivery", THEME["green"]), ("Pharmacist support", THEME["blue"]), ("Trusted brands", THEME["teal"])]
    ):
        label(c, txt, 78 + i * 205, 95, colors.white, col, size=15)

    for i in range(3):
        x = 800 + i * 170
        y = 148 + int(32 * math.sin(i + 1))
        placeholder_product(c, x, y, 142, 210, f"Slot {i + 1}", [THEME["green"], THEME["blue"], THEME["teal"]][i])
    rounded_rect(c, 1135, 330, 210, 82, 24, colors.white, THEME["line"])
    c.setFillColor(THEME["green_soft"])
    c.circle(1178, 371, 25, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(THEME["ink"])
    c.drawString(1215, 378, "Care bundle")
    c.setFont("Helvetica", 15)
    c.setFillColor(THEME["slate"])
    c.drawString(1215, 354, "Add service note")
    draw_safe_frame(c)
    c.showPage()
    c.save()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    draw_template_one(OUT / "ava-banner-template-01-product-spotlight.pdf")
    draw_template_two(OUT / "ava-banner-template-02-promotion.pdf")
    draw_template_three(OUT / "ava-banner-template-03-wellness-services.pdf")


if __name__ == "__main__":
    main()
