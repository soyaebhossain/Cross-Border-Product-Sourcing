"""
Assigns a relevant image_url to every Product.
Strategy (priority order):
  1. Exact product name match in SPECIFIC_URLS
  2. Product name substring match in NAME_KEYWORD_MAP  -> loremflickr single keyword
  3. Category slug match                               -> loremflickr category keyword
  4. "product" fallback

loremflickr.com: single-word keywords give the best results.
Same keyword + same lock = same photo every time.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product

# ── 1. Per-product specific image assignments (best quality) ─────────────────
# Format: lowercase product name substring → loremflickr single-word keyword
NAME_KEYWORD_MAP = [
    # ══ MOST SPECIFIC FIRST ══════════════════════════════════════════════

    # ── HVAC / AC — must come BEFORE brand checks ────────────────────────
    (["windfree", "split ac", "inverter ac", "ton ac",
      "window ac", "1.5 ton", "1 ton", "2 ton"],                      "airconditioner"),
    (["air purifier fan", "air purifier"],                            "airpurifier"),

    # ── PC Components (specific model names before generic words) ────────
    (["rtx 4090", "rtx 4080", "rtx 4070", "rtx 4060",
      "rtx 3090", "rtx 3080", "rtx 3070", "rtx 3060",
      "radeon rx 7", "radeon rx 6", "geforce rtx", "geforce gtx",
      "graphics card", "razer blade"],                               "gpu"),
    (["noctua nh", "nh-d15", "nh-d14", "cpu cooler",
      "h150i", "h100i", "aio cooler", "360mm aio", "240mm aio",
      "liquid cooler", "icue"],                                      "cpucooler"),
    (["rog strix b", "rog strix z", "rog strix x",
      "msi mag b", "msi mag z", "msi mpg",
      "tomahawk", "motherboard", "b650", "b760", "x670", "z790",
      "asrock b", "gigabyte b", "gigabyte z"],                       "motherboard"),
    (["rm1000", "rm850", "rm750", "rm650",
      "focus gx", "focus px", "seasonic",
      "power supply", "850w", "1000w", "750w"],                      "psu"),
    (["torrent case", "o11 dynamic", "define r", "fractal",
      "lian li", "pc case", "mid tower", "full tower", "atx case"],  "pccase"),
    (["fury beast", "vengeance ddr", "trident z5",
      "ddr5", "ddr4", "dimm", "sodimm"],                             "ram"),
    (["980 pro", "sn850x", "sn850", "t700 ssd", "970 evo",
      "nvme ssd", "m.2 ssd", "pcie ssd"],                            "ssd"),
    (["barracuda", "seagate", "wd blue hdd", "hard drive", "hdd"],   "harddisk"),
    (["core i9", "core i7", "core i5", "core i3",
      "ryzen 9", "ryzen 7", "ryzen 5", "ryzen 3"],                   "cpu"),
    (["proart", "ultrawide monitor", "4k monitor", "gaming monitor"], "monitor"),
    (["elgato", "capture card"],                                     "streamdeck"),

    # ── Phones ──────────────────────────────────────────────────────────
    (["iphone"],                      "iphone"),
    (["galaxy s2", "galaxy s1", "galaxy note"],      "samsung"),
    (["galaxy a", "galaxy m", "galaxy f"],           "samsung"),
    (["galaxy watch"],                "smartwatch"),
    (["galaxy tab"],                  "tablet"),
    (["samsung"],                     "samsung"),
    (["xiaomi 14", "xiaomi 13", "xiaomi 12"],        "smartphone"),
    (["redmi note", "redmi 1", "redmi 9", "redmi 8",
      "redmi 7", "redmi 6", "redmi 5", "redmi 13", "redmi 12"],      "smartphone"),
    (["oppo reno", "oppo a", "oppo f"],              "smartphone"),
    (["vivo v", "vivo y", "vivo x"],  "smartphone"),
    (["realme"],                      "smartphone"),
    (["tecno spark", "tecno camon"],  "smartphone"),
    (["infinix note", "infinix hot"], "smartphone"),
    (["motorola edge", "moto g", "moto e"],          "smartphone"),
    (["nokia"],                       "nokia"),
    (["sony xperia"],                 "smartphone"),
    (["google pixel"],                "smartphone"),
    (["oneplus"],                     "smartphone"),
    (["honor"],                       "smartphone"),

    # ── Tablets ─────────────────────────────────────────────────────────
    (["ipad"],                        "ipad"),
    (["galaxy tab s", "galaxy tab a"],"tablet"),

    # ── Audio ───────────────────────────────────────────────────────────
    (["wh-1000", "xm5", "xm4", "xm3",
      "headphones", "headset", "over-ear"],                          "headphones"),
    (["earbuds", "earphone", "live pro", "liberty 4",
      "soundcore"],                                                   "earphones"),
    (["jbl charge", "jbl flip", "jbl boombox",
      "bluetooth speaker", "portable speaker"],                      "speaker"),

    # ── Wearables ───────────────────────────────────────────────────────
    (["apple watch"],                 "applewatch"),
    (["garmin forerunner", "garmin fenix"],           "smartwatch"),
    (["smart band", "mi band"],       "smartwatch"),

    # ── Power / Charging ────────────────────────────────────────────────
    (["power bank", "powerbank", "anker 737", "24000mah",
      "20000mah", "10000mah"],                                        "powerbank"),
    (["gan charger", "65w charger", "45w charger",
      "boostcharge", "baseus charger"],                               "charger"),

    # ── Networking ──────────────────────────────────────────────────────
    (["deco xe", "deco x", "mesh wifi", "mesh wi-fi",
      "wifi router", "wi-fi router", "wireless router"],              "router"),

    # ── Cameras & Drones ────────────────────────────────────────────────
    (["canon eos", "nikon d", "fujifilm x", "sony a7", "sony a6"],   "camera"),
    (["dji mini", "dji air", "dji mavic", "drone"],                  "drone"),

    # ── Gaming / Consoles ───────────────────────────────────────────────
    (["nintendo switch"],             "nintendoswitch"),

    # ── Fans & HVAC ─────────────────────────────────────────────────────
    (["ceiling fan", "1200mm fan", "1400mm fan",
      "esteem", "energion", "stealth air"],                           "ceilingfan"),
    (["tower fan", "slim fan"],                                       "towerfan"),
    (["split ac", "1.5 ton", "1 ton", "windfree",
      "inverter ac", "window ac"],                                    "airconditioner"),
    (["exhaust fan"],                 "exhaustfan"),
    (["industrial fan", "maf20"],     "industrialfan"),
    (["table fan", "desk fan", "stand fan", "pedestal fan",
      "rechargeable fan", "windmill", "turbo silence",
      "turboforce", "whole room"],                                    "fan"),

    # ── TVs & Displays ──────────────────────────────────────────────────
    (["smart tv", "qled", "oled tv", "43\"", "55\"", "65\""],         "smarttv"),
    (["projector"],                   "projector"),
    (["monitor", "display"],          "monitor"),
    (["laptop"],                      "laptop"),

    # ── Input devices ───────────────────────────────────────────────────
    (["keyboard"],                    "keyboard"),
    (["mouse"],                       "mouse"),

    # ── Beauty ──────────────────────────────────────────────────────────
    (["haircare", "hair care"],       "shampoo"),
    (["skincare", "skin care"],       "skincare"),
    (["cosmetics", "makeup", "lipstick", "foundation"], "lipstick"),

    # ── Light ───────────────────────────────────────────────────────────
    (["led", "light", "bulb", "lamp"],                               "ledlight"),

    # ── Generic fallbacks ────────────────────────────────────────────────
    (["watch"],                       "watch"),
    (["cpu", "processor"],            "cpu"),
    (["ssd", "nvme"],                 "ssd"),
    (["gpu", "radeon", "geforce"],    "gpu"),
    (["router", "modem", "wifi"],     "router"),
]

# ── 2. Category fallback keywords ────────────────────────────────────────────
CATEGORY_KEYWORD = {
    "phones":        "smartphone",
    "electronics":   "electronics",
    "pc-components": "computer",
    "pc":            "computer",
    "electronic":    "fan",      # Fan category has slug "electronic"
    "fan":           "fan",
    "haircare":      "shampoo",
    "skincare":      "skincare",
    "cosmetics":     "lipstick",
    "laptop":        "laptop",
    "networking":    "router",
    "power":         "powerbank",
}


def _get_keyword(product_name: str, category_slug: str) -> str:
    name_lower = product_name.lower()
    for triggers, keyword in NAME_KEYWORD_MAP:
        if any(t in name_lower for t in triggers):
            return keyword

    slug = (category_slug or "").lower()
    for key, keyword in CATEGORY_KEYWORD.items():
        if key in slug:
            return keyword

    return "product"


def _url(keyword: str, lock: int) -> str:
    return f"https://loremflickr.com/400/400/{keyword}?lock={lock}"


class Command(BaseCommand):
    help = "Assign relevant image_url to all products using per-product keyword matching"

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true",
                            help="Re-assign even if image_url already set")

    def handle(self, *args, **options):
        overwrite = options["overwrite"]
        qs = Product.objects.select_related("category").all().order_by("category__name", "id")

        updated = 0
        for product in qs:
            if product.image and not overwrite:
                continue
            if product.image_url and not overwrite:
                continue

            cat_slug = product.category.slug if product.category else ""
            keyword  = _get_keyword(product.name, cat_slug)
            lock     = product.id * 3 + 7   # consistent, spread out

            product.image_url = _url(keyword, lock)
            product.save(update_fields=["image_url"])
            updated += 1
            self.stdout.write(f"  [{product.id:>3}] {product.name:<45} -> {keyword}")

        self.stdout.write(self.style.SUCCESS(f"\nDone -- {updated} updated."))
