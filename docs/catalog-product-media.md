# Catalog product media

## Current rollout

The storefront keeps category icons for navigation and uses product-specific
media inside product cards and detail pages. The first media rollout covers
the 140 priority products in `general_goods_v1.json`.

These files are AI-generated illustrative packshots, not photographs of a
specific supplier's inventory. The API and storefront therefore expose them
as `Illustrative preview`. They must not be presented as verified supplier
photos or exported to a merchant feed that requires an actual-product image.

Runtime copies are stored under:

- `apps/web-next/public/media/products/illustrative/`
- `services/catalog-service/media/products/illustrative/`

Both copies must remain byte-identical until catalog media moves to managed
object storage.

## Final generation prompt set

The built-in image generator was used with the `product-mockup` use case.
Each category used this common production prompt:

> Create exactly the listed unbranded products as distinct photorealistic
> ecommerce packshots in a precise contact-sheet grid. Give every cell the
> same warm-white studio background with a subtle pale-blue floor gradient
> and clear straight gutters. Place one complete object in each cell in exact
> reading order, centered with generous padding and consistent three-quarter
> framing. Use soft commercial softbox lighting and controlled natural
> shadows. Do not include people, hands, packaging, brands, logos, promotional
> text, numbers, watermarks, decorative props, overlapping cells, duplicate
> products, or cropped edges.

The exact subject order for each sheet matches the product order in the
manifest:

- Mobile Accessories: 12 products, 4 × 3 grid
- Laptop & PC Accessories: 12 products, 4 × 3 grid
- Educational & Academic Tools: 12 products, 4 × 3 grid
- Creator & Content Tools: 12 products, 4 × 3 grid
- E-commerce Packaging Supplies: 12 products, 4 × 3 grid
- Home Organization & Storage: 12 products, 4 × 3 grid
- Fashion Accessories: 12 products, 4 × 3 grid
- Beauty Tools & Accessories: 12 products, 4 × 3 grid
- Kitchen Utility Tools: 12 products, 4 × 3 grid
- Office & Desk Accessories: 12 products, 4 × 3 grid
- Travel & Luggage Accessories: 10 products, 5 × 2 grid
- Pet Care Accessories: 10 products, 5 × 2 grid

Every selected cell was visually reviewed, center-cropped and encoded as a
720 × 720 WebP. The manifest maps each product to its corresponding image.

## Replacing an illustration

An administrator can open `/admin/catalog/media`, locate the product and
replace the illustration with an approved HTTPS CDN URL or owned
`/media/products/` path. The update requires an audit note. Random placeholder
services and unsafe local paths are rejected.

Use a real, product-specific supplier image whenever it becomes available.
Record permission to use it, keep a neutral consistent crop, and do not let a
seed refresh overwrite an operator-managed image.
