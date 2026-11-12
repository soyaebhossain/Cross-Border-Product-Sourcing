"use client";

import { useLocale } from "../lib/locale-context";

const STEPS = [
  { en: "Choose product", bn: "পণ্য বাছুন", helpEn: "Pick the variant, origin and quantity", helpBn: "ভ্যারিয়েন্ট, দেশ ও পরিমাণ ঠিক করুন" },
  { en: "See total cost", bn: "মোট খরচ দেখুন", helpEn: "Product, shipping, duty and VAT", helpBn: "পণ্য, শিপিং, শুল্ক ও VAT সহ" },
  { en: "Confirm and pay advance", bn: "নিশ্চিত করে অগ্রিম দিন", helpEn: "Address and payment proof", helpBn: "ঠিকানা ও পেমেন্টের প্রমাণ" },
  { en: "Track delivery", bn: "ডেলিভারি ট্র্যাক করুন", helpEn: "Follow the order in My orders", helpBn: "My orders-এ অগ্রগতি দেখুন" },
];

/** Shows where the customer is on the way from a product to a delivered order. */
export function OrderSteps({ current }: { current: 1 | 2 | 3 | 4 }) {
  const { locale } = useLocale();
  const bn = locale === "bn";
  return (
    <ol className="order-steps" aria-label={bn ? "অর্ডারের ধাপ" : "Ordering steps"}>
      {STEPS.map((step, index) => {
        const number = index + 1;
        const state = number < current ? "done" : number === current ? "current" : "todo";
        return (
          <li key={step.en} className={`order-steps__item order-steps__item--${state}`} aria-current={state === "current" ? "step" : undefined}>
            <span className="order-steps__number" aria-hidden>{state === "done" ? "✓" : number}</span>
            <span className="order-steps__text">
              <strong>{bn ? step.bn : step.en}</strong>
              <small>{bn ? step.helpBn : step.helpEn}</small>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
