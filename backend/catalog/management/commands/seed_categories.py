"""
Seeds at least 25 products per category.
Safe to re-run — skips existing slugs.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from catalog.models import Category, Product, ProductVariant

PRODUCTS = {
    "phones": [
        {"name": "Samsung Galaxy S24 Ultra", "model": "SM-S928B", "variants": [{"name": "12GB/256GB", "w": 0.232, "l": 16.2, "wi": 7.9, "h": 0.86}]},
        {"name": "Samsung Galaxy A55", "model": "SM-A556B", "variants": [{"name": "8GB/256GB", "w": 0.213, "l": 16.1, "wi": 7.7, "h": 0.82}]},
        {"name": "Samsung Galaxy M14", "model": "SM-M146B", "variants": [{"name": "4GB/64GB", "w": 0.192, "l": 16.7, "wi": 7.7, "h": 0.91}]},
        {"name": "Xiaomi 14 Ultra", "model": "23116PN5BC", "variants": [{"name": "16GB/512GB", "w": 0.222, "l": 16.2, "wi": 7.5, "h": 0.90}]},
        {"name": "Xiaomi Redmi Note 13 Pro", "model": "23090RA98G", "variants": [{"name": "12GB/256GB", "w": 0.187, "l": 16.2, "wi": 7.5, "h": 0.80}]},
        {"name": "Xiaomi Redmi 13C", "model": "23100RN82L", "variants": [{"name": "4GB/128GB", "w": 0.192, "l": 16.8, "wi": 7.8, "h": 0.88}]},
        {"name": "OPPO Reno 11 Pro", "model": "CPH2599", "variants": [{"name": "12GB/256GB", "w": 0.194, "l": 16.2, "wi": 7.4, "h": 0.77}]},
        {"name": "OPPO A79 5G", "model": "CPH2557", "variants": [{"name": "8GB/256GB", "w": 0.193, "l": 16.8, "wi": 7.7, "h": 0.79}]},
        {"name": "Vivo V29 Pro", "model": "V2250", "variants": [{"name": "12GB/256GB", "w": 0.186, "l": 16.4, "wi": 7.5, "h": 0.79}]},
        {"name": "Vivo Y100", "model": "V2321", "variants": [{"name": "8GB/256GB", "w": 0.189, "l": 16.7, "wi": 7.7, "h": 0.79}]},
        {"name": "Realme 12 Pro Plus", "model": "RMX3840", "variants": [{"name": "12GB/512GB", "w": 0.196, "l": 16.2, "wi": 7.4, "h": 0.79}]},
        {"name": "Realme C67", "model": "RMX3890", "variants": [{"name": "8GB/256GB", "w": 0.191, "l": 16.7, "wi": 7.7, "h": 0.79}]},
        {"name": "Tecno Spark 20 Pro", "model": "KJ6", "variants": [{"name": "8GB/256GB", "w": 0.195, "l": 16.7, "wi": 7.7, "h": 0.80}]},
        {"name": "Tecno Camon 20", "model": "CK6", "variants": [{"name": "8GB/256GB", "w": 0.189, "l": 16.6, "wi": 7.6, "h": 0.79}]},
        {"name": "Infinix Note 40 Pro", "model": "X6850", "variants": [{"name": "12GB/256GB", "w": 0.194, "l": 16.4, "wi": 7.5, "h": 0.79}]},
        {"name": "Infinix Hot 40i", "model": "X6528B", "variants": [{"name": "4GB/128GB", "w": 0.188, "l": 16.8, "wi": 7.7, "h": 0.84}]},
        {"name": "Motorola Edge 50 Pro", "model": "XT2429-1", "variants": [{"name": "12GB/512GB", "w": 0.186, "l": 16.1, "wi": 7.3, "h": 0.82}]},
        {"name": "Motorola Moto G85", "model": "XT2357-1", "variants": [{"name": "12GB/256GB", "w": 0.171, "l": 16.1, "wi": 7.4, "h": 0.77}]},
        {"name": "Nokia G42 5G", "model": "TA-1581", "variants": [{"name": "6GB/128GB", "w": 0.193, "l": 16.5, "wi": 7.6, "h": 0.88}]},
        {"name": "Sony Xperia 10 VI", "model": "XQ-ES54", "variants": [{"name": "6GB/128GB", "w": 0.164, "l": 15.5, "wi": 6.8, "h": 0.86}]},
        {"name": "Google Pixel 8a", "model": "G9GVN", "variants": [{"name": "8GB/128GB", "w": 0.188, "l": 15.2, "wi": 7.2, "h": 0.86}]},
        {"name": "OnePlus 12R", "model": "CPH2609", "variants": [{"name": "16GB/256GB", "w": 0.207, "l": 16.3, "wi": 7.5, "h": 0.88}]},
        {"name": "Honor 90 Smart", "model": "WDY-LX1", "variants": [{"name": "4GB/128GB", "w": 0.183, "l": 16.4, "wi": 7.6, "h": 0.81}]},
    ],
    "electronics": [
        {"name": "Apple iPad Air M2 11\"", "model": "MUWD3LL/A", "variants": [{"name": "128GB Wi-Fi", "w": 0.462, "l": 24.8, "wi": 17.9, "h": 0.61}]},
        {"name": "Samsung Galaxy Tab S9 FE", "model": "SM-X510", "variants": [{"name": "6GB/128GB", "w": 0.523, "l": 25.6, "wi": 16.5, "h": 0.63}]},
        {"name": "Sony WH-1000XM5 Headphones", "model": "WH1000XM5/B", "variants": [{"name": "Black", "w": 0.250, "l": 26.2, "wi": 19.3, "h": 8.5}]},
        {"name": "JBL Charge 5 Speaker", "model": "JBLCHARGE5BLK", "variants": [{"name": "Black", "w": 0.960, "l": 22.1, "wi": 9.6, "h": 9.3}]},
        {"name": "Apple Watch Series 9 45mm", "model": "MR993LL/A", "variants": [{"name": "GPS", "w": 0.039, "l": 4.5, "wi": 3.8, "h": 1.08}]},
        {"name": "Samsung Galaxy Watch 6", "model": "SM-R930NZAAXFE", "variants": [{"name": "44mm Black", "w": 0.033, "l": 4.4, "wi": 4.5, "h": 0.9}]},
        {"name": "Garmin Forerunner 265", "model": "010-02810-01", "variants": [{"name": "46mm", "w": 0.047, "l": 4.6, "wi": 4.6, "h": 1.30}]},
        {"name": "Anker 737 Power Bank 24K", "model": "A1289", "variants": [{"name": "24000mAh", "w": 0.634, "l": 16.3, "wi": 7.1, "h": 3.0}]},
        {"name": "Baseus 65W GaN Charger", "model": "CCGP140201", "variants": [{"name": "3-Port", "w": 0.128, "l": 6.2, "wi": 6.2, "h": 3.1}]},
        {"name": "Xiaomi Smart TV A2 43\"", "model": "L43M8-A2EU", "variants": [{"name": "43 inch", "w": 6.2, "l": 97.0, "wi": 56.0, "h": 6.3}]},
        {"name": "Philips 27\" 4K Monitor", "model": "27E1N5500", "variants": [{"name": "IPS 4K", "w": 6.2, "l": 61.3, "wi": 42.5, "h": 22.0}]},
        {"name": "Logitech MX Master 3S Mouse", "model": "910-006556", "variants": [{"name": "Graphite", "w": 0.141, "l": 12.4, "wi": 8.4, "h": 5.1}]},
        {"name": "Keychron K2 Pro Keyboard", "model": "K2P-B2", "variants": [{"name": "RGB Aluminium", "w": 0.720, "l": 31.3, "wi": 12.4, "h": 3.8}]},
        {"name": "JBL Earbuds Live Pro 2", "model": "JBLLIVEPRO2TWS", "variants": [{"name": "Black", "w": 0.060, "l": 6.6, "wi": 5.5, "h": 3.0}]},
        {"name": "Xiaomi Smart Band 8 Pro", "model": "BHR7208GL", "variants": [{"name": "Black", "w": 0.036, "l": 4.8, "wi": 3.6, "h": 1.04}]},
        {"name": "TP-Link Deco XE75 Mesh WiFi", "model": "DECO XE75", "variants": [{"name": "2-Pack", "w": 0.840, "l": 16.0, "wi": 16.0, "h": 13.0}]},
        {"name": "Canon EOS R50 Camera", "model": "5811C002", "variants": [{"name": "Body Only", "w": 0.375, "l": 11.6, "wi": 8.5, "h": 6.8}]},
        {"name": "DJI Mini 4 Pro Drone", "model": "CP.MA.00000731.01", "variants": [{"name": "Standard", "w": 0.249, "l": 21.0, "wi": 9.6, "h": 6.2}]},
        {"name": "Nintendo Switch OLED", "model": "HEG-001", "variants": [{"name": "White", "w": 0.420, "l": 24.2, "wi": 10.2, "h": 1.36}]},
        {"name": "Xiaomi Portable Laser Projector", "model": "BHR5594GL", "variants": [{"name": "White", "w": 1.38, "l": 19.5, "wi": 12.6, "h": 6.7}]},
        {"name": "Anker Soundcore Liberty 4 NC", "model": "A3947", "variants": [{"name": "Black", "w": 0.056, "l": 6.4, "wi": 5.7, "h": 2.8}]},
        {"name": "Belkin BoostCharge Pro 3-in-1", "model": "WIZ017dqWH", "variants": [{"name": "White", "w": 0.198, "l": 24.0, "wi": 12.0, "h": 5.0}]},
    ],
    "pc-components": [
        {"name": "NVIDIA GeForce RTX 4060 Ti", "model": "RTX 4060 Ti 8GB", "variants": [{"name": "8GB GDDR6", "w": 0.652, "l": 24.0, "wi": 12.0, "h": 4.0}]},
        {"name": "AMD Radeon RX 7600 XT", "model": "RX 7600 XT 16GB", "variants": [{"name": "16GB GDDR6", "w": 0.750, "l": 24.0, "wi": 12.0, "h": 4.0}]},
        {"name": "Intel Core i9-14900K", "model": "BX8071514900K", "variants": [{"name": "LGA1700 125W", "w": 0.034, "l": 3.7, "wi": 3.7, "h": 0.4}]},
        {"name": "AMD Ryzen 9 7950X", "model": "100-100000514WOF", "variants": [{"name": "AM5 170W", "w": 0.068, "l": 4.0, "wi": 4.0, "h": 0.35}]},
        {"name": "Intel Core i5-14600K", "model": "BX8071514600K", "variants": [{"name": "LGA1700 125W", "w": 0.034, "l": 3.7, "wi": 3.7, "h": 0.4}]},
        {"name": "AMD Ryzen 5 7600X", "model": "100-100000593WOF", "variants": [{"name": "AM5 105W", "w": 0.034, "l": 4.0, "wi": 4.0, "h": 0.35}]},
        {"name": "Kingston Fury Beast 32GB DDR5", "model": "KF556C40BBK2-32", "variants": [{"name": "2x16GB 5600MHz", "w": 0.048, "l": 13.5, "wi": 3.3, "h": 0.3}]},
        {"name": "Corsair Vengeance 16GB DDR5", "model": "CMK16GX5M1B5200C40", "variants": [{"name": "1x16GB 5200MHz", "w": 0.034, "l": 13.5, "wi": 3.0, "h": 0.3}]},
        {"name": "Samsung 980 Pro 2TB NVMe SSD", "model": "MZ-V8P2T0B/AM", "variants": [{"name": "PCIe 4.0 M.2", "w": 0.009, "l": 8.0, "wi": 2.2, "h": 0.23}]},
        {"name": "WD Black SN850X 1TB SSD", "model": "WDS100T2X0E", "variants": [{"name": "PCIe 4.0 M.2", "w": 0.008, "l": 8.0, "wi": 2.2, "h": 0.23}]},
        {"name": "Seagate Barracuda 4TB HDD", "model": "ST4000DM004", "variants": [{"name": "3.5\" SATA 6Gb/s", "w": 0.400, "l": 14.7, "wi": 10.2, "h": 2.6}]},
        {"name": "ASUS ROG Strix B650-F Gaming", "model": "90MB1BN0-M0EAY0", "variants": [{"name": "ATX AM5", "w": 1.400, "l": 30.5, "wi": 24.4, "h": 5.5}]},
        {"name": "MSI MAG B760 Tomahawk WiFi", "model": "MAG B760 TOMAHAWK WIFI", "variants": [{"name": "ATX LGA1700", "w": 1.300, "l": 30.5, "wi": 24.4, "h": 5.5}]},
        {"name": "Corsair RM1000x 1000W PSU", "model": "CP-9020201-EU", "variants": [{"name": "80+ Gold Full Mod", "w": 1.680, "l": 18.0, "wi": 15.0, "h": 8.6}]},
        {"name": "Seasonic Focus GX-850", "model": "SSR-850FX", "variants": [{"name": "850W 80+ Gold", "w": 1.500, "l": 14.0, "wi": 15.0, "h": 8.6}]},
        {"name": "Noctua NH-D15 CPU Cooler", "model": "NH-D15", "variants": [{"name": "Dual Tower 140mm", "w": 0.990, "l": 16.5, "wi": 15.0, "h": 16.8}]},
        {"name": "Corsair iCUE H150i Elite LCD", "model": "CW-9060060-WW", "variants": [{"name": "360mm AIO", "w": 0.985, "l": 39.5, "wi": 12.0, "h": 2.7}]},
        {"name": "Fractal Design Torrent Case", "model": "FD-C-TOR1A-01", "variants": [{"name": "Full Tower ATX", "w": 5.300, "l": 53.0, "wi": 24.0, "h": 53.0}]},
        {"name": "Lian Li O11 Dynamic EVO", "model": "PC-O11DEX-3", "variants": [{"name": "Mid Tower ATX", "w": 4.200, "l": 46.5, "wi": 23.4, "h": 47.4}]},
        {"name": "Crucial T700 2TB PCIe 5.0 SSD", "model": "CT2000T700SSD3", "variants": [{"name": "PCIe 5.0 M.2", "w": 0.014, "l": 8.0, "wi": 2.2, "h": 0.35}]},
        {"name": "G.Skill Trident Z5 RGB 64GB", "model": "F5-6400J3239G32GX2-TZ5RK", "variants": [{"name": "2x32GB DDR5 6400", "w": 0.096, "l": 13.5, "wi": 4.4, "h": 0.3}]},
        {"name": "ASUS ProArt PA329CRV 4K Monitor", "model": "PA329CRV", "variants": [{"name": "32\" 4K IPS", "w": 9.200, "l": 73.0, "wi": 48.0, "h": 22.0}]},
        {"name": "Razer Blade 16 RTX 4090", "model": "RZ09-0483", "variants": [{"name": "32GB/1TB", "w": 2.950, "l": 35.5, "wi": 25.0, "h": 1.99}]},
        {"name": "Elgato 4K60 Pro MK.2 Capture", "model": "10GAS9901", "variants": [{"name": "PCIe 4K60", "w": 0.160, "l": 16.8, "wi": 6.8, "h": 1.9}]},
    ],
    "electronic": [  # Fan category slug is "electronic"
        {"name": "Xiaomi Mi Smart Tower Fan", "model": "ZLBPLDS05ZM", "variants": [{"name": "White 40W", "w": 3.200, "l": 20.0, "wi": 20.0, "h": 87.0}]},
        {"name": "Dyson Cool AM07 Tower Fan", "model": "300172-01", "variants": [{"name": "White/Silver", "w": 2.400, "l": 21.5, "wi": 21.5, "h": 105.0}]},
        {"name": "TP-Link Tapo Smart Ceiling Fan", "model": "TF10", "variants": [{"name": "White 40W", "w": 3.600, "l": 132.0, "wi": 18.0, "h": 40.0}]},
        {"name": "Orient Airmax Ceiling Fan 56\"", "model": "AIRMAX-56-WH", "variants": [{"name": "White 70W", "w": 4.500, "l": 142.0, "wi": 18.0, "h": 40.0}]},
        {"name": "Panasonic F-M15H5 Desk Fan 6\"", "model": "F-M15H5", "variants": [{"name": "White 30W", "w": 0.880, "l": 22.0, "wi": 22.0, "h": 28.0}]},
        {"name": "Midea MAF14 14\" Stand Fan", "model": "MAF14", "variants": [{"name": "White 50W", "w": 3.800, "l": 38.0, "wi": 38.0, "h": 130.0}]},
        {"name": "Walton WPF-16E Pedestal Fan", "model": "WPF-16E", "variants": [{"name": "White 55W", "w": 4.200, "l": 40.0, "wi": 40.0, "h": 135.0}]},
        {"name": "Vision Rechargeable Fan 12\"", "model": "VRF-1200", "variants": [{"name": "White Rechargeable", "w": 1.800, "l": 32.0, "wi": 32.0, "h": 38.0}]},
        {"name": "Haier HF-14BLW Stand Fan", "model": "HF-14BLW", "variants": [{"name": "White 45W", "w": 3.900, "l": 38.0, "wi": 38.0, "h": 130.0}]},
        {"name": "Samsung WindFree 1.5 Ton AC", "model": "AR18BYHYBWKNFE", "variants": [{"name": "Split Inverter", "w": 9.500, "l": 95.0, "wi": 35.0, "h": 22.0}]},
        {"name": "General 1.5 Ton Split AC", "model": "ASGA18FMTA", "variants": [{"name": "18000 BTU", "w": 9.200, "l": 84.0, "wi": 28.5, "h": 20.0}]},
        {"name": "Gree 1 Ton Inverter AC", "model": "GS-12XPUV32", "variants": [{"name": "12000 BTU", "w": 8.400, "l": 80.0, "wi": 25.0, "h": 19.0}]},
        {"name": "Xiaomi Mijia DC Inverter Fan", "model": "BPLDS05DM", "variants": [{"name": "Desk 35dB", "w": 0.950, "l": 22.0, "wi": 22.0, "h": 38.0}]},
        {"name": "Rowenta VU5670 Turbo Silence", "model": "VU5670", "variants": [{"name": "36cm Stand", "w": 5.200, "l": 46.0, "wi": 46.0, "h": 138.0}]},
        {"name": "Honeywell HT-900 TurboForce Fan", "model": "HT-900", "variants": [{"name": "Compact Black", "w": 0.816, "l": 20.3, "wi": 15.9, "h": 26.0}]},
        {"name": "Vornado 630 Whole Room Fan", "model": "CR1-0121-06", "variants": [{"name": "Mid Size", "w": 3.600, "l": 28.6, "wi": 35.1, "h": 34.9}]},
        {"name": "KDK 56\" Industrial Ceiling Fan", "model": "K14X9-BK", "variants": [{"name": "Bronze 60W", "w": 6.200, "l": 143.0, "wi": 20.0, "h": 44.0}]},
        {"name": "Bajaj Esteem 1200mm Ceiling Fan", "model": "252241", "variants": [{"name": "White 75W", "w": 3.900, "l": 122.0, "wi": 18.0, "h": 38.0}]},
        {"name": "Crompton Energion Ceiling Fan", "model": "ENERGION-1200", "variants": [{"name": "White 28W BLDC", "w": 3.500, "l": 122.0, "wi": 18.0, "h": 38.0}]},
        {"name": "Polar Windmill 900mm Table Fan", "model": "WM-900", "variants": [{"name": "White 55W", "w": 2.100, "l": 30.0, "wi": 30.0, "h": 45.0}]},
        {"name": "Usha Striker Marvel Exhaust Fan", "model": "STRIKER-MARVEL", "variants": [{"name": "6\" White", "w": 0.420, "l": 19.0, "wi": 19.0, "h": 6.0}]},
        {"name": "Havells Stealth Air Ceiling Fan", "model": "FHCSSTWOWH48", "variants": [{"name": "1200mm White BLDC", "w": 3.700, "l": 122.0, "wi": 18.0, "h": 40.0}]},
        {"name": "Mistral 16\" Rechargeable Fan", "model": "MRF1613RB", "variants": [{"name": "White USB-C", "w": 1.950, "l": 38.0, "wi": 38.0, "h": 42.0}]},
        {"name": "Midea MAF20 20\" Industrial Fan", "model": "MAF20-IND", "variants": [{"name": "Yellow 220W", "w": 7.600, "l": 52.0, "wi": 52.0, "h": 145.0}]},
        {"name": "Sharp PJ-A19RV Air Purifier Fan", "model": "PJ-A19RV", "variants": [{"name": "White 25W", "w": 4.400, "l": 28.0, "wi": 28.0, "h": 87.0}]},
    ],
}

# image keyword map by category slug
IMAGE_KEYWORDS = {
    "phones": ["smartphone,mobile", "samsung,galaxy", "iphone,apple", "android,phone", "mobile,phone"],
    "electronics": ["electronics,gadget", "smart,device", "tablet,tech", "headphones", "smartwatch,wearable"],
    "pc-components": ["computer,gpu", "graphics,card", "cpu,processor", "computer,hardware", "gaming,pc"],
    "electronic": ["electric,fan", "ceiling,fan", "desk,fan", "air,conditioner", "cooling,fan"],
}


class Command(BaseCommand):
    help = "Seed 25+ products per category (skips existing slugs)"

    def handle(self, *args, **options):
        total_added = 0

        for cat_slug, product_list in PRODUCTS.items():
            try:
                category = Category.objects.get(slug=cat_slug)
            except Category.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Category slug '{cat_slug}' not found — skipping."))
                continue

            keywords = IMAGE_KEYWORDS.get(cat_slug, ["product,retail"])
            added = 0

            for idx, pd in enumerate(product_list):
                slug = slugify(pd["name"])
                if Product.objects.filter(slug=slug).exists():
                    self.stdout.write(f"  SKIP [{slug}] already exists")
                    continue

                keyword = keywords[idx % len(keywords)]
                lock = 1000 + idx * 7 + hash(cat_slug) % 100

                product = Product.objects.create(
                    name=pd["name"],
                    slug=slug,
                    model=pd.get("model", ""),
                    category=category,
                    image_url=f"https://loremflickr.com/400/400/{keyword}?lock={lock}",
                )

                for v in pd.get("variants", []):
                    ProductVariant.objects.create(
                        product=product,
                        variant_name=v["name"],
                        weight_kg=v["w"],
                        length_cm=v["l"],
                        width_cm=v["wi"],
                        height_cm=v["h"],
                    )

                added += 1
                total_added += 1
                self.stdout.write(f"  ADD  [{category.name}] {product.name}")

            current = Product.objects.filter(category=category).count()
            self.stdout.write(self.style.SUCCESS(
                f"  {category.name}: added {added}, total now {current}"
            ))

        self.stdout.write(self.style.SUCCESS(f"\nDone -- {total_added} new products created."))
