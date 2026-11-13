import Link from "next/link";
import { notFound } from "next/navigation";
import { getCheapestCountryRecommendation, getProductBySlug, getProductMedia } from "../../../lib/api";
import { SourcingWorkspace } from "../../../components/sourcing-workspace";
import { ProductDetailActionPanel } from "../../../components/product-detail-action-panel";
import { ProductQuantityProvider } from "../../../components/product-quantity";
import { ProductGallery } from "../../../components/product-image";
import { formatBdt } from "../../../lib/format";
import { getServerLocale } from "../../../lib/server-locale";

type ProductDetailPageProps = {
  params: Promise<{ slug: string }>;
};

export default async function ProductDetailPage({ params }: ProductDetailPageProps) {
  const { slug } = await params;
  const bn = (await getServerLocale()) === "bn";

  try {
    const product = await getProductBySlug(slug);
    const media = getProductMedia(product);
    const primaryVariantId = product.default_variant_id ?? product.variants[0]?.id;
    const catalogPreview = product.catalog_source === "snapshot";
    const recommendation = primaryVariantId && !catalogPreview
      ? await getCheapestCountryRecommendation({
          variant_id: primaryVariantId,
          qty: 1,
          delivery_type: "DOOR",
          priority: "balanced",
        }).catch(() => null)
      : null;

    return (
      <main className="shell shell--narrow">
        <ProductQuantityProvider>
        <Link href="/" className="back-link">
          {bn ? "ক্যাটালগে ফিরে যান" : "Back to catalog"}
        </Link>
        {catalogPreview ? (
          <div className="catalog-preview-notice" role="status">
            <strong>{bn ? "ক্যাটালগ প্রিভিউ" : "Catalog preview"}</strong>
            <span>{bn ? "এই পণ্যটি দেখা যাচ্ছে। লাইভ সুপারিশ, কোট ও অর্ডার সাময়িকভাবে বন্ধ আছে।" : "This product is available to browse. Live recommendations, quotes and ordering are temporarily unavailable."}</span>
          </div>
        ) : null}

        <section className="detail">
          <div className="detail__media">
            <ProductGallery media={media} name={product.name} category={product.category.name} />
          </div>

          <div className="detail__copy">
            <p className="eyebrow">{product.category.name}</p>
            <h1>{product.name}</h1>
            <p className="lede">{product.description || (bn ? "এই পণ্যের বিবরণ এখনো যোগ করা হয়নি।" : "No description has been migrated for this product yet.")}</p>

            <div className="detail__meta">
              <div>
                <span>{bn ? "মডেল" : "Model"}</span>
                <strong>{product.model || "N/A"}</strong>
              </div>
              <div>
                <span>{bn ? "ভ্যারিয়েন্ট" : "Variants"}</span>
                <strong>{product.variants.length}</strong>
              </div>
            </div>

            <ProductDetailActionPanel product={product} landedCostAvailable={Boolean(primaryVariantId) && !catalogPreview} />

            <div className="variant-list">
              {product.variants.map((variant) => (
                <div className="variant-row" key={variant.id}>
                  <div>
                    <strong>{variant.variant_name || variant.sku || `Variant ${variant.id}`}</strong>
                    <p>
                      SKU: {variant.sku || "N/A"} | {bn ? "ওজন" : "Weight"}: {variant.weight_kg} kg
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
                          <strong>{formatBdt(item.estimated_total_bdt)}</strong>
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
        {primaryVariantId && !catalogPreview ? <SourcingWorkspace variantId={primaryVariantId} /> : catalogPreview ? (
          <section className="workspace catalog-preview-workspace">
            <div>
              <span className="market-kicker">{bn ? "লাইভ সোর্সিং সাময়িকভাবে বন্ধ" : "Live sourcing temporarily unavailable"}</span>
              <h2>{bn ? "কোট ও অর্ডার সেবা চালু হচ্ছে" : "Quote and order services are starting"}</h2>
              <p>{bn ? "এখন ক্যাটালগ দেখতে পারেন। নিরাপদ সেবা চালু হলে সাপ্লায়ার সুপারিশ, সেভড কোট ও চেকআউট পাওয়া যাবে।" : "You can review the catalog now. Supplier recommendations, saved quotes and checkout will be enabled when the secure service is online."}</p>
            </div>
            <button className="market-button" type="button" disabled>{bn ? "কোট এখন বন্ধ" : "Request quote unavailable"}</button>
          </section>
        ) : null}
        </ProductQuantityProvider>
      </main>
    );
  } catch {
    notFound();
  }
}
