import type { AppLocale } from "./locale-context";

export const sourcingCopy = {
  en: {
    addToQuote: "Add to quote",
    addedToBasket: "Added to sourcing basket",
    alreadyInBasket: "Quantity updated in sourcing basket",
    basket: "Sourcing basket",
    basketEmpty: "Your sourcing basket is empty",
    basketEmptyHelp: "Add products to compare quantities, origins, risk, and estimated product cost before requesting quotes.",
    confirmSupplier: "Confirm with supplier",
    continueSourcing: "Continue sourcing",
    estimatedProductCost: "Estimated product cost",
    estimatedSubtotal: "Estimated subtotal",
    estimatedUnitPrice: "Estimated unit price",
    finalQuoteDisclaimer: "Final quotation may change after supplier confirmation, shipping, customs, and availability verification.",
    from: "From",
    landedCostPending: "Landed cost pending",
    moq: "MOQ",
    origin: "Origin",
    quantity: "Quantity",
    quoteRequired: "Quote required",
    remove: "Remove",
    requestQuote: "Request quote",
    requestQuotes: "Request quotes",
    requestQuoteNow: "Request quote now",
    riskChecked: "Risk checked",
    shippingDisclaimer: "Excludes shipping, tariff, VAT, and customs charges.",
    supplierPending: "Supplier selection pending",
    undo: "Undo",
    variant: "Variant",
    viewBasket: "View basket",
    viewProduct: "View product",
  },
  bn: {
    addToQuote: "কোটে যোগ করুন",
    addedToBasket: "সোর্সিং বাস্কেটে যোগ হয়েছে",
    alreadyInBasket: "সোর্সিং বাস্কেটে পরিমাণ আপডেট হয়েছে",
    basket: "সোর্সিং বাস্কেট",
    basketEmpty: "আপনার সোর্সিং বাস্কেট খালি",
    basketEmptyHelp: "কোট চাওয়ার আগে পরিমাণ, উৎস, ঝুঁকি ও আনুমানিক পণ্য মূল্য তুলনা করতে পণ্য যোগ করুন।",
    confirmSupplier: "সাপ্লায়ারের সঙ্গে নিশ্চিত করুন",
    continueSourcing: "পণ্য খোঁজা চালিয়ে যান",
    estimatedProductCost: "আনুমানিক পণ্য মূল্য",
    estimatedSubtotal: "আনুমানিক সাবটোটাল",
    estimatedUnitPrice: "আনুমানিক একক মূল্য",
    finalQuoteDisclaimer: "সাপ্লায়ার নিশ্চিতকরণ, শিপিং, কাস্টমস ও পণ্যের প্রাপ্যতা যাচাইয়ের পর চূড়ান্ত কোট পরিবর্তিত হতে পারে।",
    from: "শুরু",
    landedCostPending: "ল্যান্ডেড কস্ট অপেক্ষমাণ",
    moq: "MOQ",
    origin: "উৎস",
    quantity: "পরিমাণ",
    quoteRequired: "কোট প্রয়োজন",
    remove: "সরান",
    requestQuote: "কোট চান",
    requestQuotes: "কোট চান",
    requestQuoteNow: "এখনই কোট চান",
    riskChecked: "ঝুঁকি যাচাইকৃত",
    shippingDisclaimer: "শিপিং, ট্যারিফ, VAT ও কাস্টমস চার্জ অন্তর্ভুক্ত নয়।",
    supplierPending: "সাপ্লায়ার নির্বাচন অপেক্ষমাণ",
    undo: "ফিরিয়ে নিন",
    variant: "ভ্যারিয়েন্ট",
    viewBasket: "বাস্কেট দেখুন",
    viewProduct: "পণ্য দেখুন",
  },
} as const;

export type SourcingCopyKey = keyof typeof sourcingCopy.en;

export function sourcingText(locale: AppLocale, key: SourcingCopyKey) {
  return sourcingCopy[locale][key];
}

const catalogLabelsBn: Record<string, string> = {
  "Standard supplier-declared specification": "সাপ্লায়ার-ঘোষিত স্ট্যান্ডার্ড স্পেসিফিকেশন",
  "Home Organization & Storage": "বাড়ি গোছানো ও সংরক্ষণ",
  "Laptop & PC Accessories": "ল্যাপটপ ও পিসি অ্যাকসেসরিজ",
  "Educational & Academic Tools": "শিক্ষা ও একাডেমিক সরঞ্জাম",
  "Creator & Content Tools": "ক্রিয়েটর ও কনটেন্ট সরঞ্জাম",
  "Packaging & E-commerce Supplies": "প্যাকেজিং ও ই-কমার্স সরঞ্জাম",
  "Office & Desk Accessories": "অফিস ও ডেস্ক অ্যাকসেসরিজ",
};

export function localizedCatalogLabel(locale: AppLocale, value: string) {
  return locale === "bn" ? catalogLabelsBn[value] || value : value;
}

const recommendationTextBn: Record<string, string> = {
  "Lowest landed cost.": "সর্বনিম্ন ল্যান্ডেড কস্ট।",
  "Fastest ETA.": "সবচেয়ে দ্রুত সম্ভাব্য ডেলিভারি।",
  "Strongest supplier quality.": "সাপ্লায়ারের গুণমান সবচেয়ে ভালো।",
  "Balanced trade-off across cost, ETA, and supplier quality.": "খরচ, ডেলিভারি ও সাপ্লায়ারের গুণমানের ভারসাম্যপূর্ণ সমন্বয়।",
  "limited supplier reliability": "সাপ্লায়ারের নির্ভরযোগ্যতা সীমিত",
  "quality evidence is below target": "গুণমানের প্রমাণ লক্ষ্যমাত্রার নিচে",
  "delivery time is long": "ডেলিভারি সময় বেশি",
  "sea freight has higher delay exposure": "সমুদ্রপথে বিলম্বের ঝুঁকি বেশি",
};

export function localizedRecommendationText(locale: AppLocale, value: string) {
  return locale === "bn" ? recommendationTextBn[value] || value : value;
}
