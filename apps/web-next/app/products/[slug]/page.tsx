import Link from "next/link";
import { notFound } from "next/navigation";
import { getCheapestCountryRecommendation, getProductBySlug, resolveImageUrl } from "../../../lib/api";
import { SourcingWorkspace } from "../../../components/sourcing-workspace";
import { ProductImage } from "../../../components/product-image";

type ProductDetailPageProps = {
  params: Promise<{ slug: string }>;
};

export default async function ProductDetailPage({ params }: ProductDetailPageProps) {
  const { slug } = await params;

  try {
    const product = await getProductBySlug(slug);
    const image = resolveImageUrl(product.image);
    const primaryVariantId = product.default_variant_id ?? product.variants[0]?.id;
    const recommendation = primaryVariantId
      ? await getCheapestCountryRecommendation({
          variant_id: primaryVariantId,
          qty: 1,
          delivery_type: "DOOR",
          priority: "balanced",
        }).catch(() => null)
      : null;

    return (
      <main className="shell shell--narrow">
        <Link href="/" className="back-link">
          Back to catalog
        </Link>

        <section className="detail">
          <div className="detail__media">
            <ProductImage src={image} name={product.name} category={product.category.name} />
          </div>

          <div className="detail__copy">
            <p className="eyebrow">{product.category.name}</p>
            <h1>{product.name}</h1>
            <p className="lede">{product.description || "No description has been migrated for this product yet."}</p>

            <div className="detail__meta">
              <div>
                <span>Model</span>
                <strong>{product.model || "N/A"}</strong>
              </div>
              <div>
                <span>Slug</span>
                <strong>{product.slug}</strong>
              </div>
              <div>
                <span>Variants</span>
                <strong>{product.variants.length}</strong>
              </div>
            </div>

            <div className="variant-list">
              {product.variants.map((variant) => (
                <div className="variant-row" key={variant.id}>
                  <div>
                    <strong>{variant.variant_name || variant.sku || `Variant ${variant.id}`}</strong>
                    <p>
                      SKU: {variant.sku || "N/A"} | Weight: {variant.weight_kg} kg
                    </p>
                  </div>
                  <span>
                    {variant.length_cm} x {variant.width_cm} x {variant.height_cm} cm
                  </span>
                </div>
              ))}
            </div>

            <section className="recommendation-panel">
              <div className="recommendation-panel__header">
                <div>
                  <p className="eyebrow">Cheapest Country</p>
                  <h2>Hybrid sourcing recommendation</h2>
                </div>
                {recommendation ? <span>{recommendation.priority} priority</span> : null}
              </div>

              {recommendation?.recommendations?.length ? (
                <div className="recommendation-list">
                  {recommendation.recommendations.slice(0, 3).map((item) => (
                    <article className="recommendation-card" key={`${item.country.code}-${item.mode}`}>
                      <div className="recommendation-card__headline">
                        <div>
                          <strong>
                            #{item.rank} {item.country.name}
                          </strong>
                          <span>{item.mode} sourcing</span>
                        </div>
                        <div className="recommendation-card__price">
                          <small>Estimated total</small>
                          <strong>BDT {item.estimated_total_bdt}</strong>
                        </div>
                      </div>

                      <div className="recommendation-card__meta">
                        <span>ETA {item.eta.min_days}-{item.eta.max_days} days</span>
                        <span>Quality {item.quality_score}/10</span>
                        <span>Reliability {item.reliability_score}</span>
                        <span className={`risk-badge risk-badge--${item.risk_level.toLowerCase()}`}>{item.risk_level} risk</span>
                      </div>

                      <p className="recommendation-card__reason">{item.reason}</p>
                      {item.weaknesses.length ? <p className="recommendation-card__reason"><strong>Watch:</strong> {item.weaknesses.join(", ")}.</p> : null}

                      <div className="recommendation-card__footer">
                        <span>{item.selected_offer.seller_name}</span>
                        <span>
                          Origin {item.selected_offer.price_origin} {item.selected_offer.currency}
                        </span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state empty-state--compact">
                  <strong>Recommendation data is not available yet.</strong>
                  <p>
                    The detail page still loads, but the sourcing engine did not return a ranked country list for this
                    request.
                  </p>
                </div>
              )}
            </section>
          </div>
        </section>
        {primaryVariantId ? <SourcingWorkspace variantId={primaryVariantId} /> : null}
      </main>
    );
  } catch {
    notFound();
  }
}
